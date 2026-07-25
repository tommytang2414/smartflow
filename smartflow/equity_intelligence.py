"""Deterministic stock-first follow-up ranking across source-specific evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


ACCUMULATION = "ACCUMULATION"
DISTRIBUTION = "DISTRIBUTION"
MIXED = "MIXED"
CONTEXT_ONLY = "CONTEXT_ONLY"

FOLLOW_UP_HIGH = "FOLLOW_UP_HIGH"
FOLLOW_UP_MEDIUM = "FOLLOW_UP_MEDIUM"
FOLLOW_UP_LOW = "FOLLOW_UP_LOW"
NO_DIRECTIONAL_EVIDENCE = "NO_DIRECTIONAL_EVIDENCE"

SOURCE_MAX_AGE = {
    "sec_form4": timedelta(days=7),
    "sec_form144": timedelta(days=7),
    "congress": timedelta(days=90),
    "sec_13f": timedelta(days=150),
    "hkex_director": timedelta(days=14),
    "sfc_short": timedelta(days=14),
    "hkex_ccass": timedelta(days=7),
}

ACTION_CONTRACT = {
    "sec_form4": {
        "purchase": ACCUMULATION,
        "sale": DISTRIBUTION,
    },
    "sec_form144": {
        "proposed_sale": CONTEXT_ONLY,
    },
    "congress": {
        "purchase": ACCUMULATION,
        "sale": DISTRIBUTION,
        "exchange": CONTEXT_ONLY,
    },
    "sec_13f": {
        "position_increase": ACCUMULATION,
        "position_decrease": DISTRIBUTION,
        "position_exit": DISTRIBUTION,
        "position_snapshot": CONTEXT_ONLY,
    },
    "hkex_director": {
        "purchase": ACCUMULATION,
        "sale": DISTRIBUTION,
    },
    "sfc_short": {
        "position_snapshot": CONTEXT_ONLY,
        "position_increase": CONTEXT_ONLY,
        "position_decrease": CONTEXT_ONLY,
    },
    "hkex_ccass": {
        "custody_snapshot": CONTEXT_ONLY,
        "custody_change": CONTEXT_ONLY,
        "concentration_measurement": CONTEXT_ONLY,
    },
}

DIRECT_SOURCE_WEIGHT = {
    "sec_form4": 3,
    "hkex_director": 3,
    "congress": 2,
    "sec_13f": 1,
}

SOURCE_LIMITATIONS = {
    "sec_form144": "Form 144 is proposed sale intent, not confirmed execution.",
    "congress": "Congress disclosures may lag the transaction by up to 45 days.",
    "sec_13f": "Form 13F is a lagged quarterly holdings disclosure, not a live trade.",
    "sfc_short": "SFC data is an anonymous aggregate net-short position snapshot.",
    "hkex_ccass": "CCASS balances are participant custody accounts, not beneficial ownership or trades.",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class EquityObservation:
    source: str
    source_event_id: str
    market: str
    security_id: str
    ticker: str
    action: str
    event_at: datetime
    observed_at: datetime
    actor_id: str | None = None
    quality_status: str = "valid"

    def __post_init__(self) -> None:
        if self.source not in ACTION_CONTRACT:
            raise ValueError(f"unsupported equity source: {self.source}")
        if self.action not in ACTION_CONTRACT[self.source]:
            raise ValueError(
                f"unsupported action for {self.source}: {self.action}"
            )
        if not self.source_event_id.strip():
            raise ValueError("source_event_id is required")
        if not self.market.strip() or not self.security_id.strip() or not self.ticker.strip():
            raise ValueError("market, security_id and ticker are required")
        if self.quality_status not in {"valid", "warning", "invalid"}:
            raise ValueError(f"unsupported quality status: {self.quality_status}")
        _utc(self.event_at)
        _utc(self.observed_at)


@dataclass(frozen=True)
class EquityCandidate:
    market: str
    security_id: str
    ticker: str
    stance: str
    research_priority: str
    accumulation_sources: tuple[str, ...]
    distribution_sources: tuple[str, ...]
    context_sources: tuple[str, ...]
    distinct_directional_actors: int
    evidence_count: int
    limitations: tuple[str, ...]


def _source_units(
    observations: Iterable[EquityObservation],
    stance: str,
) -> tuple[int, set[str], set[tuple[str, str]]]:
    by_source_actor: set[tuple[str, str]] = set()
    sources: set[str] = set()
    units = 0
    for observation in observations:
        if ACTION_CONTRACT[observation.source][observation.action] != stance:
            continue
        actor = observation.actor_id or observation.source_event_id
        key = (observation.source, actor)
        if key in by_source_actor:
            continue
        by_source_actor.add(key)
        sources.add(observation.source)

    for source in sources:
        actor_count = sum(1 for item in by_source_actor if item[0] == source)
        units += min(actor_count, 3) * DIRECT_SOURCE_WEIGHT[source]
    return units, sources, by_source_actor


def _stance(accumulation_units: int, distribution_units: int) -> str:
    if accumulation_units == 0 and distribution_units == 0:
        return CONTEXT_ONLY
    if distribution_units == 0:
        return ACCUMULATION
    if accumulation_units == 0:
        return DISTRIBUTION
    if accumulation_units >= 2 * distribution_units:
        return ACCUMULATION
    if distribution_units >= 2 * accumulation_units:
        return DISTRIBUTION
    return MIXED


def _priority(
    *,
    stance: str,
    accumulation_sources: set[str],
    distribution_sources: set[str],
    actor_count: int,
    has_context: bool,
) -> str:
    if stance == CONTEXT_ONLY:
        return NO_DIRECTIONAL_EVIDENCE
    aligned_source_count = max(
        len(accumulation_sources),
        len(distribution_sources),
    )
    contradictory = bool(accumulation_sources and distribution_sources)
    if aligned_source_count >= 2 or actor_count >= 3 or contradictory:
        return FOLLOW_UP_HIGH
    if actor_count >= 2 or has_context:
        return FOLLOW_UP_MEDIUM
    return FOLLOW_UP_LOW


def rank_equity_candidates(
    observations: Iterable[EquityObservation],
    *,
    as_of: datetime,
) -> list[EquityCandidate]:
    """Rank research follow-ups without producing a trading recommendation."""
    as_of_utc = _utc(as_of)
    eligible: list[EquityObservation] = []
    seen_events: set[tuple[str, str]] = set()
    for observation in observations:
        event_key = (observation.source, observation.source_event_id)
        if event_key in seen_events:
            continue
        seen_events.add(event_key)
        if observation.quality_status == "invalid":
            continue
        event_at = _utc(observation.event_at)
        observed_at = _utc(observation.observed_at)
        if event_at > as_of_utc or observed_at > as_of_utc:
            continue
        if as_of_utc - event_at > SOURCE_MAX_AGE[observation.source]:
            continue
        eligible.append(observation)

    grouped: dict[tuple[str, str], list[EquityObservation]] = {}
    for observation in eligible:
        grouped.setdefault(
            (observation.market, observation.security_id),
            [],
        ).append(observation)

    candidates = []
    for (market, security_id), group in grouped.items():
        accumulation_units, accumulation_sources, accumulation_actors = _source_units(
            group,
            ACCUMULATION,
        )
        distribution_units, distribution_sources, distribution_actors = _source_units(
            group,
            DISTRIBUTION,
        )
        context_sources = {
            observation.source
            for observation in group
            if ACTION_CONTRACT[observation.source][observation.action] == CONTEXT_ONLY
        }
        stance = _stance(accumulation_units, distribution_units)
        actor_count = len(accumulation_actors | distribution_actors)
        limitations = tuple(
            SOURCE_LIMITATIONS[source]
            for source in sorted({observation.source for observation in group})
            if source in SOURCE_LIMITATIONS
        )
        ticker = sorted({observation.ticker for observation in group})[0]
        candidates.append(
            EquityCandidate(
                market=market,
                security_id=security_id,
                ticker=ticker,
                stance=stance,
                research_priority=_priority(
                    stance=stance,
                    accumulation_sources=accumulation_sources,
                    distribution_sources=distribution_sources,
                    actor_count=actor_count,
                    has_context=bool(context_sources),
                ),
                accumulation_sources=tuple(sorted(accumulation_sources)),
                distribution_sources=tuple(sorted(distribution_sources)),
                context_sources=tuple(sorted(context_sources)),
                distinct_directional_actors=actor_count,
                evidence_count=len(group),
                limitations=limitations,
            )
        )

    priority_order = {
        FOLLOW_UP_HIGH: 0,
        FOLLOW_UP_MEDIUM: 1,
        FOLLOW_UP_LOW: 2,
        NO_DIRECTIONAL_EVIDENCE: 3,
    }
    return sorted(
        candidates,
        key=lambda candidate: (
            priority_order[candidate.research_priority],
            -candidate.distinct_directional_actors,
            -candidate.evidence_count,
            candidate.market,
            candidate.ticker,
        ),
    )
