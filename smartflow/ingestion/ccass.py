"""Offline CCASS structured-snapshot ingestion into v2 evidence."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from smartflow.db.v2_repository import BatchPersistResult, persist_event_batch
from smartflow.events import make_source_event_id, payload_sha256
from smartflow.health import SourceHealthPolicy
from smartflow.normalizers.ccass import normalize_ccass_snapshot
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.ccass import parse_ccass_snapshot


CCASS_POLICY = SourceHealthPolicy(
    source="hkex_ccass",
    expected_interval_seconds=24 * 60 * 60,
    freshness_sla_seconds=3 * 24 * 60 * 60,
    event_freshness_sla_seconds=4 * 24 * 60 * 60,
)


@dataclass(frozen=True)
class CCASSIngestionResult:
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    run_id: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ingest_ccass_snapshot(
    session: Session,
    *,
    payload: dict,
    source_url: str,
    observed_at: datetime,
    http_status: int | None = None,
) -> CCASSIngestionResult:
    """Persist one stock/date snapshot supplied through an approved data route."""
    started_at = _utc_now()
    raw_payload = {"content_type": "application/json", "snapshot": payload}
    raw_event = {
        "source": "hkex_ccass",
        "source_event_id": make_source_event_id(
            "hkex_ccass_rejected", payload_sha256(raw_payload)
        ),
        "source_url": source_url,
        "payload": raw_payload,
        "payload_sha256": payload_sha256(raw_payload),
        "http_status": http_status,
        "retrieved_at": observed_at,
    }
    normalized_events: list[dict] = []
    persist_result = BatchPersistResult(0, 0)
    stage = "parser"
    try:
        parsed = parse_ccass_snapshot(payload)
        raw_event["source_event_id"] = make_source_event_id(
            "hkex_ccass_snapshot",
            parsed["holding_date"].isoformat(),
            parsed["stock_code"],
        )
        stage = "schema"
        normalized_events = normalize_ccass_snapshot(
            parsed,
            observed_at=observed_at,
            source_url=source_url,
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
                persist_event_batch(session, raw_event=raw_event, normalized_events=[])
            except Exception as evidence_error:
                error = evidence_error
                stage = "persistence"
        finished_at = _utc_now()
        run = record_collector_outcome(
            session,
            collector="hkex_ccass",
            started_at=started_at,
            finished_at=finished_at,
            status="error",
            failure_kind=stage,
            records_observed=1,
            records_normalized=len(normalized_events),
            error=error,
        )
        refresh_source_health(
            session,
            policy=CCASS_POLICY,
            run=run,
            checked_at=finished_at,
        )
        raise

    finished_at = _utc_now()
    run = record_collector_outcome(
        session,
        collector="hkex_ccass",
        started_at=started_at,
        finished_at=finished_at,
        status="success",
        failure_kind=None,
        records_observed=1,
        records_normalized=len(normalized_events),
        records_persisted=persist_result.normalized_inserted,
    )
    refresh_source_health(
        session,
        policy=CCASS_POLICY,
        run=run,
        checked_at=finished_at,
    )
    return CCASSIngestionResult(
        raw_inserted=persist_result.raw_inserted,
        normalized_inserted=persist_result.normalized_inserted,
        normalized_observed=len(normalized_events),
        run_id=run.id,
    )
