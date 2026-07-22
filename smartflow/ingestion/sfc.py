"""Offline SFC weekly CSV ingestion into v2 evidence and health records."""

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from smartflow.db.v2_repository import BatchPersistResult, persist_event_batch
from smartflow.events import make_source_event_id, payload_sha256
from smartflow.health import SourceHealthPolicy
from smartflow.normalizers.sfc import normalize_sfc_short_report
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.sfc_short_csv import parse_sfc_short_csv


SFC_SHORT_POLICY = SourceHealthPolicy(
    source="sfc_short",
    expected_interval_seconds=7 * 24 * 60 * 60,
    freshness_sla_seconds=10 * 24 * 60 * 60,
    event_freshness_sla_seconds=10 * 24 * 60 * 60,
)


@dataclass(frozen=True)
class SFCShortIngestionResult:
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    run_id: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ingest_sfc_short_csv(
    session: Session,
    *,
    csv_content: str,
    source_url: str,
    published_at: datetime | None,
    observed_at: datetime,
    http_status: int = 200,
    expected_reporting_date: date | None = None,
    started_at: datetime | None = None,
) -> SFCShortIngestionResult:
    """Persist one complete weekly SFC report as immutable raw evidence."""
    started_at = started_at or _utc_now()
    raw_payload = {"content_type": "text/csv", "csv": csv_content}
    raw_event = {
        "source": "sfc_short",
        "source_event_id": make_source_event_id(
            "sfc_short_rejected", payload_sha256(raw_payload)
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
        parsed = parse_sfc_short_csv(csv_content)
        if (
            expected_reporting_date is not None
            and parsed["reporting_date"] != expected_reporting_date
        ):
            raise ValueError(
                "SFC CSV reporting date does not match its dated archive link: "
                f"{parsed['reporting_date']} != {expected_reporting_date}"
            )
        raw_source_event_id = make_source_event_id(
            "sfc_short_report", parsed["reporting_date"].isoformat()
        )
        raw_event["source_event_id"] = raw_source_event_id

        stage = "schema"
        normalized_events = normalize_sfc_short_report(
            parsed,
            published_at=published_at,
            observed_at=observed_at,
            source_url=source_url,
        )
        if not normalized_events:
            raise ValueError("SFC short-position report produced no normalized events")

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
            collector="sfc_short",
            started_at=started_at,
            finished_at=finished_at,
            status="error",
            failure_kind=stage,
            records_observed=1,
            records_normalized=len(normalized_events),
            records_persisted=0,
            error=error,
        )
        refresh_source_health(
            session,
            policy=SFC_SHORT_POLICY,
            run=run,
            checked_at=finished_at,
        )
        raise

    finished_at = _utc_now()
    run = record_collector_outcome(
        session,
        collector="sfc_short",
        started_at=started_at,
        finished_at=finished_at,
        status="success",
        failure_kind=None,
        records_observed=len(normalized_events),
        records_normalized=len(normalized_events),
        records_persisted=persist_result.normalized_inserted,
    )
    refresh_source_health(
        session,
        policy=SFC_SHORT_POLICY,
        run=run,
        checked_at=finished_at,
    )
    return SFCShortIngestionResult(
        raw_inserted=persist_result.raw_inserted,
        normalized_inserted=persist_result.normalized_inserted,
        normalized_observed=len(normalized_events),
        run_id=run.id,
    )
