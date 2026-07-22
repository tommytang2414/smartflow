import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.sec_live import (
    SECAuthenticationError,
    SECSourceError,
    ingest_form4_url,
)
from smartflow.ingestion.sec import SECParserError


FIXTURES = Path(__file__).parent / "fixtures" / "sec"
NOW = datetime(2026, 7, 23, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class FakeHTTPSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def get(self, url, *, headers, timeout):
        self.request = {"url": url, "headers": headers, "timeout": timeout}
        if self.error:
            raise self.error
        return self.response


class SECLiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "sec-live.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def arguments(self, http_session, user_agent="SmartFlow test contact@example.com"):
        return {
            "http_session": http_session,
            "url": "https://www.sec.gov/example.xml",
            "user_agent": user_agent,
            "accession": "test-accession",
            "filed_at": NOW,
            "observed_at": NOW,
        }

    def assert_failed_run(self, session, failure_kind):
        run = session.scalar(select(CollectorRunV2))
        self.assertEqual((run.status, run.failure_kind), ("error", failure_kind))
        self.assertEqual(session.get(SourceHealth, "sec_form4").state, "degraded")
        self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 0)

    def test_missing_user_agent_is_auth_failure(self):
        with Session(self.engine) as session:
            with self.assertRaises(SECAuthenticationError):
                ingest_form4_url(session, **self.arguments(FakeHTTPSession(), user_agent=""))
            self.assert_failed_run(session, "auth")

    def test_http_403_is_auth_failure(self):
        with Session(self.engine) as session:
            with self.assertRaises(SECAuthenticationError):
                ingest_form4_url(
                    session,
                    **self.arguments(FakeHTTPSession(response=FakeResponse(403))),
                )
            self.assert_failed_run(session, "auth")

    def test_http_503_is_source_failure(self):
        with Session(self.engine) as session:
            with self.assertRaises(SECSourceError):
                ingest_form4_url(
                    session,
                    **self.arguments(FakeHTTPSession(response=FakeResponse(503))),
                )
            self.assert_failed_run(session, "source")

    def test_successful_fetch_flows_into_v2_ingestion(self):
        xml_content = (FIXTURES / "form4_purchase_official_excerpt.xml").read_text(
            encoding="utf-8"
        )
        http_session = FakeHTTPSession(response=FakeResponse(200, xml_content))
        with Session(self.engine) as session:
            result = ingest_form4_url(session, **self.arguments(http_session))

            self.assertEqual(result.normalized_inserted, 1)
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 1)
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "healthy")
            self.assertIn("contact@example.com", http_session.request["headers"]["User-Agent"])

    def test_http_200_malformed_xml_is_parser_failure_with_raw_evidence(self):
        http_session = FakeHTTPSession(response=FakeResponse(200, "<ownershipDocument>"))
        with Session(self.engine) as session:
            with self.assertRaises(SECParserError):
                ingest_form4_url(session, **self.arguments(http_session))

            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "degraded")


if __name__ == "__main__":
    unittest.main()
