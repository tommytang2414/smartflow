import base64
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import (
    CollectorRunV2,
    NormalizedEventV2,
    RawEvent,
    SourceHealth,
)
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.congress import (
    CongressIngestionStageError,
    CongressIngestionResult,
    ingest_house_ptr_pdf,
)
from smartflow.ingestion.congress_live import (
    HouseSourceError,
    fetch_house_bytes,
    ingest_house_ptr_batch,
    parse_house_index_zip,
)
from smartflow.parsers.congress_house import (
    HouseDisclosureError,
    parse_house_index_xml,
    parse_house_ptr_word_pages,
)


FIXTURES = Path(__file__).parent / "fixtures" / "congress"
OBSERVED_AT = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
PDF_BYTES = b"%PDF-1.7\nsanitized fixture bytes\n%%EOF"


def fixture_report_and_parsed():
    xml = (FIXTURES / "house_index_sanitized.xml").read_text(encoding="utf-8")
    report = parse_house_index_xml(xml, expected_year=2026)[0]
    pages = json.loads(
        (FIXTURES / "house_ptr_words_sanitized.json").read_text(encoding="utf-8")
    )
    return report, parse_house_ptr_word_pages(pages, report=report)


class FakeResponse:
    def __init__(self, content, status_code=200, content_type=None):
        self.content = content
        self.status_code = status_code
        if content_type is None:
            content_type = (
                "application/pdf"
                if content.startswith(b"%PDF-")
                else "application/x-zip-compressed"
            )
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]


class FakeHTTPSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def index_zip():
    xml = (FIXTURES / "house_index_sanitized.xml").read_bytes()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("2026FD.xml", xml)
    return output.getvalue()


class CongressIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "congress.db"
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        create_v2_schema(self.engine)
        self.report, self.parsed = fixture_report_and_parsed()

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_exact_pdf_is_recoverable_and_ingestion_is_idempotent(self):
        extractor = lambda content, report: self.parsed
        with Session(self.engine) as session:
            with patch(
                "smartflow.ingestion.congress._utc_now",
                return_value=OBSERVED_AT,
            ):
                first = ingest_house_ptr_pdf(
                    session,
                    pdf_content=PDF_BYTES,
                    report=self.report,
                    observed_at=OBSERVED_AT,
                    extractor=extractor,
                )
                second = ingest_house_ptr_pdf(
                    session,
                    pdf_content=PDF_BYTES,
                    report=self.report,
                    observed_at=OBSERVED_AT,
                    extractor=extractor,
                )

            self.assertEqual(
                (first.raw_inserted, first.normalized_inserted),
                (1, 2),
            )
            self.assertEqual(
                (second.raw_inserted, second.normalized_inserted),
                (0, 0),
            )
            raw = session.scalar(select(RawEvent))
            recovered = base64.b64decode(raw.payload["body_base64"])
            self.assertEqual(recovered, PDF_BYTES)
            self.assertEqual(
                session.scalar(select(func.count(NormalizedEventV2.id))),
                2,
            )
            self.assertEqual(session.get(SourceHealth, "congress").state, "healthy")

    def test_batch_persistence_failure_is_not_misclassified_as_parser(self):
        http = FakeHTTPSession(
            [
                FakeResponse(index_zip()),
                FakeResponse(PDF_BYTES),
            ]
        )
        error = CongressIngestionStageError(
            "persistence",
            RuntimeError("fixture persistence failure"),
        )
        with Session(self.engine) as session:
            with patch(
                "smartflow.ingestion.congress_live.ingest_house_ptr_pdf",
                side_effect=error,
            ):
                with self.assertRaises(CongressIngestionStageError):
                    ingest_house_ptr_batch(
                        session,
                        http_session=http,
                        observed_at=OBSERVED_AT,
                        year=2026,
                        max_reports=1,
                    )

            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "persistence"))
            self.assertEqual(session.get(SourceHealth, "congress").state, "degraded")

    def test_parser_failure_preserves_pdf_and_degrades_health(self):
        def reject(content, report):
            raise HouseDisclosureError("fixture parser failure")

        with Session(self.engine) as session:
            with patch(
                "smartflow.ingestion.congress._utc_now",
                return_value=OBSERVED_AT,
            ):
                with self.assertRaisesRegex(HouseDisclosureError, "fixture parser"):
                    ingest_house_ptr_pdf(
                        session,
                        pdf_content=PDF_BYTES,
                        report=self.report,
                        observed_at=OBSERVED_AT,
                        extractor=reject,
                    )

            raw = session.scalar(select(RawEvent))
            self.assertEqual(base64.b64decode(raw.payload["body_base64"]), PDF_BYTES)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.get(SourceHealth, "congress").state, "degraded")

    def test_batch_records_one_aggregate_outcome(self):
        http = FakeHTTPSession(
            [
                FakeResponse(index_zip()),
                FakeResponse(PDF_BYTES),
            ]
        )
        stub_result = CongressIngestionResult(1, 2, 2, 0, None)
        with Session(self.engine) as session:
            with patch(
                "smartflow.ingestion.congress_live.ingest_house_ptr_pdf",
                return_value=stub_result,
            ):
                result = ingest_house_ptr_batch(
                    session,
                    http_session=http,
                    observed_at=OBSERVED_AT,
                    year=2026,
                    max_reports=1,
                )

            self.assertEqual(result.reports_observed, 1)
            self.assertEqual(result.normalized_observed, 2)
            self.assertEqual(result.warning_events, 0)
            self.assertEqual(
                session.scalar(select(func.count(CollectorRunV2.id))),
                1,
            )
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.records_observed), ("success", 1))
            self.assertEqual(session.get(SourceHealth, "congress").state, "healthy")


