"""Official Congress disclosure ingestion into immutable v2 evidence."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from smartflow.db.v2_repository import BatchPersistResult, persist_event_batch
from smartflow.events import payload_sha256
from smartflow.health import SourceHealthPolicy
from smartflow.normalizers.congress import normalize_house_ptr
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.congress_house import extract_house_ptr_pdf_bytes


CONGRESS_POLICY = SourceHealthPolicy(
    source="congress",
    expected_interval_seconds=3600,
    freshness_sla_seconds=10800,
)
MAX_HOUSE_PDF_BYTES = 10 * 1024 * 1024


class CongressParserError(ValueError):
    pass


class CongressSchemaError(ValueError):
    pass


class CongressIngestionStageError(RuntimeError):
    def __init__(self, failure_kind: str, error: Exception):
        super().__init__(str(error))
        self.failure_kind = failure_kind
        self.original_error = error


@dataclass(frozen=True)
class CongressIngestionResult:
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    warning_events: int
    run_id: int | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ingest_house_ptr_pdf(
    session: Session,
    *,
    pdf_content: bytes,
    report: dict[str, Any],
    observed_at: datetime,
    http_status: int = 200,
    record_outcome: bool = True,
    extractor: Callable[..., dict[str, Any]] = extract_house_ptr_pdf_bytes,
) -> CongressIngestionResult:
    """Persist exact PDF bytes and all normalized report rows atomically."""
    doc_id = str(report.get("doc_id", "")).strip()
    if report.get("chamber") != "house" or not doc_id.isdigit():
        raise ValueError("valid House report metadata is required")
    if not pdf_content or len(pdf_content) > MAX_HOUSE_PDF_BYTES:
        raise ValueError("House PTR PDF size is invalid")

    started_at = _utc_now()
    raw_payload = {
        "content_type": "application/pdf",
        "encoding": "base64",
        "body_base64": base64.b64encode(pdf_content).decode("ascii"),
        "pdf_sha256": hashlib.sha256(pdf_content).hexdigest(),
    }
    raw_event = {
        "source": "congress",
        "source_event_id": f"house:{doc_id}",
        "source_url": report["source_url"],
        "payload": raw_payload,
        "payload_sha256": payload_sha256(raw_payload),
        "http_status": http_status,
        "retrieved_at": observed_at,
    }

    normalized_events: list[dict[str, Any]] = []
    persist_result = BatchPersistResult(0, 0)
    stage = "parser"
    try:
        parsed = extractor(pdf_content, report=report)
        if not parsed:
            raise CongressParserError(f"House PTR parser rejected DocID {doc_id}")
        stage = "schema"
        normalized_events = normalize_house_ptr(parsed, observed_at=observed_at)
        if not normalized_events:
            raise CongressSchemaError(
                f"House PTR produced no normalized events for DocID {doc_id}"
            )
        stage = "persistence"
        persist_result = persist_event_batch(
            session,
            raw_event=raw_event,
            normalized_events=normalized_events,
        )
    except Exception as error:
        if stage != "persistence":
            try:
                persist_event_batch(
                    session,
                    raw_event=raw_event,
                    normalized_events=[],
                )
            except Exception as evidence_error:
                error = evidence_error
                stage = "persistence"
        if record_outcome:
            finished_at = _utc_now()
            run = record_collector_outcome(
                session,
                collector="congress",
                started_at=started_at,
                finished_at=finished_at,
                status="error",
                failure_kind=stage,
                records_observed=1,
                records_normalized=len(normalized_events),
                error=error,
                details={"chamber": "house", "doc_id": doc_id},
            )
            refresh_source_health(
                session,
                policy=CONGRESS_POLICY,
                run=run,
                checked_at=finished_at,
            )
        if not record_outcome:
            raise CongressIngestionStageError(stage, error) from error
        raise error

    run_id = None
    if record_outcome:
        finished_at = _utc_now()
        run = record_collector_outcome(
            session,
            collector="congress",
            started_at=started_at,
            finished_at=finished_at,
            status="success",
            failure_kind=None,
            records_observed=1,
            records_normalized=len(normalized_events),
            records_persisted=persist_result.normalized_inserted,
            details={"chamber": "house", "doc_id": doc_id},
        )
        refresh_source_health(
            session,
            policy=CONGRESS_POLICY,
            run=run,
            checked_at=finished_at,
        )
        run_id = run.id

    return CongressIngestionResult(
        raw_inserted=persist_result.raw_inserted,
        normalized_inserted=persist_result.normalized_inserted,
        normalized_observed=len(normalized_events),
        warning_events=sum(
            event["quality_status"] == "warning" for event in normalized_events
        ),
        run_id=run_id,
    )
