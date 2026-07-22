"""Validate a structured CCASS snapshot obtained through an approved data route."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


PARTICIPANT_ID = re.compile(r"^[A-Z]\d{4,6}$")


class CCASSSnapshotError(ValueError):
    pass


def _decimal(value: Any, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as error:
        raise CCASSSnapshotError(f"invalid {field}: {value!r}") from error
    return result


def parse_ccass_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate stock/date/participant balances without assigning trade direction."""
    raw_stock_code = str(payload.get("stock_code", "")).strip()
    if not raw_stock_code.isdigit():
        raise CCASSSnapshotError("CCASS stock_code must be numeric")
    stock_code = raw_stock_code.zfill(5)
    try:
        holding_date = date.fromisoformat(str(payload.get("holding_date", "")))
    except ValueError as error:
        raise CCASSSnapshotError("invalid CCASS holding_date") from error

    raw_holdings = payload.get("holdings")
    if not isinstance(raw_holdings, list) or not raw_holdings:
        raise CCASSSnapshotError("CCASS snapshot contains no participant holdings")

    holdings = []
    seen_participants: set[str] = set()
    for index, item in enumerate(raw_holdings):
        if not isinstance(item, dict):
            raise CCASSSnapshotError(f"holding {index} must be an object")
        participant_id = str(item.get("participant_id", "")).strip().upper()
        if not PARTICIPANT_ID.fullmatch(participant_id):
            raise CCASSSnapshotError(f"invalid participant_id at holding {index}")
        if participant_id in seen_participants:
            raise CCASSSnapshotError(f"duplicate participant_id: {participant_id}")
        seen_participants.add(participant_id)

        shares = _decimal(item.get("shares"), field=f"shares at holding {index}")
        if shares <= 0 or shares != shares.to_integral_value():
            raise CCASSSnapshotError(
                f"shares must be a positive whole number at holding {index}"
            )
        pct_of_issued_shares = _decimal(
            item.get("pct_of_issued_shares"),
            field=f"issued-share percentage at holding {index}",
        )
        if pct_of_issued_shares < 0 or pct_of_issued_shares > 100:
            raise CCASSSnapshotError(
                f"issued-share percentage out of range at holding {index}"
            )

        participant_name = str(item.get("participant_name", "")).strip()
        participant_type = str(item.get("participant_type", "other")).strip().lower()
        if participant_type not in {"clearing", "broker", "bank", "finance", "investor", "other"}:
            raise CCASSSnapshotError(
                f"invalid participant_type at holding {index}: {participant_type}"
            )
        holdings.append(
            {
                "participant_id": participant_id,
                "participant_name": participant_name,
                "participant_type": participant_type,
                "shares": shares,
                "pct_of_issued_shares": pct_of_issued_shares,
            }
        )

    return {
        "stock_code": stock_code,
        "stock_name": str(payload.get("stock_name", "")).strip(),
        "holding_date": holding_date,
        "holdings": holdings,
    }
