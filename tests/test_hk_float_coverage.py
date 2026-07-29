import unittest
from pathlib import Path

from smartflow.hk_float_coverage import (
    load_sfc_concentration_cases,
    summarize_sfc_universe,
)


UNIVERSE = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "hk_float_coverage"
    / "sfc_high_concentration_20250101_20260630.csv"
)


class HKFloatCoverageTests(unittest.TestCase):
    def test_fixed_universe_contains_all_27_sfc_notices(self):
        cases = load_sfc_concentration_cases(UNIVERSE)

        self.assertEqual(len(cases), 27)
        self.assertEqual(cases[0].stock_code, "02531")
        self.assertEqual(cases[-1].stock_code, "09963")

    def test_every_notice_arrived_after_at_least_100pct_rerating(self):
        result = summarize_sfc_universe(load_sfc_concentration_cases(UNIVERSE))

        self.assertEqual(result.notice_before_100pct_rerating_count, 0)
        self.assertEqual(result.min_pre_notice_rerating_pct, 193.6)
        self.assertEqual(result.median_pre_notice_rerating_pct, 474)

    def test_all_cases_had_other_shareholder_residual_at_or_below_10pct(self):
        result = summarize_sfc_universe(load_sfc_concentration_cases(UNIVERSE))

        self.assertEqual(result.other_shareholders_at_or_below_10pct_count, 27)
        self.assertEqual(result.median_reported_other_shareholders_pct, 8.03)

    def test_notice_delay_is_explicit_and_not_backdated(self):
        result = summarize_sfc_universe(load_sfc_concentration_cases(UNIVERSE))

        self.assertEqual(result.median_notice_lag_calendar_days, 14)
        self.assertEqual(result.min_notice_lag_calendar_days, 9)
        self.assertEqual(result.max_notice_lag_calendar_days, 22)

    def test_h_share_denominator_is_not_mixed_with_domestic_shares(self):
        cases = load_sfc_concentration_cases(UNIVERSE)
        h_share_cases = [
            case for case in cases if case.share_class_scope == "H_SHARES_ONLY"
        ]

        self.assertEqual(len(h_share_cases), 1)
        self.assertEqual(h_share_cases[0].stock_code, "02418")


if __name__ == "__main__":
    unittest.main()
