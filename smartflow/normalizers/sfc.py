"""Normalize SFC short-position snapshots without inventing trade semantics."""

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from smartflow.events import make_source_event_id


SFC_SHORT_PARSER_VERSION = "sfc-short-v1"
HONG_KONG = ZoneInfo("Asia/Hong_Kong")


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_sfc_short_report(
    parsed: dict[str, Any],
    *,
    published_at: datetime | None,
    observed_at: datetime,
    source_url: str,
) -> list[dict[str, Any]]:
    """Create one anonymous aggregate position snapshot per specified share."""
    report_date = parsed["reporting_date"]
    event_at = datetime.combine(report_date, time(16, 0), HONG_KONG).astimezone(
        timezone.utc
    )
    events = []
    for record in parsed["records"]:
        stock_code = record["stock_code"]
        quality_reasons = []
        if record["market_value_hkd"] is None:
            quality_reasons.append("market_value_not_available")
        events.append(
            {
                "source": "sfc_short",
                "source_event_id": make_source_event_id(
                    "sfc_short", report_date.isoformat(), stock_code
                ),
                "event_type": "aggregated_reportable_short_position",
                "action": "position_snapshot",
                "side": "SHORT",
                "execution_status": "reported",
                "market": "HK",
                "security_id": f"HKEX:{stock_code}",
                "ticker": f"{stock_code}.HK",
                "entity_id": None,
                "entity_name": None,
                "entities": None,
                "quantity": record["shares"],
                "price": None,
                "value": record["market_value_hkd"],
                "currency": "HKD",
                "event_at": event_at,
                "filed_at": _ensure_utc(published_at),
                "observed_at": _ensure_utc(observed_at),
                "source_url": source_url,
                "parser_version": SFC_SHORT_PARSER_VERSION,
                "quality_status": "warning" if quality_reasons else "valid",
                "quality_reasons": quality_reasons,
            }
        )
    return events
