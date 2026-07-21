"""SEC filing normalization into source-specific v2 event semantics."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from smartflow.events import make_source_event_id


FORM4_PARSER_VERSION = "sec-form4-v1"
FORM144_PARSER_VERSION = "sec-form144-v1"

FORM4_ACTIONS = {
    "P": "purchase",
    "S": "sale",
    "A": "grant_or_award",
    "D": "issuer_disposition",
    "F": "tax_or_exercise_payment",
    "G": "gift",
    "M": "derivative_exercise_or_conversion",
    "J": "other_acquisition_or_disposition",
}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _utc_date(value: str) -> datetime | None:
    if not value:
        return None


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalize_form4(
    parsed: dict[str, Any],
    *,
    accession: str,
    filed_at: datetime | None,
    observed_at: datetime,
    source_url: str,
) -> list[dict[str, Any]]:
    """Create one normalized event per Form 4 transaction."""
    if not accession.strip():
        raise ValueError("Form 4 accession is required")

    events = []
    for index, transaction in enumerate(parsed.get("transactions", [])):
        transaction_code = str(transaction.get("code", "")).upper()
        quantity = _decimal(transaction.get("shares_raw", transaction.get("shares")))
        price = _decimal(transaction.get("price_raw", transaction.get("price")))
        event_at = _utc_date(str(transaction.get("date", "")))
        side = {"P": "BUY", "S": "SELL"}.get(transaction_code)
        quality_reasons = []
        if not parsed.get("ticker"):
            quality_reasons.append("missing_ticker")
        if event_at is None:
            quality_reasons.append("missing_or_invalid_event_at")
        if transaction_code not in FORM4_ACTIONS:
            quality_reasons.append(f"unmapped_transaction_code:{transaction_code or 'blank'}")

        events.append(
            {
                "source": "sec_form4",
                "source_event_id": make_source_event_id("sec_form4", accession, index),
                "event_type": "form4_transaction",
                "action": FORM4_ACTIONS.get(transaction_code, "other"),
                "side": side,
                "execution_status": "reported",
                "market": "US",
                "security_id": parsed.get("issuer_cik"),
                "ticker": parsed.get("ticker"),
                "entity_id": parsed.get("entity_cik"),
                "entity_name": parsed.get("entity_name"),
                "quantity": quantity,
                "price": price,
                "value": quantity * price if quantity is not None and price is not None else None,
                "currency": "USD",
                "event_at": event_at,
                "filed_at": _ensure_utc(filed_at),
                "observed_at": _ensure_utc(observed_at),
                "source_url": source_url,
                "parser_version": FORM4_PARSER_VERSION,
                "quality_status": "warning" if quality_reasons else "valid",
                "quality_reasons": quality_reasons,
            }
        )
    return events


def normalize_form144(
    parsed: dict[str, Any],
    *,
    accession: str,
    filed_at: datetime | None,
    observed_at: datetime,
    source_url: str,
) -> list[dict[str, Any]]:
    """Normalize Form 144 as proposed-sale intent, never an executed trade."""
    if not accession.strip():
        raise ValueError("Form 144 accession is required")

    quality_reasons = []
    if not parsed.get("ticker"):
        quality_reasons.append("missing_ticker")
    if parsed.get("proposed_sale_at") is None:
        quality_reasons.append("missing_proposed_sale_at")

    return [
        {
            "source": "sec_form144",
            "source_event_id": make_source_event_id("sec_form144", accession, 0),
            "event_type": "form144_notice",
            "action": "proposed_sale",
            "side": "SELL",
            "execution_status": "proposed",
            "market": "US",
            "security_id": parsed.get("issuer_cik"),
            "ticker": parsed.get("ticker"),
            "entity_id": parsed.get("filer_cik"),
            "entity_name": parsed.get("filer_name"),
            "quantity": _decimal(parsed.get("no_of_units_sold")),
            "price": None,
            "value": _decimal(parsed.get("proposed_amount")),
            "currency": "USD",
            "event_at": _ensure_utc(parsed.get("proposed_sale_at")),
            "filed_at": _ensure_utc(filed_at),
            "observed_at": _ensure_utc(observed_at),
            "source_url": source_url,
            "parser_version": FORM144_PARSER_VERSION,
            "quality_status": "warning" if quality_reasons else "valid",
            "quality_reasons": quality_reasons,
        }
    ]
