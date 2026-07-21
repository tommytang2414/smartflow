"""Isolated v2 event schema; legacy tables are intentionally untouched."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class V2Base(DeclarativeBase):
    pass


class RawEvent(V2Base):
    """Immutable source payload plus retrieval evidence."""

    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_raw_event_source_id"),
        Index("ix_raw_events_source_retrieved", "source", "retrieved_at"),
        CheckConstraint(
            "http_status IS NULL OR (http_status >= 100 AND http_status <= 599)",
            name="ck_raw_events_http_status",
        ),
    )


class NormalizedEventV2(V2Base):
    """Source-specific interpretation linked back to immutable raw evidence."""

    __tablename__ = "normalized_events_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(64))
    side: Mapped[str | None] = mapped_column(String(16))
    execution_status: Mapped[str | None] = mapped_column(String(32))
    market: Mapped[str | None] = mapped_column(String(32))
    security_id: Mapped[str | None] = mapped_column(String(128))
    ticker: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(128))
    entity_name: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    currency: Mapped[str | None] = mapped_column(String(8))
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_event_id: Mapped[int] = mapped_column(
        ForeignKey("raw_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_event_id",
            "parser_version",
            name="uq_normalized_event_version",
        ),
        Index("ix_normalized_events_source_event_at", "source", "event_at"),
        Index("ix_normalized_events_ticker_event_at", "ticker", "event_at"),
        Index("ix_normalized_events_quality", "quality_status"),
        CheckConstraint(
            "quality_status IN ('valid', 'warning', 'invalid')",
            name="ck_normalized_events_quality",
        ),
    )


class CollectorRunV2(V2Base):
    """Collector outcome with empty success distinct from operational failure."""

    __tablename__ = "collector_runs_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collector: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_kind: Mapped[str | None] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    records_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_persisted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("ix_collector_runs_v2_collector_started", "collector", "started_at"),
        Index("ix_collector_runs_v2_status", "status"),
        CheckConstraint(
            "status IN ('success', 'empty', 'degraded', 'error', 'timeout')",
            name="ck_collector_runs_v2_status",
        ),
        CheckConstraint(
            "failure_kind IS NULL OR failure_kind IN "
            "('auth', 'schema', 'parser', 'source', 'timeout', 'persistence', 'internal')",
            name="ck_collector_runs_v2_failure_kind",
        ),
        CheckConstraint(
            "records_observed >= 0 AND records_normalized >= 0 AND records_persisted >= 0",
            name="ck_collector_runs_v2_nonnegative_counts",
        ),
        CheckConstraint(
            "(status IN ('success', 'empty') AND failure_kind IS NULL) OR "
            "(status IN ('degraded', 'error', 'timeout') AND failure_kind IS NOT NULL)",
            name="ck_collector_runs_v2_failure_consistency",
        ),
        CheckConstraint(
            "status != 'timeout' OR failure_kind = 'timeout'",
            name="ck_collector_runs_v2_timeout_kind",
        ),
    )


class SourceHealth(V2Base):
    """Current operational health derived from collector outcomes and freshness policy."""

    __tablename__ = "source_health"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    expected_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    freshness_sla_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    last_run_status: Mapped[str | None] = mapped_column(String(16))
    last_failure_kind: Mapped[str | None] = mapped_column(String(16))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        Index("ix_source_health_state", "state"),
        CheckConstraint(
            "expected_interval_seconds > 0 AND freshness_sla_seconds > 0",
            name="ck_source_health_positive_intervals",
        ),
        CheckConstraint(
            "state IN ('healthy', 'stale', 'degraded', 'unknown', 'disabled')",
            name="ck_source_health_state",
        ),
    )
