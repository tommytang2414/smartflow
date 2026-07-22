"""Normalize CCASS custody snapshots and transparent concentration metrics."""

from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from smartflow.events import make_source_event_id


CCASS_PARSER_VERSION = "ccass-v1"
HONG_KONG = ZoneInfo("Asia/Hong_Kong")


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def concentration_attributes(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe participant-account concentration without beneficial-owner claims."""
    total_shares = sum((holding["shares"] for holding in holdings), Decimal("0"))
    ranked = sorted(holdings, key=lambda holding: holding["shares"], reverse=True)
    top_1 = ranked[0]["shares"] / total_shares * 100
    top_5 = sum(
        (holding["shares"] for holding in ranked[:5]), Decimal("0")
    ) / total_shares * 100
    hhi = sum(
        ((holding["shares"] / total_shares) ** 2 for holding in holdings),
        Decimal("0"),
    )
    return {
        "participant_count": len(holdings),
        "total_ccass_shares": str(total_shares),
        "top_1_participant_pct_of_ccass": str(top_1),
        "top_5_participant_pct_of_ccass": str(top_5),
        "participant_hhi": str(hhi),
        "top_5_participant_ids": [holding["participant_id"] for holding in ranked[:5]],
        "interpretation": "participant_account_concentration_not_beneficial_ownership",
    }


def normalize_ccass_snapshot(
    parsed: dict[str, Any],
    *,
    observed_at: datetime,
    source_url: str,
) -> list[dict[str, Any]]:
    """Create participant custody balances plus one non-directional concentration event."""
    stock_code = parsed["stock_code"]
    holding_date = parsed["holding_date"]
    event_at = datetime.combine(holding_date, time(23, 59, 59), HONG_KONG).astimezone(
        timezone.utc
    )
    common = {
        "source": "hkex_ccass",
        "market": "HK",
        "security_id": f"HKEX:{stock_code}",
        "ticker": f"{stock_code}.HK",
        "price": None,
        "value": None,
        "currency": None,
        "event_at": event_at,
        "filed_at": None,
        "observed_at": _ensure_utc(observed_at),
        "source_url": source_url,
        "parser_version": CCASS_PARSER_VERSION,
        "quality_status": "valid",
        "quality_reasons": [],
    }

    events = []
    for holding in parsed["holdings"]:
        events.append(
            {
                **common,
                "source_event_id": make_source_event_id(
                    "hkex_ccass_holding",
                    holding_date.isoformat(),
                    stock_code,
                    holding["participant_id"],
                ),
                "event_type": "ccass_participant_holding_snapshot",
                "action": "custody_snapshot",
                "side": None,
                "execution_status": "reported",
                "entity_id": holding["participant_id"],
                "entity_name": holding["participant_name"] or None,
                "entities": None,
                "attributes": {
                    "participant_type": holding["participant_type"],
                    "pct_of_issued_shares": str(holding["pct_of_issued_shares"]),
                    "interpretation": "participant_account_balance_not_beneficial_ownership",
                },
                "quantity": holding["shares"],
            }
        )

    events.append(
        {
            **common,
            "source_event_id": make_source_event_id(
                "hkex_ccass_concentration", holding_date.isoformat(), stock_code
            ),
            "event_type": "ccass_participant_concentration_snapshot",
            "action": "concentration_measurement",
            "side": None,
            "execution_status": "derived",
            "entity_id": None,
            "entity_name": None,
            "entities": None,
            "attributes": concentration_attributes(parsed["holdings"]),
            "quantity": sum(
                (holding["shares"] for holding in parsed["holdings"]), Decimal("0")
            ),
        }
    )
    return events
