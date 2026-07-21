import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from smartflow.db.models import Base, TrackedEntity
from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent
from smartflow.db.v2_schema import V2_TABLES, create_v2_schema
from smartflow.events import make_source_event_id, payload_sha256


class EventIdentityTests(unittest.TestCase):
    def test_source_event_id_is_stable_and_source_scoped(self):
        first = make_source_event_id("SEC_FORM4", "accession", 1)
        second = make_source_event_id("sec_form4", "accession", 1)

        self.assertEqual(first, second)
        self.assertNotEqual(first, make_source_event_id("sec_form4", "accession", 2))

    def test_source_event_id_rejects_incomplete_identity(self):
        with self.assertRaises(ValueError):
            make_source_event_id("sec_form4", "")

    def test_payload_hash_ignores_dictionary_key_order(self):
        self.assertEqual(payload_sha256({"a": 1, "b": 2}), payload_sha256({"b": 2, "a": 1}))


class V2SchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "legacy-copy.db"
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add(
                TrackedEntity(
                    entity_type="insider",
                    name="Legacy Evidence",
                    identifier="legacy-1",
                    market="US",
                )
            )
            session.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_schema_is_repeatable_and_legacy_tables_are_unchanged(self):
        inspector = inspect(self.engine)
        legacy_columns_before = {
            table: [column["name"] for column in inspector.get_columns(table)]
            for table in Base.metadata.tables
        }

        create_v2_schema(self.engine)
        create_v2_schema(self.engine)

        inspector = inspect(self.engine)
        self.assertTrue(V2_TABLES.issubset(set(inspector.get_table_names())))
        for table, columns_before in legacy_columns_before.items():
            self.assertEqual(
                [column["name"] for column in inspector.get_columns(table)],
                columns_before,
            )
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(TrackedEntity.name)), "Legacy Evidence")

        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
        finally:
            connection.close()

    def test_raw_identity_is_unique_and_numeric_values_keep_precision(self):
        create_v2_schema(self.engine)
        now = datetime.now(timezone.utc)
        source_event_id = make_source_event_id("sec_form4", "accession", "transaction-1")
        payload = {"transactionCode": "P", "shares": "0.123456789012"}

        with Session(self.engine) as session:
            raw_event = RawEvent(
                source="sec_form4",
                source_event_id=source_event_id,
                source_url="https://www.sec.gov/example.xml",
                payload=payload,
                payload_sha256=payload_sha256(payload),
                http_status=200,
                retrieved_at=now,
            )
            session.add(raw_event)
            session.flush()
            session.add(
                NormalizedEventV2(
                    source="sec_form4",
                    source_event_id=source_event_id,
                    event_type="insider_transaction",
                    action="purchase",
                    side="BUY",
                    execution_status="reported",
                    market="US",
                    ticker="TST",
                    quantity=Decimal("0.123456789012"),
                    price=Decimal("25.000000000001"),
                    value=Decimal("3.086419725300"),
                    currency="USD",
                    event_at=now,
                    filed_at=now,
                    observed_at=now,
                    source_url=raw_event.source_url,
                    raw_event_id=raw_event.id,
                    parser_version="form4-v1",
                    quality_status="valid",
                    quality_reasons=[],
                )
            )
            session.commit()

        with Session(self.engine) as session:
            normalized = session.scalar(select(NormalizedEventV2))
            self.assertEqual(normalized.quantity, Decimal("0.123456789012"))
            session.add(
                RawEvent(
                    source="sec_form4",
                    source_event_id=source_event_id,
                    payload=payload,
                    payload_sha256=payload_sha256(payload),
                    retrieved_at=now,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_collector_outcome_enforces_failure_semantics(self):
        create_v2_schema(self.engine)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            session.add(
                CollectorRunV2(
                    collector="sec_form4",
                    started_at=now,
                    status="error",
                    failure_kind=None,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_failure_taxonomy_and_empty_success_are_distinct(self):
        create_v2_schema(self.engine)
        now = datetime.now(timezone.utc)
        failure_kinds = ("auth", "schema", "parser", "source", "persistence", "internal")
        with Session(self.engine) as session:
            session.add(
                CollectorRunV2(
                    collector="sec_form4",
                    started_at=now,
                    finished_at=now,
                    status="empty",
                    records_observed=0,
                )
            )
            session.add_all(
                CollectorRunV2(
                    collector=f"collector_{failure_kind}",
                    started_at=now,
                    finished_at=now,
                    status="error",
                    failure_kind=failure_kind,
                )
                for failure_kind in failure_kinds
            )
            session.add(
                CollectorRunV2(
                    collector="collector_timeout",
                    started_at=now,
                    finished_at=now,
                    status="timeout",
                    failure_kind="timeout",
                )
            )
            session.commit()

            outcomes = {
                (run.status, run.failure_kind)
                for run in session.scalars(select(CollectorRunV2)).all()
            }
            self.assertIn(("empty", None), outcomes)
            self.assertIn(("timeout", "timeout"), outcomes)
            for failure_kind in failure_kinds:
                self.assertIn(("error", failure_kind), outcomes)


if __name__ == "__main__":
    unittest.main()
