"""Normalize official congressional transaction disclosures into v2 evidence."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from smartflow.events import make_source_event_id


HOUSE_PTR_PARSER_VERSION = "congress-house-ptr-v2"
HOUSE_ACTIONS = {
    "P": ("purchase", "BUY"),
    "S": ("sale", "SELL"),
    "E": ("exchange", None),
}


def _utc_date(value) -> datetime:
    return datetime.combine(value, time.min, timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def normalize_house_ptr(
    parsed: dict[str, Any],
    *,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    """Create one range-preserving event per official House PTR row."""
    doc_id = str(parsed.get("doc_id", ""))
    if parsed.get("chamber") != "house" or not doc_id.isdigit():
        raise ValueError("invalid House PTR identity")
    member_name = str(parsed.get("member_name", "")).strip()
    if not member_name:
        raise ValueError("House PTR member_name is required")
    member_id = make_source_event_id(
        "congress_house_member",
        member_name.casefold(),
        parsed.get("state_district") or "unknown",
    )
    if parsed.get("document_status") == "requires_amendment_reconciliation":
        return [
            {
                "source": "congress",
                "source_event_id": make_source_event_id(
                    "congress",
                    "house",
                    doc_id,
                    "amendment_requires_reconciliation",
                ),
                "event_type": "congress_document_notice",
                "action": "amendment_requires_reconciliation",
                "side": None,
                "execution_status": "reported",
                "market": "US",
                "security_id": None,
                "ticker": None,
                "entity_id": member_id,
                "entity_name": member_name,
                "entities": [
                    {
                        "member_name": member_name,
                        "chamber": "house",
                        "state_district": parsed.get("state_district"),
                    }
                ],
                "attributes": {
                    "chamber": "house",
                    "doc_id": doc_id,
                    "document_status": "requires_amendment_reconciliation",
                    "amendment_indicator": parsed["amendment_indicator"],
                },
                "quantity": None,
                "price": None,
                "value": None,
                "currency": None,
                "event_at": _utc_date(parsed["filing_date"]),
                "filed_at": _utc_date(parsed["filing_date"]),
                "observed_at": _utc(observed_at),
                "source_url": parsed["source_url"],
                "parser_version": HOUSE_PTR_PARSER_VERSION,
                "quality_status": "warning",
                "quality_reasons": [
                    "amendment_requires_original_report_reconciliation",
                    "no_directional_transaction_extracted",
                ],
            }
        ]
    if parsed.get("document_status") == "requires_ocr":
        return [
            {
                "source": "congress",
                "source_event_id": make_source_event_id(
                    "congress",
                    "house",
                    doc_id,
                    "document_requires_ocr",
                ),
                "event_type": "congress_document_notice",
                "action": "unparsed_document",
                "side": None,
                "execution_status": "reported",
                "market": "US",
                "security_id": None,
                "ticker": None,
                "entity_id": member_id,
                "entity_name": member_name,
                "entities": [
                    {
                        "member_name": member_name,
                        "chamber": "house",
                        "state_district": parsed.get("state_district"),
                    }
                ],
                "attributes": {
                    "chamber": "house",
                    "doc_id": doc_id,
                    "document_status": "requires_ocr",
                },
                "quantity": None,
                "price": None,
                "value": None,
                "currency": None,
                "event_at": _utc_date(parsed["filing_date"]),
                "filed_at": _utc_date(parsed["filing_date"]),
                "observed_at": _utc(observed_at),
                "source_url": parsed["source_url"],
                "parser_version": HOUSE_PTR_PARSER_VERSION,
                "quality_status": "warning",
                "quality_reasons": [
                    "image_only_pdf_requires_ocr",
                    "no_directional_transaction_extracted",
                ],
            }
        ]

    events = []
    for transaction in parsed.get("transactions", []):
        transaction_code = transaction["transaction_code"]
        if transaction_code not in HOUSE_ACTIONS:
            raise ValueError(f"unsupported House PTR transaction code: {transaction_code}")
        action, side = HOUSE_ACTIONS[transaction_code]
        row_number = int(transaction["row_number"])
        ticker = transaction.get("ticker")
        quality_reasons = []
        if not ticker:
            quality_reasons.append("ticker_not_disclosed")
        if transaction["notification_date"] < transaction["transaction_date"]:
            quality_reasons.append("notification_precedes_transaction")

        events.append(
            {
                "source": "congress",
                "source_event_id": make_source_event_id(
                    "congress",
                    "house",
                    doc_id,
                    row_number,
                ),
                "event_type": "congress_periodic_transaction",
                "action": action,
                "side": side,
                "execution_status": "reported",
                "market": "US",
                "security_id": f"US:{ticker}" if ticker else None,
                "ticker": ticker,
                "entity_id": member_id,
                "entity_name": member_name,
                "entities": [
                    {
                        "member_name": member_name,
                        "chamber": "house",
                        "state_district": parsed.get("state_district"),
                        "owner_code": transaction.get("owner_code"),
                    }
                ],
                "attributes": {
                    "chamber": "house",
                    "doc_id": doc_id,
                    "row_number": row_number,
                    "asset": transaction["asset"],
                    "asset_type": transaction.get("asset_type"),
                    "transaction_type": transaction["transaction_type"],
                    "owner_code": transaction.get("owner_code"),
                    "notification_date": transaction["notification_date"].isoformat(),
                    "amount_lower": str(transaction["amount_lower"]),
                    "amount_upper": (
                        str(transaction["amount_upper"])
                        if transaction["amount_upper"] is not None
                        else None
                    ),
                    "amount_is_range": transaction["amount_is_range"],
                },
                "quantity": None,
                "price": None,
                "value": None,
                "currency": "USD",
                "event_at": _utc_date(transaction["transaction_date"]),
                "filed_at": _utc_date(parsed["filing_date"]),
                "observed_at": _utc(observed_at),
                "source_url": parsed["source_url"],
                "parser_version": HOUSE_PTR_PARSER_VERSION,
                "quality_status": "warning" if quality_reasons else "valid",
                "quality_reasons": quality_reasons,
            }
        )
    if not events:
        raise ValueError("House PTR produced no normalized events")
    return events
