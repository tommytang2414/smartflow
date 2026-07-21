import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import NormalizedEventV2, RawEvent
from smartflow.db.v2_repository import EvidenceConflictError, persist_event_batch
from smartflow.db.v2_schema import create_v2_schema
from smartflow.events import payload_sha256


class V2PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "v2.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def raw_event(self, payload=None):
        payload = payload or {"filing": "original"}
        return {
            "source": "sec_form4",
            "source_event_id": "accession-1",
            "source_url": "https://www.sec.gov/filing.xml",
            "payload": payload,
            "payload_sha256": payload_sha256(payload),
            "http_status": 200,
            "retrieved_at": self.now,
        }

    def normalized_event(self, suffix="1", quality_status="valid"):
        return {
            "source": "sec_form4",
            "source_event_id": f"transaction-{suffix}",
            "event_type": "form4_transaction",
            "action": "purchase",
            "side": "BUY",
            "execution_status": "reported",
            "market": "US",
            "security_id": "1",
            "ticker": "TST",
            "entity_id": "2",
            "entity_name": "Owner",
            "quantity": 10,
            "price": 25,
            "value": 250,
            "currency": "USD",
            "event_at": self.now,
            "filed_at": self.now,
            "observed_at": self.now,
            "source_url": "https://www.sec.gov/filing.xml",
            "parser_version": "sec-form4-v1",
            "quality_status": quality_status,
            "quality_reasons": [],
        }

    def test_batch_is_atomic_and_idempotent(self):
        with Session(self.engine) as session:
            first = persist_event_batch(
                session,
                raw_event=self.raw_event(),
                normalized_events=[self.normalized_event("1"), self.normalized_event("2")],
            )
            second = persist_event_batch(
                session,
                raw_event=self.raw_event(),
                normalized_events=[self.normalized_event("1"), self.normalized_event("2")],
            )

            self.assertEqual((first.raw_inserted, first.normalized_inserted), (1, 2))
            self.assertEqual((second.raw_inserted, second.normalized_inserted), (0, 0))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 2)

    def test_changed_raw_payload_is_rejected_not_overwritten(self):
        with Session(self.engine) as session:
            persist_event_batch(
                session,
                raw_event=self.raw_event(),
                normalized_events=[self.normalized_event()],
            )
            with self.assertRaises(EvidenceConflictError):
                persist_event_batch(
                    session,
                    raw_event=self.raw_event({"filing": "changed"}),
                    normalized_events=[self.normalized_event()],
                )

            stored = session.scalar(select(RawEvent))
            self.assertEqual(stored.payload, {"filing": "original"})

    def test_invalid_normalized_event_rolls_back_new_raw_event(self):
        with Session(self.engine) as session:
            with self.assertRaises(IntegrityError):
                persist_event_batch(
                    session,
                    raw_event=self.raw_event(),
                    normalized_events=[self.normalized_event(quality_status="not-valid")],
                )

            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 0)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 0)

    def test_normalized_identity_cannot_move_to_different_raw_evidence(self):
        with Session(self.engine) as session:
            persist_event_batch(
                session,
                raw_event=self.raw_event(),
                normalized_events=[self.normalized_event()],
            )
            second_raw = self.raw_event({"filing": "second"})
            second_raw["source_event_id"] = "accession-2"

            with self.assertRaises(EvidenceConflictError):
                persist_event_batch(
                    session,
                    raw_event=second_raw,
                    normalized_events=[self.normalized_event()],
                )

            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)


if __name__ == "__main__":
    unittest.main()
