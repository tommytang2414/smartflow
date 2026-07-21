import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.health import (
    SourceHealthPolicy,
    evaluate_source_health,
    record_source_health,
)


NOW = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)


class SourceHealthEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = SourceHealthPolicy(
            source="sec_form4",
            expected_interval_seconds=300,
            freshness_sla_seconds=900,
        )

    def test_recent_empty_run_is_healthy_not_a_failure(self):
        assessment = evaluate_source_health(
            self.policy,
            checked_at=NOW,
            last_run_status="empty",
            last_run_at=NOW - timedelta(minutes=2),
            last_success_at=NOW - timedelta(minutes=2),
        )

        self.assertEqual((assessment.state, assessment.reason), ("healthy", "recent_empty"))

    def test_timeout_is_degraded_not_empty(self):
        assessment = evaluate_source_health(
            self.policy,
            checked_at=NOW,
            last_run_status="timeout",
            last_failure_kind="timeout",
            last_run_at=NOW - timedelta(minutes=1),
            last_success_at=NOW - timedelta(minutes=10),
        )

        self.assertEqual(assessment.state, "degraded")
        self.assertEqual(assessment.reason, "last_run_timeout:timeout")

    def test_old_success_is_stale(self):
        assessment = evaluate_source_health(
            self.policy,
            checked_at=NOW,
            last_run_status="success",
            last_run_at=NOW - timedelta(hours=1),
            last_success_at=NOW - timedelta(hours=1),
        )

        self.assertEqual(assessment.state, "stale")

    def test_disabled_and_never_run_states_are_explicit(self):
        disabled = evaluate_source_health(
            SourceHealthPolicy("sec_form4", 300, 900, enabled=False),
            checked_at=NOW,
            last_run_status=None,
            last_run_at=None,
            last_success_at=None,
        )
        unknown = evaluate_source_health(
            self.policy,
            checked_at=NOW,
            last_run_status=None,
            last_run_at=None,
            last_success_at=None,
        )

        self.assertEqual(disabled.state, "disabled")
        self.assertEqual(unknown.state, "unknown")


class SourceHealthPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "health.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_current_health_is_updated_without_duplicate_source_rows(self):
        policy = SourceHealthPolicy("sec_form4", 300, 900)
        healthy = evaluate_source_health(
            policy,
            checked_at=NOW,
            last_run_status="empty",
            last_run_at=NOW,
            last_success_at=NOW,
        )
        degraded = evaluate_source_health(
            policy,
            checked_at=NOW + timedelta(minutes=5),
            last_run_status="error",
            last_failure_kind="parser",
            last_run_at=NOW + timedelta(minutes=5),
            last_success_at=NOW,
        )

        with Session(self.engine) as session:
            record_source_health(
                session,
                policy=policy,
                assessment=healthy,
                last_run_status="empty",
                last_failure_kind=None,
                last_run_at=NOW,
                last_success_at=NOW,
                last_event_at=None,
            )
            record_source_health(
                session,
                policy=policy,
                assessment=degraded,
                last_run_status="error",
                last_failure_kind="parser",
                last_run_at=NOW + timedelta(minutes=5),
                last_success_at=NOW,
                last_event_at=None,
            )

            rows = session.scalars(select(SourceHealth)).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].state, "degraded")
            self.assertEqual(rows[0].last_failure_kind, "parser")


if __name__ == "__main__":
    unittest.main()
