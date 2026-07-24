import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda"))

from beta_report import BetaReportError, build_beta_report, build_pause_notice


def load_publisher_module():
    path = ROOT / "ops" / "publish_sec_beta_snapshot.py"
    spec = importlib.util.spec_from_file_location("publish_sec_beta_snapshot", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PUBLISHER = load_publisher_module()


def load_lambda_module():
    os.environ.setdefault("S3_BUCKET", "smartflow-tommy-db")
    os.environ.setdefault("SES_FROM", "sender@example.com")
    os.environ.setdefault("EMAIL_TO", "recipient@example.com")
    path = ROOT / "lambda" / "lambda_function.py"
    spec = importlib.util.spec_from_file_location("smartflow_lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


LAMBDA = load_lambda_module()


def create_beta_database(path: Path, snapshot_at: datetime) -> None:
    def timestamp(value: datetime) -> str:
        return value.isoformat(sep=" ")

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE raw_events (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL
            );
            CREATE TABLE collector_runs_v2 (
                id INTEGER PRIMARY KEY,
                collector TEXT NOT NULL
            );
            CREATE TABLE source_health (
                source TEXT PRIMARY KEY,
                expected_interval_seconds INTEGER NOT NULL,
                freshness_sla_seconds INTEGER NOT NULL,
                state TEXT NOT NULL,
                reason TEXT NOT NULL,
                last_run_status TEXT,
                last_failure_kind TEXT,
                last_run_at TEXT,
                last_success_at TEXT,
                last_event_at TEXT,
                checked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE normalized_events_v2 (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                source_event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT,
                side TEXT,
                execution_status TEXT,
                ticker TEXT,
                entity_name TEXT,
                quantity NUMERIC,
                price NUMERIC,
                value NUMERIC,
                currency TEXT,
                event_at TEXT,
                filed_at TEXT,
                observed_at TEXT NOT NULL,
                source_url TEXT,
                raw_event_id INTEGER NOT NULL REFERENCES raw_events(id),
                parser_version TEXT NOT NULL,
                quality_status TEXT NOT NULL,
                quality_reasons TEXT NOT NULL
            );
            """
        )
        naive_snapshot = snapshot_at.astimezone(timezone.utc).replace(tzinfo=None)
        health_rows = [
            (
                "sec_form4",
                300,
                900,
                "healthy",
                "recent_success",
                "success",
                None,
                timestamp(naive_snapshot - timedelta(minutes=2)),
                timestamp(naive_snapshot - timedelta(minutes=2)),
                timestamp(naive_snapshot),
                timestamp(naive_snapshot - timedelta(minutes=2)),
                timestamp(naive_snapshot - timedelta(minutes=2)),
            ),
            (
                "sec_form144",
                3600,
                10800,
                "healthy",
                "recent_success",
                "empty",
                None,
                timestamp(naive_snapshot - timedelta(minutes=55)),
                timestamp(naive_snapshot - timedelta(minutes=55)),
                timestamp(naive_snapshot),
                timestamp(naive_snapshot - timedelta(minutes=55)),
                timestamp(naive_snapshot - timedelta(minutes=55)),
            ),
        ]
        connection.executemany(
            "INSERT INTO source_health VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            health_rows,
        )
        connection.executemany(
            "INSERT INTO raw_events (id, source) VALUES (?, ?)",
            [(1, "sec_form4"), (2, "sec_form4"), (3, "sec_form144"), (4, "sec_form4")],
        )
        base = timestamp(naive_snapshot - timedelta(hours=1))
        event_rows = [
            (
                1,
                "sec_form4",
                "form4-purchase",
                "form4_transaction",
                "purchase",
                "BUY",
                "reported",
                "AAA",
                "Director A",
                100,
                10,
                1000,
                "USD",
                base,
                base,
                base,
                "https://www.sec.gov/Archives/edgar/data/1/form4.xml",
                1,
                "sec-form4-v4",
                "valid",
                "[]",
            ),
            (
                2,
                "sec_form4",
                "form4-sale",
                "form4_transaction",
                "sale",
                "SELL",
                "reported",
                "BBB",
                "Officer B",
                50,
                20,
                1000,
                "USD",
                base,
                base,
                base,
                "https://www.sec.gov/Archives/edgar/data/2/form4.xml",
                2,
                "sec-form4-v4",
                "valid",
                "[]",
            ),
            (
                3,
                "sec_form144",
                "form144-proposed",
                "form144_notice",
                "proposed_sale",
                "SELL",
                "proposed",
                "CCC",
                "Officer C",
                25,
                None,
                750,
                "USD",
                base,
                base,
                base,
                "https://www.sec.gov/Archives/edgar/data/3/primary_doc.xml",
                3,
                "sec-form144-v1",
                "valid",
                "[]",
            ),
            (
                4,
                "sec_form4",
                "form4-warning",
                "form4_transaction",
                "other",
                None,
                "reported",
                "DDD",
                "Officer D",
                1,
                None,
                None,
                "USD",
                base,
                base,
                base,
                "https://www.sec.gov/Archives/edgar/data/4/form4.xml",
                4,
                "sec-form4-v4",
                "warning",
                '["unsupported_transaction_code"]',
            ),
        ]
        connection.executemany(
            """
            INSERT INTO normalized_events_v2 (
                id, source, source_event_id, event_type, action, side,
                execution_status, ticker, entity_name, quantity, price, value,
                currency, event_at, filed_at, observed_at, source_url,
                raw_event_id, parser_version, quality_status, quality_reasons
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            event_rows,
        )
        connection.commit()
    finally:
        connection.close()


class SecBetaReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database = self.directory / "smartflow-v2-shadow.db"
        self.snapshot_at = datetime(2026, 7, 24, 23, 55, tzinfo=timezone.utc)
        create_beta_database(self.database, self.snapshot_at)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def build(self):
        return build_beta_report(
            self.database,
            snapshot_at=self.snapshot_at,
            now=self.snapshot_at + timedelta(minutes=5),
        )

    def test_builds_deterministic_non_directional_report(self):
        report = self.build()

        self.assertEqual(report.report_date, "2026-07-25")
        self.assertIn("INFORMATIONAL ONLY — NOT INVESTMENT ADVICE", report.body)
        self.assertIn("[reported purchase] AAA", report.body)
        self.assertIn("[reported sale] BBB", report.body)
        self.assertIn("[proposed sale — not executed] CCC", report.body)
        self.assertIn("Warning/invalid events excluded from detail: 1", report.body)
        self.assertIn("Events from superseded parser versions excluded: 0", report.body)
        self.assertNotIn("form4-warning", report.body)
        self.assertNotIn("LONG", report.body)
        self.assertNotIn("SHORT", report.body)
        self.assertNotIn("WATCH", report.body)

    def test_superseded_parser_events_are_excluded(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE normalized_events_v2 SET parser_version = 'sec-form4-v3' "
                "WHERE id = 1"
            )
            connection.commit()
        finally:
            connection.close()

        report = self.build()

        self.assertNotIn("[reported purchase] AAA", report.body)
        self.assertIn("Events from superseded parser versions excluded: 1", report.body)

    def test_unhealthy_source_pauses_report(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE source_health SET state = 'degraded' WHERE source = 'sec_form4'"
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(BetaReportError, "SOURCE_HEALTH_UNSAFE"):
            self.build()

    def test_stale_snapshot_pauses_report(self):
        with self.assertRaisesRegex(BetaReportError, "SNAPSHOT_STALE"):
            build_beta_report(
                self.database,
                snapshot_at=self.snapshot_at,
                now=self.snapshot_at + timedelta(hours=27),
            )

    def test_non_sec_url_pauses_report(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE normalized_events_v2 SET source_url = ? WHERE id = 1",
                ("https://example.com/Archives/form4.xml",),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(BetaReportError, "SOURCE_URL_INVALID"):
            self.build()

    def test_pause_notice_does_not_echo_unknown_error(self):
        notice = build_pause_notice("secret raw exception")
        self.assertIn("INTERNAL_VALIDATION_ERROR", notice)
        self.assertNotIn("secret raw exception", notice)


class SecBetaLambdaTests(unittest.TestCase):
    def setUp(self):
        self.previous_mode = os.environ.get("REPORT_MODE")

    def tearDown(self):
        if self.previous_mode is None:
            os.environ.pop("REPORT_MODE", None)
        else:
            os.environ["REPORT_MODE"] = self.previous_mode

    @patch.object(LAMBDA, "_download_beta_snapshot")
    @patch.object(LAMBDA, "send_email")
    def test_containment_default_does_not_read_beta_snapshot(self, send_email, download):
        os.environ.pop("REPORT_MODE", None)

        result = LAMBDA.handler({}, None)

        self.assertEqual(result["status"], "containment")
        download.assert_not_called()
        send_email.assert_called_once()

    @patch.object(LAMBDA, "send_email")
    def test_beta_health_failure_sends_paused_notice(self, send_email):
        os.environ["REPORT_MODE"] = "informational_beta"
        with patch.object(
            LAMBDA,
            "_download_beta_snapshot",
            side_effect=BetaReportError("SOURCE_HEALTH_UNSAFE"),
        ):
            result = LAMBDA.handler({}, None)

        self.assertEqual(result["status"], "beta_paused")
        self.assertEqual(result["reason"], "SOURCE_HEALTH_UNSAFE")
        self.assertIn("BETA PAUSED", send_email.call_args.args[1])

    def test_unsupported_mode_fails_closed(self):
        os.environ["REPORT_MODE"] = "legacy"

        with self.assertRaisesRegex(ValueError, "Unsupported REPORT_MODE"):
            LAMBDA.handler({}, None)


class SecBetaPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database = self.directory / "smartflow-v2-shadow.db"
        self.snapshot_at = datetime.now(timezone.utc)
        create_beta_database(self.database, self.snapshot_at)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @patch.object(PUBLISHER.subprocess, "run")
    def test_publishes_verified_snapshot_to_exact_key(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"VersionId": "v1", "ETag": '"etag"'}),
            stderr="",
        )

        result = PUBLISHER.publish_snapshot(self.database)

        self.assertEqual(result["status"], "published")
        self.assertEqual(result["key"], "beta/sec-v2-shadow.db")
        command = run.call_args.args[0]
        self.assertEqual(command[0:3], ["aws", "s3api", "put-object"])
        self.assertIn("beta/sec-v2-shadow.db", command)
        self.assertIn("AES256", command)

    def test_refuses_legacy_database_name(self):
        legacy = self.directory / "smartflow.db"
        legacy.write_bytes(self.database.read_bytes())

        with self.assertRaisesRegex(ValueError, "refusing legacy"):
            PUBLISHER.publish_snapshot(legacy)

    def test_refuses_unapproved_destination(self):
        with self.assertRaisesRegex(ValueError, "unapproved S3 destination"):
            PUBLISHER.publish_snapshot(self.database, key="smartflow.db")


if __name__ == "__main__":
    unittest.main()
