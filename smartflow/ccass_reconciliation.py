"""Non-directional custody-balance changes between CCASS snapshots."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CCASSParticipantBalanceChange:
    participant_id: str
    participant_name: str
    previous_shares: Decimal | None
    current_shares: Decimal | None
    shares_change: Decimal | None
    reporting_state: str
    interpretation: str = "custody_balance_change_not_trade_direction"


def reconcile_ccass_snapshots(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> tuple[date, date, list[CCASSParticipantBalanceChange]]:
    """Compare like-for-like stock snapshots without BUY/SELL inference."""
    if previous["stock_code"] != current["stock_code"]:
        raise ValueError("CCASS reconciliation requires the same stock code")
    previous_date = previous["holding_date"]
    current_date = current["holding_date"]
    if current_date <= previous_date:
        raise ValueError("current CCASS snapshot must be newer than previous snapshot")

    old_by_id = {holding["participant_id"]: holding for holding in previous["holdings"]}
    new_by_id = {holding["participant_id"]: holding for holding in current["holdings"]}
    changes = []
    for participant_id in sorted(old_by_id.keys() | new_by_id.keys()):
        old = old_by_id.get(participant_id)
        new = new_by_id.get(participant_id)
        if old is None:
            state = "newly_present"
        elif new is None:
            state = "not_in_current_snapshot"
        elif old["shares"] == new["shares"]:
            state = "unchanged"
        else:
            state = "changed"
        previous_shares = old["shares"] if old else None
        current_shares = new["shares"] if new else None
        changes.append(
            CCASSParticipantBalanceChange(
                participant_id=participant_id,
                participant_name=(new or old)["participant_name"],
                previous_shares=previous_shares,
                current_shares=current_shares,
                shares_change=(
                    current_shares - previous_shares
                    if current_shares is not None and previous_shares is not None
                    else None
                ),
                reporting_state=state,
            )
        )
    return previous_date, current_date, changes
