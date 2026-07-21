"""Source freshness and operational-health evaluation."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import SourceHealth


FAILURE_STATUSES = {"degraded", "error", "timeout"}


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class SourceHealthPolicy:
    source: str
    expected_interval_seconds: int
    freshness_sla_seconds: int
    enabled: bool = True

    def __post_init__(self):
        if not self.source.strip():
            raise ValueError("source is required")
        if self.expected_interval_seconds <= 0 or self.freshness_sla_seconds <= 0:
            raise ValueError("health intervals must be positive")


@dataclass(frozen=True)
class HealthAssessment:
    state: str
    reason: str
    checked_at: datetime


def evaluate_source_health(
    policy: SourceHealthPolicy,
    *,
    checked_at: datetime,
    last_run_status: str | None,
    last_run_at: datetime | None,
    last_success_at: datetime | None,
    last_failure_kind: str | None = None,
) -> HealthAssessment:
    """Evaluate source availability; a successful empty run counts as operational."""
    checked_at = _ensure_utc(checked_at)
    last_run_at = _ensure_utc(last_run_at)
    last_success_at = _ensure_utc(last_success_at)

    if not policy.enabled:
        return HealthAssessment("disabled", "source_disabled", checked_at)
    if last_run_at is None or last_run_status is None:
        return HealthAssessment("unknown", "no_completed_run", checked_at)
    if last_run_status in FAILURE_STATUSES:
        reason = f"last_run_{last_run_status}"
        if last_failure_kind:
            reason = f"{reason}:{last_failure_kind}"
        return HealthAssessment("degraded", reason, checked_at)
    if last_run_status not in {"success", "empty"}:
        return HealthAssessment("unknown", f"unrecognized_run_status:{last_run_status}", checked_at)
    if last_success_at is None:
        return HealthAssessment("unknown", "successful_status_without_timestamp", checked_at)

    success_age_seconds = (checked_at - last_success_at).total_seconds()
    if success_age_seconds > policy.freshness_sla_seconds:
        return HealthAssessment("stale", "last_success_exceeded_sla", checked_at)
    return HealthAssessment("healthy", f"recent_{last_run_status}", checked_at)


def record_source_health(
    session: Session,
    *,
    policy: SourceHealthPolicy,
    assessment: HealthAssessment,
    last_run_status: str | None,
    last_failure_kind: str | None,
    last_run_at: datetime | None,
    last_success_at: datetime | None,
    last_event_at: datetime | None,
) -> SourceHealth:
    """Upsert current source health; health state is mutable operational metadata."""
    health = session.scalar(select(SourceHealth).where(SourceHealth.source == policy.source))
    if health is None:
        health = SourceHealth(source=policy.source)
        session.add(health)

    health.expected_interval_seconds = policy.expected_interval_seconds
    health.freshness_sla_seconds = policy.freshness_sla_seconds
    health.state = assessment.state
    health.reason = assessment.reason
    health.last_run_status = last_run_status
    health.last_failure_kind = last_failure_kind
    health.last_run_at = _ensure_utc(last_run_at)
    health.last_success_at = _ensure_utc(last_success_at)
    health.last_event_at = _ensure_utc(last_event_at)
    health.checked_at = assessment.checked_at
    session.commit()
    return health
