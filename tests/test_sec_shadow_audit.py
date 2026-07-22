import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ops.audit_sec_shadow import audit
from ops.manage_v2_shadow import create_shadow_database
from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.outcomes import record_collector_outcome


class SECShadowAuditTests(unittest.TestCase):
    def test_audit_reports_reliability_without_mutating_legacy_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "smartflow-v2-shadow.db"
            create_shadow_database(database_path)
            engine = open_v2_shadow_engine(database_path)
            now = datetime.now(timezone.utc)
            try:
                with Session(engine) as session:
                    record_collector_outcome(
                        session,
                        collector="sec_form4",
                        started_at=now,
                        finished_at=now,
                        status="success",
                        failure_kind=None,
                    )
                    record_collector_outcome(
                        session,
                        collector="sec_form4",
                        started_at=now,
                        finished_at=now,
                        status="error",
                        failure_kind="source",
                    )
            finally:
                engine.dispose()

            result = audit(database_path)

            self.assertEqual(result["quick_check"], "ok")
            self.assertEqual(result["reliability"]["sec_form4"]["total_runs"], 2)
            self.assertEqual(result["reliability"]["sec_form4"]["reliability_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
