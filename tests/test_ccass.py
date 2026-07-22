import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.ccass_legacy_audit import audit_ccass_legacy
from smartflow.ccass_reconciliation import reconcile_ccass_snapshots
from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.ccass import ingest_ccass_snapshot
from smartflow.normalizers.ccass import normalize_ccass_snapshot
from smartflow.parsers.ccass import CCASSSnapshotError, parse_ccass_snapshot


FIXTURES = Path(__file__).parent / "fixtures" / "ccass"
OBSERVED_AT = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
SOURCE_URL = "approved://ccass/snapshot/00700/2026-07-20"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CCASSContractTests(unittest.TestCase):
    def test_snapshot_parser_preserves_exact_custody_balances(self):
        parsed = parse_ccass_snapshot(fixture("synthetic_snapshot_20260720.json"))

        self.assertEqual(parsed["stock_code"], "00700")
        self.assertEqual(parsed["holding_date"].isoformat(), "2026-07-20")
        self.assertEqual(parsed["holdings"][0]["shares"], Decimal("4000"))
        self.assertEqual(
            parsed["holdings"][0]["pct_of_issued_shares"], Decimal("4.00")
        )

    def test_duplicate_participant_is_schema_failure(self):
        payload = fixture("synthetic_snapshot_20260720.json")
        payload["holdings"].append(dict(payload["holdings"][0]))
        with self.assertRaisesRegex(CCASSSnapshotError, "duplicate participant"):
            parse_ccass_snapshot(payload)

    def test_normalizer_never_infers_trade_direction_or_beneficial_owner(self):
        parsed = parse_ccass_snapshot(fixture("synthetic_snapshot_20260720.json"))
        events = normalize_ccass_snapshot(
            parsed,
            observed_at=OBSERVED_AT,
            source_url=SOURCE_URL,
        )

        self.assertEqual(len(events), 4)
        self.assertTrue(all(event["side"] is None for event in events))
        self.assertNotIn("BUY", {event["action"] for event in events})
        self.assertNotIn("SELL", {event["action"] for event in events})
        holding = events[0]
        self.assertEqual(holding["action"], "custody_snapshot")
        self.assertIn("not_beneficial_ownership", holding["attributes"]["interpretation"])
        concentration = events[-1]
        self.assertEqual(concentration["action"], "concentration_measurement")
        self.assertEqual(
            Decimal(concentration["attributes"]["participant_hhi"]),
            Decimal("0.345"),
        )

    def test_reconciliation_is_balance_change_not_trade(self):
        previous = parse_ccass_snapshot(fixture("synthetic_snapshot_20260720.json"))
        current = parse_ccass_snapshot(fixture("synthetic_snapshot_20260721.json"))
        _, _, changes = reconcile_ccass_snapshots(previous, current)
        by_id = {change.participant_id: change for change in changes}

        self.assertEqual(by_id["C00001"].shares_change, Decimal("-200"))
        self.assertEqual(by_id["B00001"].shares_change, Decimal("200"))
        self.assertEqual(by_id["B00002"].reporting_state, "not_in_current_snapshot")
        self.assertIsNone(by_id["B00002"].shares_change)
        self.assertEqual(by_id["B00003"].reporting_state, "newly_present")
        self.assertTrue(
            all("not_trade_direction" in change.interpretation for change in changes)
        )


class CCASSIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "ccass.db"
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_ingestion_is_idempotent_and_attributes_are_queryable(self):
        arguments = {
            "payload": fixture("synthetic_snapshot_20260720.json"),
            "source_url": SOURCE_URL,
            "observed_at": OBSERVED_AT,
        }
        with Session(self.engine) as session:
            with patch("smartflow.ingestion.ccass._utc_now", return_value=OBSERVED_AT):
                first = ingest_ccass_snapshot(session, **arguments)
                second = ingest_ccass_snapshot(session, **arguments)

            self.assertEqual((first.raw_inserted, first.normalized_inserted), (1, 4))
            self.assertEqual((second.raw_inserted, second.normalized_inserted), (0, 0))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 4)
            event = session.scalar(
                select(NormalizedEventV2).where(
                    NormalizedEventV2.event_type == "ccass_participant_holding_snapshot"
                )
            )
            self.assertEqual(event.attributes["pct_of_issued_shares"], "4.00")
            self.assertIsNone(event.side)
            self.assertEqual(session.get(SourceHealth, "hkex_ccass").state, "healthy")

    def test_malformed_snapshot_preserves_raw_and_degrades_health(self):
        with Session(self.engine) as session:
            with self.assertRaises(CCASSSnapshotError):
                ingest_ccass_snapshot(
                    session,
                    payload={"stock_code": "700", "holding_date": "bad", "holdings": []},
                    source_url=SOURCE_URL,
                    observed_at=OBSERVED_AT,
                )
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.get(SourceHealth, "hkex_ccass").state, "degraded")


class CCASSLegacyAuditTests(unittest.TestCase):
    def test_all_legacy_directional_signals_are_classified_unsupported(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE ccass_holdings (holding_date DATE);"
                "CREATE TABLE ccass_metrics (metric_date DATE, concentration_flag TEXT);"
                "CREATE TABLE smart_money_signals (source TEXT, direction TEXT);"
                "INSERT INTO ccass_holdings VALUES ('2026-07-20');"
                "INSERT INTO ccass_metrics VALUES ('2026-07-20', 'RED');"
                "INSERT INTO smart_money_signals VALUES ('hkex_ccass', 'SELL');"
            )
            connection.commit()
            connection.close()

            result = audit_ccass_legacy(database)
            self.assertEqual(result["legacy_directional_signals"], 1)
            self.assertEqual(result["supported_directional_signals"], 0)
            self.assertEqual(result["status"], "directional_semantics_unsupported")


if __name__ == "__main__":
    unittest.main()
