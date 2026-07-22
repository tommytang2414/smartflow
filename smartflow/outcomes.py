"""Structured v2 collector outcomes and source-health refresh."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2
from smartflow.health import (
    SourceHealthPolicy,
    evaluate_source_health,
    record_source_health,
)


def record_collector_outcome(
    session: Session,
    *,
    collector: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    failure_kind: str | None,
    records_observed: int = 0,
    records_normalized: int = 0,
    records_persisted: int = 0,
    error: Exception | None = None,
    details: dict | None = None,
) -> CollectorRunV2:
    run = CollectorRunV2(
        collector=collector,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        failure_kind=failure_kind,
        error_code=type(error).__name__ if error else None,
        error_message=str(error)[:500] if error else None,
        records_observed=records_observed,
        records_normalized=records_normalized,
        records_persisted=records_persisted,
        details=details,
    )
    session.add(run)
    session.commit()
    return run


def refresh_source_health(
    session: Session,
    *,
    policy: SourceHealthPolicy,
    run: CollectorRunV2,
    checked_at: datetime,
) -> None:
    last_success_at = session.scalar(
        select(func.max(CollectorRunV2.finished_at)).where(
            CollectorRunV2.collector == policy.source,
            CollectorRunV2.status.in_(("success", "empty")),
        )
    )
    last_event_at = session.scalar(
        select(func.max(NormalizedEventV2.event_at)).where(
            NormalizedEventV2.source == policy.source,
        )
    )
    assessment = evaluate_source_health(
        policy,
        checked_at=checked_at,
        last_run_status=run.status,
        last_run_at=run.finished_at,
        last_success_at=last_success_at,
        last_failure_kind=run.failure_kind,
    )
    record_source_health(
        session,
        policy=policy,
        assessment=assessment,
        last_run_status=run.status,
        last_failure_kind=run.failure_kind,
        last_run_at=run.finished_at,
        last_success_at=last_success_at,
        last_event_at=last_event_at,
    )


def record_timeout_outcome(
    session: Session,
    *,
    policy: SourceHealthPolicy,
    started_at: datetime,
    finished_at: datetime,
    timeout_seconds: float,
    error: TimeoutError,
) -> CollectorRunV2:
    run = record_collector_outcome(
        session,
        collector=policy.source,
        started_at=started_at,
        finished_at=finished_at,
        status="timeout",
        failure_kind="timeout",
        error=error,
        details={"timeout_seconds": timeout_seconds, "observer": "parent_process"},
    )
    refresh_source_health(session, policy=policy, run=run, checked_at=finished_at)
    return run