class CongressLiveBoundaryTests(unittest.TestCase):
    def test_official_fetch_disables_redirects_and_checks_magic(self):
        http = FakeHTTPSession([FakeResponse(PDF_BYTES)])
        payload = fetch_house_bytes(
            http,
            url=(
                "https://disclosures-clerk.house.gov/public_disc/"
                "ptr-pdfs/2026/20039991.pdf"
            ),
            expected_kind="pdf",
        )
        self.assertEqual(payload, PDF_BYTES)
        self.assertFalse(http.calls[0][1]["allow_redirects"])

        with self.assertRaisesRegex(HouseSourceError, "non-official"):
            fetch_house_bytes(
                http,
                url="https://example.com/report.pdf",
                expected_kind="pdf",
            )
        bad = FakeHTTPSession([FakeResponse(b"<html>not pdf</html>")])
        with self.assertRaisesRegex(HouseSourceError, "content type is invalid"):
            fetch_house_bytes(
                bad,
                url=(
                    "https://disclosures-clerk.house.gov/public_disc/"
                    "ptr-pdfs/2026/20039991.pdf"
                ),
                expected_kind="pdf",
            )

        redirect = FakeHTTPSession([FakeResponse(b"", status_code=302)])
        with self.assertRaisesRegex(HouseSourceError, "redirect rejected"):
            fetch_house_bytes(
                redirect,
                url=(
                    "https://disclosures-clerk.house.gov/public_disc/"
                    "ptr-pdfs/2026/20039991.pdf"
                ),
                expected_kind="pdf",
            )

        oversized_response = FakeResponse(PDF_BYTES)
        oversized_response.headers["Content-Length"] = str(10 * 1024 * 1024 + 1)
        oversized = FakeHTTPSession([oversized_response])
        with self.assertRaisesRegex(HouseSourceError, "payload size is invalid"):
            fetch_house_bytes(
                oversized,
                url=(
                    "https://disclosures-clerk.house.gov/public_disc/"
                    "ptr-pdfs/2026/20039991.pdf"
                ),
                expected_kind="pdf",
            )

    def test_index_zip_reads_only_expected_year_member(self):
        reports = parse_house_index_zip(index_zip(), year=2026)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["doc_id"], "20039991")

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("wrong.xml", b"<x/>")
        with self.assertRaisesRegex(HouseDisclosureError, "missing 2026FD.xml"):
            parse_house_index_zip(output.getvalue(), year=2026)


if __name__ == "__main__":
    unittest.main()
