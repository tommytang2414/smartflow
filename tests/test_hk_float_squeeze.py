import unittest
from datetime import date
from pathlib import Path

from smartflow.hk_float_cases import load_float_squeeze_case
from smartflow.hk_float_squeeze import (
    INVALIDATED,
    OVERHEATED,
    TRIGGERED,
    WATCH_DATA_GAP,
    FloatSqueezeSnapshot,
    FloatStructure,
    OwnershipPoint,
    assess_float_squeeze,
    reconcile_ownership,
    render_owner_brief,
)


def snapshot(**overrides):
    values = {
        "ticker": "01234.HK",
        "company_name": "Synthetic Holdings",
        "as_of": date(2026, 7, 27),
        "anchor_holder_pct": 40,
        "disclosed_holders_pct": 75,
        "confirmed_holder_delta_pct_of_issued": 3,
        "issued_share_change_pct": -2.5,
        "executed_buyback_pct": 3,
        "buyback_announced": True,
        "tradable_float_pct": 18,
        "return_60d_pct": 12,
        "return_252d_pct": 20,
        "distance_to_20d_high_pct": -1,
        "latest_volume_ratio_20d": 2,
        "dual_listed": False,
    }
    values.update(overrides)
    return FloatSqueezeSnapshot(**values)


class HKFloatSqueezeTests(unittest.TestCase):
    def test_complete_locked_float_breakout_is_triggered(self):
        result = assess_float_squeeze(snapshot())

        self.assertEqual(result.state, TRIGGERED)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.confidence, "HIGH")
        self.assertEqual(result.data_gaps, ())

    def test_percentage_increase_without_share_delta_fails_closed(self):
        result = assess_float_squeeze(
            snapshot(
                confirmed_holder_delta_pct_of_issued=None,
                issued_share_change_pct=None,
                tradable_float_pct=None,
            )
        )

        self.assertEqual(result.state, WATCH_DATA_GAP)
        self.assertEqual(result.components["confirmed_accumulation"], 0)
        self.assertEqual(result.confidence, "LOW")
        self.assertEqual(
            result.data_gaps,
            (
                "actual_holder_share_delta",
                "issued_share_change",
                "consolidated_tradable_float",
            ),
        )

    def test_dual_listing_and_low_volume_near_high_are_risks(self):
        result = assess_float_squeeze(
            snapshot(
                dual_listed=True,
                return_252d_pct=59,
                latest_volume_ratio_20d=0.55,
            )
        )

        self.assertIn(
            "dual_listing_requires_consolidated_global_share_capital",
            result.risks,
        )
        self.assertIn("price_has_already_rerated_materially", result.risks)
        self.assertIn("near_high_without_volume_confirmation", result.risks)

    def test_owner_brief_explains_data_gap_instead_of_recommending_entry(self):
        item = snapshot(
            confirmed_holder_delta_pct_of_issued=None,
            issued_share_change_pct=None,
            tradable_float_pct=None,
        )
        report = render_owner_brief(item, assess_float_squeeze(item))

        self.assertIn("WATCH_DATA_GAP", report)
        self.assertIn("未證實為float squeeze", report)
        self.assertIn("actual_holder_share_delta", report)

    def test_invalid_percentages_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            snapshot(anchor_holder_pct=101)

    def test_distribution_or_material_dilution_invalidates_setup(self):
        distribution = assess_float_squeeze(
            snapshot(confirmed_holder_delta_pct_of_issued=-1)
        )
        dilution = assess_float_squeeze(snapshot(issued_share_change_pct=2))

        self.assertEqual(distribution.state, INVALIDATED)
        self.assertIn("confirmed_holder_distribution", distribution.risks)
        self.assertEqual(dilution.state, INVALIDATED)
        self.assertIn("material_share_supply_increase", dilution.risks)

    def test_percentage_rise_can_mask_actual_holder_distribution(self):
        previous = OwnershipPoint(
            as_of=date(2024, 3, 13),
            holder_name="Temasek",
            holder_shares=447_461_831,
            holder_pct=17.002,
            issued_shares=2_631_812_260,
            issued_shares_quality="exact",
        )
        current = OwnershipPoint(
            as_of=date(2026, 3, 2),
            holder_name="Temasek",
            holder_shares=405_300_789,
            holder_pct=18.005981,
            issued_shares=2_250_923_118,
            issued_shares_quality="inferred",
        )

        result = reconcile_ownership(previous, current)

        self.assertEqual(result.attribution, "CONFIRMED_DISTRIBUTION")
        self.assertEqual(result.holder_share_delta, -42_161_042)
        self.assertGreater(result.ownership_pct_change_points, 1)
        self.assertLess(result.issued_share_change_pct, -14)
        self.assertEqual(result.quality, "INCLUDES_INFERRED_ISSUED_SHARES")

    def test_unchanged_holder_with_percentage_rise_is_denominator_only(self):
        previous = OwnershipPoint(
            date(2026, 1, 1), "Holder", 200, 20, 1_000, "exact"
        )
        current = OwnershipPoint(
            date(2026, 2, 1), "Holder", 200, 25, 800, "exact"
        )

        result = reconcile_ownership(previous, current)

        self.assertEqual(result.attribution, "DENOMINATOR_ONLY")
        self.assertEqual(result.holder_share_delta, 0)
        self.assertEqual(result.issued_share_change_pct, -20)

    def test_float_structure_calculates_effective_tradable_float(self):
        structure = FloatStructure(
            issued_shares=298_976_000,
            effective_tradable_shares=24_854_000,
        )

        self.assertAlmostEqual(structure.tradable_float_pct, 8.31, places=2)

    def test_low_float_after_extreme_rerating_is_overheated(self):
        item = snapshot(
            confirmed_holder_delta_pct_of_issued=None,
            issued_share_change_pct=None,
            executed_buyback_pct=None,
            tradable_float_pct=9.2,
            return_60d_pct=761.85,
            return_252d_pct=703.84,
        )
        result = assess_float_squeeze(
            item
        )

        self.assertEqual(result.state, OVERHEATED)
        self.assertIn("low_float_can_amplify_drawdown_and_exit_slippage", result.risks)
        report = render_owner_brief(item, result)
        self.assertIn("唔係早期買入訊號", report)

    def test_standard_chartered_case_uses_publication_date_without_lookahead(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "hk_float_squeeze"
            / "standard_chartered_20260305.json"
        )

        case = load_float_squeeze_case(path)
        result = assess_float_squeeze(case.snapshot)

        self.assertEqual(case.information_date, date(2026, 3, 2))
        self.assertEqual(case.available_at, date(2026, 3, 5))
        self.assertEqual(result.state, INVALIDATED)
        self.assertIn("ownership_comparison_window_exceeds_365_days", result.risks)


if __name__ == "__main__":
    unittest.main()
