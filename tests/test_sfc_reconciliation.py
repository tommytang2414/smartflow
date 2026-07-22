import unittest
from decimal import Decimal
from pathlib import Path

from smartflow.parsers.sfc_short_csv import parse_sfc_short_csv
from smartflow.sfc_reconciliation import reconcile_sfc_short_reports


FIXTURES = Path(__file__).parent / "fixtures" / "sfc"


class SFCReconciliationTests(unittest.TestCase):
    def test_two_official_weeks_produce_exact_position_changes(self):
        previous = parse_sfc_short_csv(
            (FIXTURES / "short_positions_20260703_official_excerpt.csv").read_text(
                encoding="utf-8"
            )
        )
        current = parse_sfc_short_csv(
            (FIXTURES / "short_positions_20260710_official_excerpt.csv").read_text(
                encoding="utf-8"
            )
        )
        previous_date, current_date, changes = reconcile_sfc_short_reports(previous, current)
        by_code = {change.stock_code: change for change in changes}

        self.assertEqual((previous_date.isoformat(), current_date.isoformat()), ("2026-07-03", "2026-07-10"))
        self.assertEqual(by_code["00001"].shares_change, Decimal("4171666"))
        self.assertEqual(by_code["00005"].value_change_hkd, Decimal("647013365"))
        self.assertEqual(by_code["00028"].reporting_state, "unchanged")

    def test_missing_row_is_not_converted_to_zero(self):
        previous = {
            "reporting_date": __import__("datetime").date(2026, 7, 3),
            "records": [{"stock_code": "00001", "stock_name": "ONE", "shares": Decimal("10"), "market_value_hkd": Decimal("20")}],
        }
        current = {"reporting_date": __import__("datetime").date(2026, 7, 10), "records": []}
        _, _, changes = reconcile_sfc_short_reports(previous, current)

        self.assertEqual(changes[0].reporting_state, "not_in_current_report")
        self.assertIsNone(changes[0].current_shares)
        self.assertIsNone(changes[0].shares_change)


if __name__ == "__main__":
    unittest.main()
