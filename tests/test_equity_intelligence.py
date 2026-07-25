import unittest
from datetime import datetime, timedelta, timezone

from smartflow.equity_intelligence import (
    ACCUMULATION,
    CONTEXT_ONLY,
    FOLLOW_UP_HIGH,
    FOLLOW_UP_LOW,
    FOLLOW_UP_MEDIUM,
    MIXED,
    NO_DIRECTIONAL_EVIDENCE,
    DISTRIBUTION,
    EquityObservation,
    rank_equity_candidates,
)


AS_OF = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)


def observation(
    source,
    event_id,
    action,
    *,
    ticker="ACME",
    security_id="US:ACME",
    market="US",
    actor_id=None,
    age_days=1,
    quality_status="valid",
):
    event_at = AS_OF - timedelta(days=age_days)
    return EquityObservation(
        source=source,
        source_event_id=event_id,
        market=market,
        security_id=security_id,
        ticker=ticker,
        action=action,
        event_at=event_at,
        observed_at=event_at,
        actor_id=actor_id,
        quality_status=quality_status,
    )


class EquityIntelligenceTests(unittest.TestCase):
    def test_independent_accumulation_sources_create_high_priority_follow_up(self):
        candidates = rank_equity_candidates(
            [
                observation("sec_form4", "f4-1", "purchase", actor_id="insider-1"),
                observation("congress", "ptr-1", "purchase", actor_id="member-1"),
            ],
            as_of=AS_OF,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].stance, ACCUMULATION)
        self.assertEqual(candidates[0].research_priority, FOLLOW_UP_HIGH)
        self.assertEqual(
            candidates[0].accumulation_sources,
            ("congress", "sec_form4"),
        )

    def test_multiple_transactions_by_same_actor_do_not_fake_consensus(self):
        candidate = rank_equity_candidates(
            [
                observation("sec_form4", "f4-line-1", "purchase", actor_id="insider-1"),
                observation("sec_form4", "f4-line-2", "purchase", actor_id="insider-1"),
            ],
            as_of=AS_OF,
        )[0]

        self.assertEqual(candidate.distinct_directional_actors, 1)
        self.assertEqual(candidate.evidence_count, 2)
        self.assertEqual(candidate.research_priority, FOLLOW_UP_LOW)

    def test_context_can_raise_single_actor_follow_up_without_changing_stance(self):
        candidate = rank_equity_candidates(
            [
                observation("congress", "ptr-1", "sale", actor_id="member-1"),
                observation("sfc_short", "sfc-1", "position_increase"),
            ],
            as_of=AS_OF,
        )[0]

        self.assertEqual(candidate.stance, DISTRIBUTION)
        self.assertEqual(candidate.research_priority, FOLLOW_UP_MEDIUM)
        self.assertEqual(candidate.context_sources, ("sfc_short",))

    def test_sfc_ccass_and_form144_never_become_executed_direction(self):
        candidate = rank_equity_candidates(
            [
                observation("sfc_short", "sfc-1", "position_increase"),
                observation("hkex_ccass", "ccass-1", "custody_change"),
                observation("sec_form144", "144-1", "proposed_sale"),
            ],
            as_of=AS_OF,
        )[0]

        self.assertEqual(candidate.stance, CONTEXT_ONLY)
        self.assertEqual(candidate.research_priority, NO_DIRECTIONAL_EVIDENCE)
        self.assertEqual(candidate.distinct_directional_actors, 0)
        self.assertEqual(
            candidate.context_sources,
            ("hkex_ccass", "sec_form144", "sfc_short"),
        )
        self.assertEqual(len(candidate.limitations), 3)

    def test_conflicting_directional_sources_are_high_priority_mixed_evidence(self):
        candidate = rank_equity_candidates(
            [
                observation("sec_form4", "f4-1", "purchase", actor_id="insider-1"),
                observation("congress", "ptr-1", "sale", actor_id="member-1"),
            ],
            as_of=AS_OF,
        )[0]

        self.assertEqual(candidate.stance, MIXED)
        self.assertEqual(candidate.research_priority, FOLLOW_UP_HIGH)

    def test_stale_and_invalid_observations_are_excluded(self):
        candidates = rank_equity_candidates(
            [
                observation(
                    "sec_form4",
                    "stale",
                    "purchase",
                    actor_id="insider-1",
                    age_days=8,
                ),
                observation(
                    "congress",
                    "invalid",
                    "purchase",
                    actor_id="member-1",
                    quality_status="invalid",
                ),
            ],
            as_of=AS_OF,
        )

        self.assertEqual(candidates, [])

    def test_source_action_contract_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported action"):
            observation("hkex_ccass", "ccass-1", "purchase")


if __name__ == "__main__":
    unittest.main()
