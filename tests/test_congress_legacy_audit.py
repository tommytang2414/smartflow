import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from smartflow.congress_legacy_audit import audit_congress_legacy


class CongressLegacyAuditTests(unittest.TestCase):
    def test_legacy_rows_are_not_treated_as_official_ground_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE smart_money_signals (
                    id INTEGER PRIMARY KEY,
                    source TEXT,
                    source_id TEXT,
                    ticker TEXT,
                    entity_name TEXT,
                    direction TEXT,
                    value_usd REAL,
                    traded_at TEXT,
                    filed_at TEXT,
                    raw_data TEXT
                );
                """
            )
            connection.executemany(
                """
                INSERT INTO smart_money_signals
                (source, source_id, ticker, entity_name, direction, value_usd,
                 traded_at, filed_at, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "congress",
                        "congress_Member_2026-07-01",
                        "EXM",
                        "Member",
                        "BUY",
                        8000.5,
                        "2026-07-01",
                        "2026-07-20",
                        json.dumps(
                            {
                                "source": "quiverquant",
                                "amount_str": "$1,001 - $15,000",
                            }
                        ),
                    ),
                    (
                        "congress",
                        "congress_Other_2026-07-02",
                        None,
                        "Other",
                        "SELL",
                        50000,
                        "2026-07-02",
                        "2026-07-21",
                        json.dumps({"source": "disclosure", "amount_str": ""}),
                    ),
                ],
            )
            connection.commit()
            connection.close()

            result = audit_congress_legacy(database)
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["directions"], {"BUY": 1, "SELL": 1})
            self.assertEqual(result["range_disclosure_rows"], 1)
            self.assertEqual(result["range_value_midpoint_rows"], 1)
            self.assertEqual(result["missing_ticker_rows"], 1)
            self.assertEqual(result["non_report_row_identity_rows"], 2)
            self.assertEqual(result["official_report_row_traceable"], 0)
            self.assertEqual(
                result["status"],
                "legacy_identity_and_amount_semantics_unsupported",
            )


if __name__ == "__main__":
    unittest.main()
