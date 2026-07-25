import csv
import importlib.util
import io
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
from owner_brief import (
    M3OutputError,
    OwnerBriefError,
    build_decision_pack,
    build_deep_dive_csv,
    build_m3_fact_pack,
    deterministic_narrative,
    pack_sha256,
    render_owner_email,
    validate_decision_pack,
    validate_m3_response,
)


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
                source TEXT NOT NULL,
                source_event_id TEXT NOT NULL,
                source_url TEXT,
                payload TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                http_status INTEGER,
                retrieved_at TEXT NOT NULL,
                created_at TEXT NOT NULL
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
        base = timestamp(naive_snapshot - timedelta(hours=1))
        raw_rows = [
            (
                index,
                source,
                accession,
                url,
                json.dumps({"xml": f"<ownershipDocument>{accession}</ownershipDocument>"}),
                f"{index:064x}",
                200,
                base,
                base,
            )
            for index, source, accession, url in [
                (
                    1,
                    "sec_form4",
                    "0000000001-26-000001",
                    "https://www.sec.gov/Archives/edgar/data/1/form4.xml",
                ),
                (
                    2,
                    "sec_form4",
                    "0000000002-26-000002",
                    "https://www.sec.gov/Archives/edgar/data/2/form4.xml",
                ),
                (
                    3,
                    "sec_form144",
                    "0000000003-26-000003",
                    "https://www.sec.gov/Archives/edgar/data/3/primary_doc.xml",
                ),
                (
                    4,
                    "sec_form4",
                    "0000000004-26-000004",
                    "https://www.sec.gov/Archives/edgar/data/4/form4.xml",
                ),
            ]
        ]
        connection.executemany(
            "INSERT INTO raw_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            raw_rows,
        )
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


class OwnerBriefContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database = self.directory / "smartflow-v2-shadow.db"
        self.snapshot_at = datetime(2026, 7, 24, 23, 55, tzinfo=timezone.utc)
        self.snapshot_hash = "a" * 64
        create_beta_database(self.database, self.snapshot_at)
        self.payload = build_decision_pack(
            self.database,
            snapshot_at=self.snapshot_at,
            generated_at=self.snapshot_at,
            snapshot_sha256=self.snapshot_hash,
        )
        self.metadata = {
            "decision-pack-sha256": pack_sha256(self.payload),
            "snapshot-sha256": self.snapshot_hash,
        }
        self.pack = validate_decision_pack(
            self.payload,
            metadata=self.metadata,
            object_last_modified=self.snapshot_at,
            now=self.snapshot_at + timedelta(minutes=5),
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_pack_has_deterministic_result_and_no_raw_payload(self):
        self.assertEqual(self.pack["summary"]["result"], "MIXED")
        self.assertEqual(self.pack["summary"]["business_action"], "MANUAL_REVIEW")
        self.assertEqual(len(self.pack["events"]), 3)
        self.assertLess(len(self.payload), 5 * 1024 * 1024)
        self.assertNotIn(b"ownershipDocument", self.payload)
        self.assertNotIn(b"raw_xml", self.payload.lower())

    def test_same_filing_transactions_are_aggregated_for_research_items(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                """
                UPDATE normalized_events_v2
                SET raw_event_id = 1, action = 'purchase', side = 'BUY',
                    ticker = 'AAA'
                WHERE id = 2
                """
            )
            connection.commit()
        finally:
            connection.close()
        payload = build_decision_pack(
            self.database,
            snapshot_at=self.snapshot_at,
            generated_at=self.snapshot_at,
            snapshot_sha256=self.snapshot_hash,
        )
        pack = json.loads(payload)

        purchase = next(
            row
            for row in pack["evidence"]
            if row["accession"] == "0000000001-26-000001"
            and row["action"] == "purchase"
        )
        self.assertEqual(purchase["transaction_count"], 2)
        self.assertEqual(pack["summary"]["result"], "PURCHASE_HEAVY")

    def test_pack_hash_and_freshness_fail_closed(self):
        with self.assertRaisesRegex(OwnerBriefError, "PACK_HASH_MISMATCH"):
            validate_decision_pack(
                self.payload + b" ",
                metadata=self.metadata,
                object_last_modified=self.snapshot_at,
                now=self.snapshot_at,
            )
        with self.assertRaisesRegex(OwnerBriefError, "PACK_STALE"):
            validate_decision_pack(
                self.payload,
                metadata=self.metadata,
                object_last_modified=self.snapshot_at,
                now=self.snapshot_at + timedelta(hours=3),
            )

    def test_pack_recomputes_result_and_evidence_after_valid_hash(self):
        tampered = json.loads(self.payload)
        tampered["summary"]["result"] = "PURCHASE_HEAVY"
        tampered_payload = json.dumps(
            tampered,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        metadata = {
            **self.metadata,
            "decision-pack-sha256": pack_sha256(tampered_payload),
        }
        with self.assertRaisesRegex(OwnerBriefError, "PACK_DERIVATION_MISMATCH"):
            validate_decision_pack(
                tampered_payload,
                metadata=metadata,
                object_last_modified=self.snapshot_at,
                now=self.snapshot_at,
            )

        tampered = json.loads(self.payload)
        tampered["evidence"][0]["disclosed_value"] = "999999"
        tampered_payload = json.dumps(
            tampered,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        metadata["decision-pack-sha256"] = pack_sha256(tampered_payload)
        with self.assertRaisesRegex(OwnerBriefError, "PACK_EVIDENCE_MISMATCH"):
            validate_decision_pack(
                tampered_payload,
                metadata=metadata,
                object_last_modified=self.snapshot_at,
                now=self.snapshot_at,
            )

    def test_m3_fact_pack_excludes_names_urls_and_raw_xml(self):
        fact_pack = json.dumps(
            build_m3_fact_pack(self.pack),
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("Director A", fact_pack)
        self.assertNotIn("Officer B", fact_pack)
        self.assertNotIn("https://", fact_pack)
        self.assertNotIn("ownershipDocument", fact_pack)

    def _m3_response(self, output: dict, *, content_prefix: str = "") -> dict:
        return {
            "model": "MiniMax-M3",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": content_prefix
                        + json.dumps(output, ensure_ascii=False),
                    },
                }
            ],
        }

    def _valid_output(self) -> dict:
        return {
            "headline": "申報方向未形成一致結論",
            "summary": "披露資料方向混合，需由 Business Owner 人手覆核。",
            "risk_note": "Form 144 只屬 proposed，並非已完成交易。",
            "result": "MIXED",
            "business_action": "MANUAL_REVIEW",
            "evidence_ids": ["E001"],
        }

    def test_valid_m3_output_is_accepted(self):
        output = validate_m3_response(
            self._m3_response(self._valid_output()),
            pack=self.pack,
            expected_model="MiniMax-M3",
        )
        self.assertEqual(output["result"], "MIXED")

    def test_m3_timeout_uses_deterministic_fallback(self):
        with patch.object(LAMBDA, "_call_m3", side_effect=TimeoutError):
            narrative, ai_used = LAMBDA._generate_narrative(self.pack)

        self.assertFalse(ai_used)
        self.assertEqual(narrative["result"], "MIXED")
        self.assertEqual(narrative["business_action"], "MANUAL_REVIEW")

    def test_valid_m3_response_is_used(self):
        with patch.object(
            LAMBDA,
            "_call_m3",
            return_value=self._m3_response(self._valid_output()),
        ):
            narrative, ai_used = LAMBDA._generate_narrative(self.pack)

        self.assertTrue(ai_used)
        self.assertEqual(narrative["headline"], "申報方向未形成一致結論")

    def test_m3_invented_number_trade_word_and_execution_claim_are_rejected(self):
        invented = self._valid_output()
        invented["summary"] = "資料顯示 999 宗 filing。"
        with self.assertRaisesRegex(M3OutputError, "M3_NUMBER_INVENTED"):
            validate_m3_response(
                self._m3_response(invented),
                pack=self.pack,
                expected_model="MiniMax-M3",
            )

        trade_word = self._valid_output()
        trade_word["summary"] = "應該 BUY。"
        with self.assertRaisesRegex(M3OutputError, "M3_TRADE_INSTRUCTION"):
            validate_m3_response(
                self._m3_response(trade_word),
                pack=self.pack,
                expected_model="MiniMax-M3",
            )

        executed = self._valid_output()
        executed["risk_note"] = "Form 144 已完成交易。"
        with self.assertRaisesRegex(M3OutputError, "M3_FORM144_EXECUTION_CLAIM"):
            validate_m3_response(
                self._m3_response(executed),
                pack=self.pack,
                expected_model="MiniMax-M3",
            )

    def test_malformed_thinking_is_rejected(self):
        with self.assertRaisesRegex(M3OutputError, "M3_REASONING_LEAK"):
            validate_m3_response(
                self._m3_response(
                    self._valid_output(),
                    content_prefix="<think>private reasoning",
                ),
                pack=self.pack,
                expected_model="MiniMax-M3",
            )

    def test_csv_contains_all_rows_and_blocks_formula_injection(self):
        self.pack["events"][0]["entity_name"] = "=HYPERLINK(\"bad\")"
        payload = build_deep_dive_csv(self.pack)
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(payload[3:].decode("utf-8"))))
        self.assertEqual(len(rows), len(self.pack["events"]))
        self.assertTrue(rows[0]["entity_name"].startswith("'="))
        self.assertNotIn("ownershipDocument", payload.decode("utf-8"))

    def test_deterministic_fallback_email_is_short_and_labelled(self):
        narrative = deterministic_narrative(self.pack)
        subject, body = render_owner_email(
            self.pack,
            narrative,
            ai_used=False,
        )
        self.assertIn("[DETERMINISTIC FALLBACK]", subject)
        self.assertIn("RESULT: MIXED", body)
        self.assertIn("BUSINESS ACTION: MANUAL_REVIEW", body)
        self.assertLess(len(body), 5_000)


