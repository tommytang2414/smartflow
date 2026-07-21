"""Transactional, idempotent persistence for raw and normalized v2 evidence."""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import NormalizedEventV2, RawEvent


class EvidenceConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class BatchPersistResult:
    raw_inserted: int
    normalized_inserted: int


def persist_event_batch(
    session: Session,
    *,
    raw_event: Mapping[str, Any],
    normalized_events: Sequence[Mapping[str, Any]],
) -> BatchPersistResult:
    """Persist one raw payload and all derived events in a single transaction."""
    source = str(raw_event.get("source", "")).strip()
    raw_source_event_id = str(raw_event.get("source_event_id", "")).strip()
    incoming_hash = str(raw_event.get("payload_sha256", "")).strip()
    if not source or not raw_source_event_id or not incoming_hash:
        raise ValueError("raw source, source_event_id, and payload_sha256 are required")

    seen_normalized_keys: set[tuple[str, str]] = set()
    for event in normalized_events:
        if event.get("source") != source:
            raise ValueError("normalized event source must match raw event source")
        if "raw_event_id" in event:
            raise ValueError("raw_event_id is assigned by the repository")
        key = (str(event.get("source_event_id", "")), str(event.get("parser_version", "")))
        if not all(key):
            raise ValueError("normalized source_event_id and parser_version are required")
        if key in seen_normalized_keys:
            raise ValueError(f"duplicate normalized event in batch: {key}")
        seen_normalized_keys.add(key)

    try:
        stored_raw = session.scalar(
            select(RawEvent).where(
                RawEvent.source == source,
                RawEvent.source_event_id == raw_source_event_id,
            )
        )
        raw_inserted = 0
        if stored_raw is None:
            stored_raw = RawEvent(**raw_event)
            session.add(stored_raw)
            session.flush()
            raw_inserted = 1
        elif stored_raw.payload_sha256 != incoming_hash:
            raise EvidenceConflictError(
                f"raw evidence changed for {source}:{raw_source_event_id}"
            )

        normalized_inserted = 0
        for event in normalized_events:
            stored_event = session.scalar(
                select(NormalizedEventV2).where(
                    NormalizedEventV2.source == source,
                    NormalizedEventV2.source_event_id == event["source_event_id"],
                    NormalizedEventV2.parser_version == event["parser_version"],
                )
            )
            if stored_event is not None:
                if stored_event.raw_event_id != stored_raw.id:
                    raise EvidenceConflictError(
                        f"normalized identity belongs to different raw evidence: "
                        f"{source}:{event['source_event_id']}:{event['parser_version']}"
                    )
                continue

            session.add(NormalizedEventV2(raw_event_id=stored_raw.id, **event))
            normalized_inserted += 1

        session.commit()
        return BatchPersistResult(
            raw_inserted=raw_inserted,
            normalized_inserted=normalized_inserted,
        )
    except Exception:
        session.rollback()
        raise
