import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from ops.audit_sfc_short_shadow import audit
from ops.manage_v2_shadow import create_shadow_database
from ops.publish_sfc_short_shadow import publish_snapshot
from ops.run_sfc_short_shadow import main as run_main
from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.sfc import ingest_sfc_short_csv
from smartflow.sfc_short_shadow_job import SFCShortShadowRunResult


FIXTURES = Path(__file__).parent / "fixtures" / "sfc"
CSV_CONTENT = (
    FIXTURES / "short_positions_20260710_official_excerpt.csv"
).read_text(encoding="utf-8")
SOURCE_URL = "https://www.sfc.hk/-/media/EN/pdf/spr/2026/07/10/report.csv"
OBSERVED_AT = datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc)


class SFCShortShadowTests(unittest.TestCase):
    def test_audit_and_snapshot_keep_sfc_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sfc-short-v2-shadow.db"
            create_shadow_database(database_path)
            engine = open_v2_shadow_engine(database_path)
            try:
                with Session(engine) as session:
                    with patch(
                        "smartflow.ingestion.sfc._utc_now",
                        return_value=OBSERVED_AT,
                    ):
                        ingest_sfc_short_csv(
                            session,
                            csv_content=CSV_CONTENT.replace(
                                "3672850160",
                                "n.a.",
                                1,
                            ),
                            source_url=SOURCE_URL,
                            published_at=None,
                            observed_at=OBSERVED_AT,
                        )
            finally:
                engine.dispose()

            audit_result = audit(database_path, since_days=365)
            self.assertTrue(audit_result["release_ready"])
            self.assertEqual(audit_result["raw_count"], 1)
            self.assertEqual(audit_result["event_count"], 3)
            self.assertEqual(audit_result["unexpected_sources"], [])
            self.assertEqual(audit_result["rejected_raw"], 0)

            with patch(
                "ops.publish_sfc_short_shadow._put_object",
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
                "beta/sfc-short-v2-shadow.db",
            )
            self.assertIsNone(publish_result["archive"])
            self.assertEqual(put_object.call_count, 1)

    def test_cli_uses_child_process_boundary_and_exact_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sfc-short-v2-shadow.db"
            create_shadow_database(database_path)
            fixture_result = SFCShortShadowRunResult(
                reporting_date="2026-07-17",
                cache_hit=True,
                raw_inserted=0,
                normalized_inserted=0,
                normalized_observed=0,
                run_id=16,
            )
            output = io.StringIO()
            arguments = [
                "run_sfc_short_shadow.py",
                "--database",
                str(database_path),
                "--timeout-seconds",
                "180",
            ]
            with (
                patch("sys.argv", arguments),
                patch(
                    "ops.run_sfc_short_shadow.run_in_process_with_v2_timeout",
                    return_value=fixture_result,
                ) as runner,
                redirect_stdout(output),
            ):
                run_main()

            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["result"]["cache_hit"])
            self.assertEqual(
                runner.call_args.kwargs["args"],
                (str(database_path.resolve()),),
            )
            self.assertEqual(
                runner.call_args.args[0],
                "smartflow.sfc_short_shadow_job:run_sfc_short_shadow_job",
            )


if __name__ == "__main__":
    unittest.main()