class SecBetaLambdaTests(unittest.TestCase):
    def setUp(self):
        self.previous_mode = os.environ.get("REPORT_MODE")

    def tearDown(self):
        if self.previous_mode is None:
            os.environ.pop("REPORT_MODE", None)
        else:
            os.environ["REPORT_MODE"] = self.previous_mode

    @patch.object(LAMBDA, "_download_decision_pack")
    @patch.object(LAMBDA, "send_email")
    def test_containment_default_does_not_read_decision_pack(self, send_email, download):
        os.environ.pop("REPORT_MODE", None)

        result = LAMBDA.handler({}, None)

        self.assertEqual(result["status"], "containment")
        download.assert_not_called()
        send_email.assert_called_once()

    @patch.object(LAMBDA, "_generate_narrative")
    @patch.object(LAMBDA, "send_email")
    def test_data_failure_sends_paused_notice_without_calling_m3(
        self,
        send_email,
        generate,
    ):
        os.environ["REPORT_MODE"] = "informational_beta"
        with patch.object(
            LAMBDA,
            "_download_decision_pack",
            side_effect=OwnerBriefError("SOURCE_HEALTH_UNSAFE"),
        ):
            result = LAMBDA.handler({}, None)

        self.assertEqual(result["status"], "beta_paused")
        self.assertEqual(result["reason"], "SOURCE_HEALTH_UNSAFE")
        self.assertIn("BETA PAUSED", send_email.call_args.args[1])
        generate.assert_not_called()

    def test_unsupported_mode_fails_closed(self):
        os.environ["REPORT_MODE"] = "legacy"

        with self.assertRaisesRegex(ValueError, "Unsupported REPORT_MODE"):
            LAMBDA.handler({}, None)


class SecBetaPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database = self.directory / "smartflow-v2-shadow.db"
        self.snapshot_at = datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)
        create_beta_database(self.database, self.snapshot_at)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def _success(version: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"VersionId": version, "ETag": '"etag"'}),
            stderr="",
        )

    @patch.object(PUBLISHER.subprocess, "run")
    def test_publishes_snapshot_and_decision_pack_to_exact_keys(self, run):
        run.side_effect = [self._success("db-v1"), self._success("pack-v1")]

        result = PUBLISHER.publish_snapshot(
            self.database,
            now=self.snapshot_at,
        )

        self.assertEqual(result["status"], "published")
        self.assertEqual(result["key"], "beta/sec-v2-shadow.db")
        self.assertEqual(
            result["decision_pack"]["key"],
            "beta/sec-v2-decision-pack.json",
        )
        self.assertIsNone(result["archive"])
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn("beta/sec-v2-shadow.db", commands[0])
        self.assertIn("beta/sec-v2-decision-pack.json", commands[1])
        self.assertIn("AES256", commands[0])
        self.assertIn("application/json", commands[1])

    @patch.object(PUBLISHER.subprocess, "run")
    def test_monthly_archive_is_append_only_and_path_exact(self, run):
        august_first = datetime(2026, 7, 31, 16, 5, tzinfo=timezone.utc)
        august_database = self.directory / "smartflow-v2-shadow-august.db"
        create_beta_database(august_database, august_first)
        run.side_effect = [
            self._success("db-v1"),
            self._success("pack-v1"),
            self._success("archive-v1"),
        ]

        result = PUBLISHER.publish_snapshot(august_database, now=august_first)

        self.assertEqual(
            result["archive"]["key"],
            "snapshots/sec-v2/2026/08/sec-v2-shadow-20260801.db",
        )
        archive_command = run.call_args_list[2].args[0]
        self.assertIn("--if-none-match", archive_command)
        self.assertIn("*", archive_command)

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
