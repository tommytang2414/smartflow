import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from smartflow.db.models_v2 import CollectorRunV2, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.health import SourceHealthPolicy
from smartflow.runtime import ProcessTimeoutError
from smartflow.runtime_v2 import run_in_process_with_v2_timeout


class V2RuntimeOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "runtime-v2.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_parent_records_terminated_timeout_and_degraded_health(self):
        policy = SourceHealthPolicy("sec_form4", 300, 900)

        with self.assertRaises(ProcessTimeoutError):
            run_in_process_with_v2_timeout(
                "tests.process_targets:sleep_for",
                policy=policy,
                session_factory=self.session_factory,
                args=(10,),
                timeout_seconds=0.2,
            )

        with Session(self.engine) as session:
            run = session.scalar(select(CollectorRunV2))
            health = session.get(SourceHealth, "sec_form4")
            self.assertEqual((run.status, run.failure_kind), ("timeout", "timeout"))
            self.assertEqual(run.error_code, "ProcessTimeoutError")
            self.assertEqual(run.details["observer"], "parent_process")
            self.assertEqual(run.details["timeout_seconds"], 0.2)
            self.assertEqual(health.state, "degraded")
            self.assertEqual(health.reason, "last_run_timeout:timeout")


if __name__ == "__main__":
    unittest.main()
