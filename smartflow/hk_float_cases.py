"""Point-in-time case loading for the local Hong Kong float-squeeze prototype."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from smartflow.hk_float_squeeze import (
    FloatSqueezeSnapshot,
    FloatStructure,
    OwnershipPoint,
    OwnershipReconciliation,
    reconcile_ownership,
)


@dataclass(frozen=True)
class FloatSqueezeCase:
    case_id: str
    snapshot: FloatSqueezeSnapshot
    information_date: date
    available_at: date
    ownership_reconciliation: OwnershipReconciliation | None
    outcome: dict[str, float | None] | None
    research: tuple[dict[str, str], ...]


def _ownership_point(payload: dict) -> OwnershipPoint:
    return OwnershipPoint(
        as_of=date.fromisoformat(payload["as_of"]),
        holder_name=payload["holder_name"],
        holder_shares=int(payload["holder_shares"]),
        holder_pct=float(payload["holder_pct"]),
        issued_shares=int(payload["issued_shares"]),
        issued_shares_quality=payload["issued_shares_quality"],
    )


def load_float_squeeze_case(path: Path) -> FloatSqueezeCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    available_at = date.fromisoformat(payload["available_at"])
    information_date = date.fromisoformat(payload["information_date"])
    if available_at < information_date:
        raise ValueError("available_at cannot precede information_date")

    ownership = payload.get("ownership_history")
    reconciliation = None
    if ownership is not None:
        previous = _ownership_point(
            {**ownership["previous"], "holder_name": ownership["holder_name"]}
        )
        current = _ownership_point(
            {**ownership["current"], "holder_name": ownership["holder_name"]}
        )
        reconciliation = reconcile_ownership(previous, current)
        if reconciliation.current_as_of > information_date:
            raise ValueError(
                "ownership evidence date cannot follow the case information_date"
            )

    float_payload = payload.get("float_structure")
    float_structure = (
        FloatStructure(
            issued_shares=int(float_payload["issued_shares"]),
            effective_tradable_shares=int(
                float_payload["effective_tradable_shares"]
            ),
        )
        if float_payload is not None
        else None
    )
    lock = payload["ownership_lock"]
    capital = payload["capital"]
    market = payload["market"]
    snapshot = FloatSqueezeSnapshot(
        ticker=payload["ticker"],
        company_name=payload["company_name"],
        as_of=available_at,
        anchor_holder_pct=float(lock["anchor_holder_pct"]),
        disclosed_holders_pct=float(lock["disclosed_holders_pct"]),
        confirmed_holder_delta_pct_of_issued=(
            reconciliation.holder_delta_pct_of_prior_issued
            if reconciliation is not None
            else None
        ),
        issued_share_change_pct=(
            reconciliation.issued_share_change_pct
            if reconciliation is not None
            else (
                float(capital["issued_share_change_pct"])
                if capital["issued_share_change_pct"] is not None
                else None
            )
        ),
        executed_buyback_pct=(
            float(capital["executed_buyback_pct"])
            if capital["executed_buyback_pct"] is not None
            else None
        ),
        buyback_announced=bool(capital["buyback_announced"]),
        tradable_float_pct=(
            float_structure.tradable_float_pct
            if float_structure is not None
            else None
        ),
        return_60d_pct=float(market["return_60d_pct"]),
        return_252d_pct=float(market["return_252d_pct"]),
        distance_to_20d_high_pct=float(market["distance_to_20d_high_pct"]),
        latest_volume_ratio_20d=float(market["latest_volume_ratio_20d"]),
        ownership_window_days=(
            reconciliation.window_days if reconciliation is not None else None
        ),
        dual_listed=bool(payload["dual_listed"]),
    )
    return FloatSqueezeCase(
        case_id=payload["case_id"],
        snapshot=snapshot,
        information_date=information_date,
        available_at=available_at,
        ownership_reconciliation=reconciliation,
        outcome=payload.get("outcome"),
        research=tuple(payload["research"]),
    )
