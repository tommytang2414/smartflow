import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_repository import EvidenceConflictError
from smartflow.db.v2_schema import create_v2_schema
from smartflow.events import payload_sha256
from smartflow.ingestion.sec import SECSchemaError
from smartflow.sec_reprocessing import reprocess_transactionless_form4


FIXTURES = Path(__file__).parent / "fixtures" / "sec"
OBSERVED_AT = datetime(2026, 7, 24, 14, 40, tzinfo=timezone.utc)
ACCESSION = "0001461219-26-000003"


class SECForm4ReprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "reprocess.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def add_raw_event(self, fixture: str) -> str:
        xml = (FIXTURES / fixture).read_text(encoding="utf-8")
        payload = {"content_type": "application/xml", "xml": xml}
        digest = payload_sha256(payload)
        with Session(self.engine) as session:
            session.add(
                RawEvent(
                    source="sec_form4",
                    source_event_id=ACCESSION,
                    source_url="https://www.sec.gov/Archives/test/primary_doc.xml",
                    payload=payload,
                    payload_sha256=digest,
                    http_status=200,
                    retrieved_at=OBSERVED_AT,
                )
            )
            session.commit()
        return digest

    def test_reprocesses_exact_raw_evidence_without_rewriting_operational_history(self):
        digest = self.add_raw_event("form4_administrative_fund_i_official_excerpt.xml")

        with Session(self.engine) as session:
            first = reprocess_transactionless_form4(
                session,
                accession=ACCESSION,
                expected_sha256=digest,
            )
            second = reprocess_transactionless_form4(
                session,
                accession=ACCESSION,
                expected_sha256=digest,
            )

            event = session.scalar(select(NormalizedEventV2))
            self.assertEqual((first.normalized_inserted, second.normalized_inserted), (1, 0))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 1)
            self.assertEqual(event.event_type, "form4_administrative_notice")
            self.assertEqual(event.parser_version, "sec-form4-v4")
            self.assertIsNone(event.side)
            self.assertIsNone(event.quantity)
            self.assertEqual(session.scalar(select(func.count(CollectorRunV2.id))), 0)
            self.assertEqual(session.scalar(select(func.count(SourceHealth.source))), 0)

    def test_hash_mismatch_fails_without_normalized_write(self):
        self.add_raw_event("form4_administrative_fund_i_official_excerpt.xml")

        with Session(self.engine) as session:
            with self.assertRaises(EvidenceConflictError):
                reprocess_transactionless_form4(
                    session,
                    accession=ACCESSION,
                    expected_sha256="0" * 64,
                )
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 0)

    def test_rejects_transaction_filing_even_with_matching_hash(self):
        digest = self.add_raw_event("form4_purchase_official_excerpt.xml")

        with Session(self.engine) as session:
            with self.assertRaises(SECSchemaError):
                reprocess_transactionless_form4(
                    session,
                    accession=ACCESSION,
                    expected_sha256=digest,
                )
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 0)


if __name__ == "__main__":
    unittest.main()
