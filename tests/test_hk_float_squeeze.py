import unittest
from datetime import date

from smartflow.hk_float_squeeze import (
    INVALIDATED,
    TRIGGERED,
    WATCH_DATA_GAP,
    FloatSqueezeSnapshot,
    assess_float_squeeze,
    render_owner_brief,
)


def snapshot(**overrides):
    values = {
        "ticker": "01234.HK",
        "company_name": "Synthetic Holdings",
        "as_of": date(2026, 7, 27),
        "anchor_holder_pct": 40,
        "disclosed_holders_pct": 75,
        "confirmed_holder_accumulation_pct_90d": 3,
        "issued_share_change_pct_90d": -2.5,
        "executed_buyback_pct_90d": 3,
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
                confirmed_holder_accumulation_pct_90d=None,
                issued_share_change_pct_90d=None,
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
            confirmed_holder_accumulation_pct_90d=None,
            issued_share_change_pct_90d=None,
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
            snapshot(confirmed_holder_accumulation_pct_90d=-1)
        )
        dilution = assess_float_squeeze(snapshot(issued_share_change_pct_90d=2))

        self.assertEqual(distribution.state, INVALIDATED)
        self.assertIn("confirmed_holder_distribution", distribution.risks)
        self.assertEqual(dilution.state, INVALIDATED)
        self.assertIn("material_share_supply_increase", dilution.risks)


if __name__ == "__main__":
    unittest.main()
