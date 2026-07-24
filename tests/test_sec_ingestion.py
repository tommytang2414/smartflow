import tempfile
import unittest
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
from smartflow.ingestion.sec import SECParserError, ingest_form4_xml, ingest_form144_xml


FIXTURES = Path(__file__).parent / "fixtures" / "sec"
OBSERVED_AT = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)
FILED_AT = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)


class SECIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "ingestion.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_transactionless_form4_persists_one_administrative_event_idempotently(self):
        xml = (
            FIXTURES / "form4_administrative_fund_i_official_excerpt.xml"
        ).read_text(encoding="utf-8")
        arguments = {
            "xml_content": xml,
            "accession": "0001461219-26-000003",
            "source_url": "https://www.sec.gov/administrative-form4.xml",
            "filed_at": FILED_AT,
            "observed_at": OBSERVED_AT,
        }
        with Session(self.engine) as session:
            first = ingest_form4_xml(session, **arguments)
            second = ingest_form4_xml(session, **arguments)
            event = session.scalar(select(NormalizedEventV2))

            self.assertEqual((first.raw_inserted, first.normalized_inserted), (1, 1))
            self.assertEqual((second.raw_inserted, second.normalized_inserted), (0, 0))
            self.assertEqual(event.event_type, "form4_administrative_notice")
            self.assertEqual(event.action, "no_reportable_transaction")
            self.assertIsNone(event.side)
            self.assertIsNone(event.quantity)
            self.assertIsNone(event.price)
            self.assertIsNone(event.value)

    def test_form4_end_to_end_and_idempotent_rerun(self):
        xml = (FIXTURES / "form4_non_market_official_excerpt.xml").read_text(encoding="utf-8")
        arguments = {
            "xml_content": xml,
            "accession": "0001140361-26-018962",
            "source_url": "https://www.sec.gov/form4.xml",
            "filed_at": FILED_AT,
            "observed_at": OBSERVED_AT,
        }
        with Session(self.engine) as session:
            first = ingest_form4_xml(session, **arguments)
            second = ingest_form4_xml(session, **arguments)

            self.assertEqual(
                (first.raw_inserted, first.normalized_inserted, first.normalized_observed),
                (1, 4, 4),
            )
            self.assertEqual(
                (second.raw_inserted, second.normalized_inserted, second.normalized_observed),
                (0, 0, 4),
            )
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 4)
            stored_event = session.scalar(select(NormalizedEventV2).limit(1))
            self.assertEqual(len(stored_event.entities), 4)
            self.assertTrue(stored_event.entity_id.startswith("sec_form4_group:"))
            self.assertEqual(session.scalar(select(func.count(CollectorRunV2.id))), 2)
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "healthy")

    def test_malformed_filing_preserves_raw_and_records_parser_failure(self):
        with Session(self.engine) as session:
            with self.assertRaises(SECParserError):
                ingest_form4_xml(
                    session,
                    xml_content="<ownershipDocument>",
                    accession="malformed-accession",
                    source_url="https://www.sec.gov/malformed.xml",
                    filed_at=FILED_AT,
                    observed_at=OBSERVED_AT,
                )

            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 0)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "degraded")

    def test_form144_end_to_end_keeps_proposed_status(self):
        xml = (FIXTURES / "form144_official_excerpt.xml").read_text(encoding="utf-8")
        with Session(self.engine) as session:
            result = ingest_form144_xml(
                session,
                xml_content=xml,
                accession="0001921094-25-001148",
                source_url="https://www.sec.gov/form144.xml",
                filed_at=FILED_AT,
                observed_at=OBSERVED_AT,
                cik_ticker_cache={"1326801": "META"},
            )

            event = session.scalar(select(NormalizedEventV2))
            self.assertEqual(result.normalized_inserted, 1)
            self.assertEqual(event.action, "proposed_sale")
            self.assertEqual(event.side, "SELL")
            self.assertEqual(event.execution_status, "proposed")
            self.assertEqual(session.get(SourceHealth, "sec_form144").state, "healthy")

    def test_normalization_failure_is_schema_failure_and_preserves_raw(self):
        xml = (FIXTURES / "form4_non_market_official_excerpt.xml").read_text(encoding="utf-8")
        with Session(self.engine) as session:
            with patch(
                "smartflow.ingestion.sec.normalize_form4",
                side_effect=ValueError("normalizer contract failed"),
            ):
                with self.assertRaisesRegex(ValueError, "normalizer contract failed"):
                    ingest_form4_xml(
                        session,
                        xml_content=xml,
                        accession="schema-failure-accession",
                        source_url="https://www.sec.gov/schema-failure.xml",
                        filed_at=FILED_AT,
                        observed_at=OBSERVED_AT,
                    )

            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "schema"))


if __name__ == "__main__":
    unittest.main()
