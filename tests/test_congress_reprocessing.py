import base64
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.congress_reprocessing import reprocess_house_ptr
from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent
from smartflow.db.v2_repository import EvidenceConflictError
from smartflow.db.v2_schema import create_v2_schema
from smartflow.events import payload_sha256
from smartflow.ingestion.congress import ingest_house_ptr_pdf
from smartflow.parsers.congress_house import HouseDisclosureError


OBSERVED_AT = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
PDF_BYTES = b"%PDF-1.7\npreserved House fixture\n%%EOF"


class CongressReprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "congress-reprocess.db"
        )
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        create_v2_schema(self.engine)
        self.report = {
            "chamber": "house",
            "doc_id": "20034201",
            "member_name": "Alex Example",
            "state_district": "XX00",
            "filing_date": OBSERVED_AT.date(),
            "source_url": (
                "https://disclosures-clerk.house.gov/public_disc/"
                "ptr-pdfs/2026/20034201.pdf"
            ),
        }
        self.parsed = {
            **self.report,
            "document_status": "parsed",
            "transactions": [
                {
                    "row_number": 1,
                    "page_number": 1,
                    "owner_code": None,
                    "asset": "Example (EXM) [ST]",
                    "asset_type": "ST",
                    "ticker": "EXM",
                    "transaction_code": "S",
                    "transaction_type": "S",
                    "transaction_date": OBSERVED_AT.date(),
                    "notification_date": OBSERVED_AT.date(),
                    "amount_lower": 1001,
                    "amount_upper": 15000,
                    "amount_is_range": True,
                    "amount_note": "@ $470.985/share",
                }
            ],
        }
        def reject(content, report):
            raise HouseDisclosureError("fixture failure")

        with Session(self.engine) as session:
            with self.assertRaisesRegex(HouseDisclosureError, "fixture failure"):
                ingest_house_ptr_pdf(
                    session,
                    pdf_content=PDF_BYTES,
                    report=self.report,
                    observed_at=OBSERVED_AT,
                    extractor=reject,
                )
            raw = session.scalar(select(RawEvent))
            self.expected_sha256 = raw.payload_sha256

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_hash_pinned_reprocess_uses_stored_pdf_and_is_idempotent(self):
        extractor = lambda content, report: self.parsed
        with Session(self.engine) as session:
            first = reprocess_house_ptr(
                session,
                doc_id="20034201",
                expected_sha256=self.expected_sha256,
                report=self.report,
                extractor=extractor,
            )
            second = reprocess_house_ptr(
                session,
                doc_id="20034201",
                expected_sha256=self.expected_sha256,
                report=self.report,
                extractor=extractor,
            )

            self.assertEqual(first.normalized_inserted, 1)
            self.assertEqual(second.normalized_inserted, 0)
            self.assertEqual(
                session.scalar(select(func.count(RawEvent.id))),
                1,
            )
            self.assertEqual(
                session.scalar(select(func.count(NormalizedEventV2.id))),
                1,
            )
            self.assertEqual(
                session.scalar(select(func.count(CollectorRunV2.id))),
                1,
            )
            raw = session.scalar(select(RawEvent))
            self.assertEqual(base64.b64decode(raw.payload["body_base64"]), PDF_BYTES)
            self.assertEqual(
                raw.payload["pdf_sha256"],
                hashlib.sha256(PDF_BYTES).hexdigest(),
            )
            event = session.scalar(select(NormalizedEventV2))
            self.assertEqual(event.parser_version, "congress-house-ptr-v4")
            self.assertEqual(
                event.attributes["amount_note"],
                "@ $470.985/share",
            )

    def test_hash_mismatch_refuses_reprocessing(self):
        with Session(self.engine) as session:
            with self.assertRaises(EvidenceConflictError):
                reprocess_house_ptr(
                    session,
                    doc_id="20034201",
                    expected_sha256="0" * 64,
                    report=self.report,
                    extractor=lambda content, report: self.parsed,
                )


if __name__ == "__main__":
    unittest.main()
