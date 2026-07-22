"""Week-over-week reconciliation for SFC aggregate short-position reports."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class SFCShortPositionChange:
    stock_code: str
    stock_name: str
    previous_shares: Decimal | None
    current_shares: Decimal | None
    shares_change: Decimal | None
    previous_value_hkd: Decimal | None
    current_value_hkd: Decimal | None
    value_change_hkd: Decimal | None
    reporting_state: str


def reconcile_sfc_short_reports(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> tuple[date, date, list[SFCShortPositionChange]]:
    """Compare two reports without treating a missing row as a zero position."""
    previous_date = previous["reporting_date"]
    current_date = current["reporting_date"]
    if current_date <= previous_date:
        raise ValueError("current SFC report must be newer than previous report")

    previous_by_code = {record["stock_code"]: record for record in previous["records"]}
    current_by_code = {record["stock_code"]: record for record in current["records"]}
    changes = []
    for stock_code in sorted(previous_by_code.keys() | current_by_code.keys()):
        old = previous_by_code.get(stock_code)
        new = current_by_code.get(stock_code)
        if old is None:
            state = "newly_reported"
        elif new is None:
            state = "not_in_current_report"
        elif (
            old["shares"] == new["shares"]
            and old["market_value_hkd"] == new["market_value_hkd"]
        ):
            state = "unchanged"
        else:
            state = "changed"

        previous_shares = old["shares"] if old else None
        current_shares = new["shares"] if new else None
        previous_value = old["market_value_hkd"] if old else None
        current_value = new["market_value_hkd"] if new else None
        changes.append(
            SFCShortPositionChange(
                stock_code=stock_code,
                stock_name=(new or old)["stock_name"],
                previous_shares=previous_shares,
                current_shares=current_shares,
                shares_change=(
                    current_shares - previous_shares
                    if current_shares is not None and previous_shares is not None
                    else None
                ),
                previous_value_hkd=previous_value,
                current_value_hkd=current_value,
                value_change_hkd=(
                    current_value - previous_value
                    if current_value is not None and previous_value is not None
                    else None
                ),
                reporting_state=state,
            )
        )
    return previous_date, current_date, changes
