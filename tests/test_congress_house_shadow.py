import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from ops.audit_congress_house_shadow import audit
from ops.manage_v2_shadow import create_shadow_database
from ops.publish_congress_house_shadow import publish_snapshot
from ops.run_congress_house_shadow import main as run_main
from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.congress import ingest_house_ptr_pdf
from smartflow.ingestion.congress_live import HouseBatchResult
from smartflow.parsers.congress_house import (
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


class CongressHouseShadowTests(unittest.TestCase):
    def test_audit_and_snapshot_keep_congress_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "congress-house-v2-shadow.db"
            create_shadow_database(database_path)
            report, parsed = fixture_report_and_parsed()
            engine = open_v2_shadow_engine(database_path)
            try:
                with Session(engine) as session:
                    ingest_house_ptr_pdf(
                        session,
                        pdf_content=PDF_BYTES,
                        report=report,
                        observed_at=OBSERVED_AT,
                        extractor=lambda content, report: parsed,
                    )
            finally:
                engine.dispose()

            audit_result = audit(database_path, since_hours=24 * 365)
            self.assertTrue(audit_result["release_ready"])
            self.assertEqual(audit_result["raw_count"], 1)
            self.assertEqual(audit_result["event_count"], 2)
            self.assertEqual(audit_result["unexpected_sources"], [])

            with patch(
                "ops.publish_congress_house_shadow._put_object",
                return_value={
                    "status": "uploaded",
                    "version_id": "fixture-version",
                    "etag": "fixture-etag",
                },
            ) as put_object:
                publish_result = publish_snapshot(
                    database_path,
                    now=datetime(2026, 7, 26, 2, 0, tzinfo=timezone.utc),
                )

            self.assertEqual(
                publish_result["key"],
                "beta/congress-house-v2-shadow.db",
            )
            self.assertIsNone(publish_result["archive"])
            self.assertEqual(put_object.call_count, 1)

    def test_cli_uses_child_process_boundary_and_exact_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "congress-house-v2-shadow.db"
            create_shadow_database(database_path)
            fixture_result = HouseBatchResult(
                reports_available=313,
                reports_cached=25,
                reports_observed=25,
                reports_remaining=263,
                pdf_bytes_observed=1_683_635,
                raw_inserted=25,
                normalized_inserted=137,
                normalized_observed=137,
                warning_events=30,
                run_id=1,
            )
            output = io.StringIO()
            arguments = [
                "run_congress_house_shadow.py",
                "--database",
                str(database_path),
                "--year",
                "2026",
                "--limit",
                "25",
                "--timeout-seconds",
                "300",
            ]
            with (
                patch("sys.argv", arguments),
                patch(
                    "ops.run_congress_house_shadow.run_in_process_with_v2_timeout",
                    return_value=fixture_result,
                ) as runner,
                redirect_stdout(output),
            ):
                run_main()

            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["result"]["reports_remaining"], 263)
            self.assertEqual(
                runner.call_args.kwargs["args"],
                (str(database_path.resolve()), 2026, 25),
            )
            self.assertEqual(
                runner.call_args.args[0],
                "smartflow.congress_house_shadow_job:run_congress_house_shadow_job",
            )


if __name__ == "__main__":
    unittest.main()
