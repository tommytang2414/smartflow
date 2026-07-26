"""Hash-pinned reprocessing of preserved House PTR raw evidence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import RawEvent
from smartflow.db.v2_repository import EvidenceConflictError, persist_event_batch
from smartflow.ingestion.congress import CongressParserError, CongressSchemaError
from smartflow.normalizers.congress import normalize_house_ptr
from smartflow.parsers.congress_house import extract_house_ptr_pdf_bytes


DOC_ID_PATTERN = re.compile(r"^\d{8}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class HouseReprocessResult:
    doc_id: str
    raw_event_id: int
    normalized_observed: int
    normalized_inserted: int


def reprocess_house_ptr(
    session: Session,
    *,
    doc_id: str,
    expected_sha256: str,
    report: dict[str, Any],
    extractor: Callable[..., dict[str, Any]] = extract_house_ptr_pdf_bytes,
) -> HouseReprocessResult:
    """Normalize one exact stored House PDF without downloading it again."""
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise ValueError("invalid House PTR DocID")
    normalized_sha256 = expected_sha256.strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized_sha256):
        raise ValueError(
            "expected SHA-256 must be 64 lowercase hexadecimal characters"
        )
    if (
        report.get("chamber") != "house"
        or str(report.get("doc_id", "")) != doc_id
    ):
        raise ValueError("House PTR report metadata does not match DocID")

    raw_event = session.scalar(
        select(RawEvent).where(
            RawEvent.source == "congress",
            RawEvent.source_event_id == f"house:{doc_id}",
        )
    )
    if raw_event is None:
        raise ValueError(f"House PTR raw evidence not found: {doc_id}")
    if not hmac.compare_digest(raw_event.payload_sha256, normalized_sha256):
        raise EvidenceConflictError(
            f"raw evidence hash mismatch for congress:house:{doc_id}"
        )
    if report.get("source_url") != raw_event.source_url:
        raise EvidenceConflictError(
            f"source URL mismatch for congress:house:{doc_id}"
        )

    payload: Any = raw_event.payload
    if not isinstance(payload, dict):
        raise CongressParserError(f"invalid raw payload for House PTR {doc_id}")
    if (
        payload.get("content_type") != "application/pdf"
        or payload.get("encoding") != "base64"
    ):
        raise CongressParserError(
            f"unexpected raw content contract for House PTR {doc_id}"
        )
    encoded_pdf = payload.get("body_base64")
    if not isinstance(encoded_pdf, str) or not encoded_pdf:
        raise CongressParserError(f"missing raw PDF for House PTR {doc_id}")
    try:
        pdf_content = base64.b64decode(encoded_pdf, validate=True)
    except ValueError as error:
        raise CongressParserError(
            f"invalid raw PDF encoding for House PTR {doc_id}"
        ) from error
    pdf_sha256 = hashlib.sha256(pdf_content).hexdigest()
    if (
        not pdf_content.startswith(b"%PDF-")
        or not hmac.compare_digest(str(payload.get("pdf_sha256", "")), pdf_sha256)
    ):
        raise EvidenceConflictError(
            f"raw PDF hash mismatch for congress:house:{doc_id}"
        )

    parsed = extractor(pdf_content, report=report)
    if not parsed:
        raise CongressParserError(f"House PTR parser rejected DocID {doc_id}")
    observed_at = raw_event.retrieved_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    normalized_events = normalize_house_ptr(parsed, observed_at=observed_at)
    if not normalized_events:
        raise CongressSchemaError(
            f"House PTR produced no normalized events for DocID {doc_id}"
        )

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
    return HouseReprocessResult(
        doc_id=doc_id,
        raw_event_id=raw_event.id,
        normalized_observed=len(normalized_events),
        normalized_inserted=result.normalized_inserted,
    )
