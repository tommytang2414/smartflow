import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.sfc_live import (
    SFCSourceError,
    discover_sfc_short_csv_links,
    ingest_latest_sfc_short_report,
)
from smartflow.parsers.sfc_short_csv import SFCShortCSVError


FIXTURES = Path(__file__).parent / "fixtures" / "sfc"
OBSERVED_AT = datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc)
INDEX_URL = "https://www.sfc.hk/en/official-index"
LATEST_URL = "https://www.sfc.hk/-/media/EN/pdf/spr/2026/07/10/report.csv?rev=latest"
OLDER_URL = "https://www.sfc.hk/-/media/EN/pdf/spr/2026/07/03/report.csv?rev=older"


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class FakeHTTPSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, *, headers, timeout):
        self.requests.append({"url": url, "headers": headers, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def index_html():
    return f'<a href="{OLDER_URL}">CSV</a><a href="{LATEST_URL}">CSV</a>'


class SFCLiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "sfc-live.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_discovery_uses_dated_official_links_and_sorts_latest(self):
        links = discover_sfc_short_csv_links(index_html(), index_url=INDEX_URL)
        self.assertEqual([link.reporting_date.isoformat() for link in links], ["2026-07-10", "2026-07-03"])
        self.assertEqual(links[0].url, LATEST_URL)

    def test_latest_report_flows_to_v2(self):
        csv_content = (FIXTURES / "short_positions_20260710_official_excerpt.csv").read_text(
            encoding="utf-8"
        )
        http_session = FakeHTTPSession(
            [FakeResponse(200, index_html()), FakeResponse(200, csv_content)]
        )
        with Session(self.engine) as session:
            link, result = ingest_latest_sfc_short_report(
                session,
                http_session=http_session,
                observed_at=OBSERVED_AT,
                index_url=INDEX_URL,
            )
            self.assertEqual(link.reporting_date.isoformat(), "2026-07-10")
            self.assertEqual(result.normalized_inserted, 3)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 3)
            self.assertEqual(session.get(SourceHealth, "sfc_short").state, "healthy")
            self.assertIn("SmartFlow", http_session.requests[0]["headers"]["User-Agent"])

    def test_index_source_failure_is_not_empty_success(self):
        with Session(self.engine) as session:
            with self.assertRaises(SFCSourceError):
                ingest_latest_sfc_short_report(
                    session,
                    http_session=FakeHTTPSession([FakeResponse(503)]),
                    observed_at=OBSERVED_AT,
                    index_url=INDEX_URL,
                )
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "source"))

    def test_dated_link_and_csv_date_mismatch_is_parser_failure(self):
        older_csv = (FIXTURES / "short_positions_20260703_official_excerpt.csv").read_text(
            encoding="utf-8"
        )
        with Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, "does not match"):
                ingest_latest_sfc_short_report(
                    session,
                    http_session=FakeHTTPSession(
                        [FakeResponse(200, index_html()), FakeResponse(200, older_csv)]
                    ),
                    observed_at=OBSERVED_AT,
                    index_url=INDEX_URL,
                )
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))

    def test_index_schema_drift_preserves_html_evidence(self):
        with Session(self.engine) as session:
            with self.assertRaises(SFCShortCSVError):
                ingest_latest_sfc_short_report(
                    session,
                    http_session=FakeHTTPSession([FakeResponse(200, "<html>changed</html>")]),
                    observed_at=OBSERVED_AT,
                    index_url=INDEX_URL,
                )
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))


if __name__ == "__main__":
    unittest.main()
