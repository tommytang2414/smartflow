"""Non-production SEC HTTP adapter with explicit operational failure taxonomy."""

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from smartflow.health import SourceHealthPolicy
from smartflow.ingestion.sec import (
    SOURCE_POLICIES,
    SECIngestionResult,
    ingest_form4_xml,
    ingest_form144_xml,
)
from smartflow.outcomes import record_collector_outcome, refresh_source_health


class SECAuthenticationError(RuntimeError):
    pass


class SECSourceError(RuntimeError):
    pass


def fetch_sec_xml(
    http_session: Any,
    *,
    url: str,
    user_agent: str,
    timeout_seconds: float = 30,
) -> tuple[str, int]:
    """Fetch SEC XML and classify HTTP failures before parsing."""
    if not user_agent.strip():
        raise SECAuthenticationError("SEC User-Agent contact identity is required")
    try:
        response = http_session.get(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=timeout_seconds,
        )
    except Exception as error:
        raise SECSourceError(f"SEC request failed: {error}") from error

    status_code = int(response.status_code)
    if status_code in {401, 403}:
        raise SECAuthenticationError(f"SEC returned HTTP {status_code}")
    if status_code < 200 or status_code >= 300:
        raise SECSourceError(f"SEC returned HTTP {status_code}")
    return response.text, status_code


def _record_fetch_failure(
    session: Session,
    *,
    policy: SourceHealthPolicy,
    started_at: datetime,
    error: Exception,
) -> None:
    finished_at = datetime.now(timezone.utc)
    failure_kind = "auth" if isinstance(error, SECAuthenticationError) else "source"
    run = record_collector_outcome(
        session,
        collector=policy.source,
        started_at=started_at,
        finished_at=finished_at,
        status="error",
        failure_kind=failure_kind,
        error=error,
    )
    refresh_source_health(
        session,
        policy=policy,
        run=run,
        checked_at=finished_at,
    )


def _ingest_sec_url(
    session: Session,
    *,
    source: str,
    http_session: Any,
    url: str,
    user_agent: str,
    accession: str,
    filed_at: datetime | None,
    observed_at: datetime,
    ingest_xml: Callable[..., SECIngestionResult],
    ingest_kwargs: dict | None = None,
) -> SECIngestionResult:
    started_at = datetime.now(timezone.utc)
    try:
        xml_content, http_status = fetch_sec_xml(
            http_session,
            url=url,
            user_agent=user_agent,
        )
    except (SECAuthenticationError, SECSourceError) as error:
        _record_fetch_failure(
            session,
            policy=SOURCE_POLICIES[source],
            started_at=started_at,
            error=error,
        )
        raise

    return ingest_xml(
        session,
        xml_content=xml_content,
        accession=accession,
        source_url=url,
        filed_at=filed_at,
        observed_at=observed_at,
        http_status=http_status,
        **(ingest_kwargs or {}),
    )


def ingest_form4_url(
    session: Session,
    *,
    http_session: Any,
    url: str,
    user_agent: str,
    accession: str,
    filed_at: datetime | None,
    observed_at: datetime,
) -> SECIngestionResult:
    return _ingest_sec_url(
        session,
        source="sec_form4",
        http_session=http_session,
        url=url,
        user_agent=user_agent,
        accession=accession,
        filed_at=filed_at,
        observed_at=observed_at,
        ingest_xml=ingest_form4_xml,
    )


def ingest_form144_url(
    session: Session,
    *,
    http_session: Any,
    url: str,
    user_agent: str,
    accession: str,
    filed_at: datetime | None,
    observed_at: datetime,
    cik_ticker_cache: dict[str, str] | None = None,
) -> SECIngestionResult:
    return _ingest_sec_url(
        session,
        source="sec_form144",
        http_session=http_session,
        url=url,
        user_agent=user_agent,
        accession=accession,
        filed_at=filed_at,
        observed_at=observed_at,
        ingest_xml=ingest_form144_xml,
        ingest_kwargs={"cik_ticker_cache": cik_ticker_cache},
    )
