import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.sfc import SFC_SHORT_POLICY, ingest_sfc_short_csv
from smartflow.normalizers.sfc import normalize_sfc_short_report
from smartflow.parsers.sfc_short_csv import SFCShortCSVError, parse_sfc_short_csv


FIXTURE = Path(__file__).parent / "fixtures" / "sfc" / "short_positions_20260710_official_excerpt.csv"
SOURCE_URL = "https://www.sfc.hk/official-weekly-report.csv"
OBSERVED_AT = datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc)
PUBLISHED_AT = datetime(2026, 7, 17, 1, 0, tzinfo=timezone.utc)


class SFCShortParserTests(unittest.TestCase):
    def test_official_excerpt_preserves_position_schema(self):
        parsed = parse_sfc_short_csv(FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(parsed["reporting_date"].isoformat(), "2026-07-10")
        self.assertEqual(len(parsed["records"]), 3)
        self.assertEqual(parsed["records"][0]["stock_code"], "00001")
        self.assertEqual(parsed["records"][0]["shares"], Decimal("52469288"))
        self.assertEqual(
            parsed["records"][1]["market_value_hkd"], Decimal("10667932869")
        )
        self.assertEqual(parsed["records"][2]["shares"], Decimal("0"))

    def test_schema_drift_is_not_a_successful_empty_report(self):
        with self.assertRaisesRegex(SFCShortCSVError, "unexpected.*headers"):
            parse_sfc_short_csv("Date,Stock Code,Short Sell Value (HKD)\n10/07/2026,1,10\n")

    def test_mixed_reporting_dates_are_rejected(self):
        content = FIXTURE.read_text(encoding="utf-8").replace(
            "10/07/2026,5", "03/07/2026,5"
        )
        with self.assertRaisesRegex(SFCShortCSVError, "mixed reporting dates"):
            parse_sfc_short_csv(content)


class SFCShortNormalizerTests(unittest.TestCase):
    def test_snapshot_is_short_position_not_sell_trade(self):
        parsed = parse_sfc_short_csv(FIXTURE.read_text(encoding="utf-8"))
        events = normalize_sfc_short_report(
            parsed,
            published_at=PUBLISHED_AT,
            observed_at=OBSERVED_AT,
            source_url=SOURCE_URL,
        )

        event = events[0]
        self.assertEqual(event["event_type"], "aggregated_reportable_short_position")
        self.assertEqual(event["action"], "position_snapshot")
        self.assertEqual(event["side"], "SHORT")
        self.assertNotEqual(event["action"], "sale")
        self.assertIsNone(event["entity_id"])
        self.assertEqual(event["ticker"], "00001.HK")
        self.assertEqual(event["event_at"], datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc))


class SFCShortIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "sfc.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_end_to_end_is_idempotent_and_healthy(self):
        arguments = {
            "csv_content": FIXTURE.read_text(encoding="utf-8"),
            "source_url": SOURCE_URL,
            "published_at": PUBLISHED_AT,
            "observed_at": OBSERVED_AT,
        }
        with Session(self.engine) as session:
            with patch("smartflow.ingestion.sfc._utc_now", return_value=OBSERVED_AT):
                first = ingest_sfc_short_csv(session, **arguments)
                second = ingest_sfc_short_csv(session, **arguments)

            self.assertEqual((first.raw_inserted, first.normalized_inserted), (1, 3))
            self.assertEqual((second.raw_inserted, second.normalized_inserted), (0, 0))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 3)
            self.assertEqual(session.scalar(select(func.count(CollectorRunV2.id))), 2)
            self.assertEqual(session.get(SourceHealth, "sfc_short").state, "healthy")
            self.assertEqual(SFC_SHORT_POLICY.expected_interval_seconds, 604800)

    def test_parser_failure_is_visible_and_degrades_health(self):
        with Session(self.engine) as session:
            with self.assertRaises(SFCShortCSVError):
                ingest_sfc_short_csv(
                    session,
                    csv_content="wrong,headers\n1,2\n",
                    source_url=SOURCE_URL,
                    published_at=PUBLISHED_AT,
                    observed_at=OBSERVED_AT,
                )

            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.get(SourceHealth, "sfc_short").state, "degraded")


if __name__ == "__main__":
    unittest.main()
