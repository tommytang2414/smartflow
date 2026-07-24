"""Bounded reprocessing of preserved SEC Form 4 raw evidence."""

import hmac
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import RawEvent
from smartflow.db.v2_repository import EvidenceConflictError, persist_event_batch
from smartflow.ingestion.sec import SECParserError, SECSchemaError
from smartflow.normalizers.sec import normalize_form4
from smartflow.parsers.edgar_xml import parse_form4_xml


ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Form4ReprocessResult:
    accession: str
    raw_event_id: int
    normalized_observed: int
    normalized_inserted: int


def reprocess_transactionless_form4(
    session: Session,
    *,
    accession: str,
    expected_sha256: str,
) -> Form4ReprocessResult:
    """Add the v4 administrative child for one exact immutable raw filing."""
    if not ACCESSION_PATTERN.fullmatch(accession):
        raise ValueError("invalid SEC accession")
    normalized_sha256 = expected_sha256.strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")

    raw_event = session.scalar(
        select(RawEvent).where(
            RawEvent.source == "sec_form4",
            RawEvent.source_event_id == accession,
        )
    )
    if raw_event is None:
        raise ValueError(f"Form 4 raw evidence not found: {accession}")
    if not hmac.compare_digest(raw_event.payload_sha256, normalized_sha256):
        raise EvidenceConflictError(f"raw evidence hash mismatch for sec_form4:{accession}")

    payload: Any = raw_event.payload
    if not isinstance(payload, dict):
        raise SECParserError(f"invalid raw payload for sec_form4:{accession}")
    if payload.get("content_type") != "application/xml":
        raise SECParserError(f"unexpected raw content type for sec_form4:{accession}")
    xml_content = payload.get("xml")
    if not isinstance(xml_content, str) or not xml_content.strip():
        raise SECParserError(f"missing raw XML for sec_form4:{accession}")

    parsed = parse_form4_xml(xml_content)
    if parsed is None:
        raise SECParserError(f"sec_form4 parser rejected accession {accession}")
    if not parsed.get("is_transactionless_administrative"):
        raise SECSchemaError(f"accession is not a transactionless administrative Form 4: {accession}")

    normalized_events = normalize_form4(
        parsed,
        accession=accession,
        filed_at=None,
        observed_at=raw_event.retrieved_at,
        source_url=raw_event.source_url or "",
    )
    if len(normalized_events) != 1:
        raise SECSchemaError(f"administrative Form 4 must produce exactly one event: {accession}")

    result = persist_event_batch(
        session,
        raw_event={
            "source": raw_event.source,
            "source_event_id": raw_event.source_event_id,
            "source_url": raw_event.source_url,
            "payload": raw_event.payload,
            "payload_sha256": raw_event.payload_sha256,
            "http_status": raw_event.http_status,
            "retrieved_at": raw_event.retrieved_at,
        },
        normalized_events=normalized_events,
    )
    return Form4ReprocessResult(
        accession=accession,
        raw_event_id=raw_event.id,
        normalized_observed=1,
        normalized_inserted=result.normalized_inserted,
    )
