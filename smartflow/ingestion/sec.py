"""End-to-end SEC XML ingestion into v2 evidence and health records."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from smartflow.db.v2_repository import BatchPersistResult, persist_event_batch
from smartflow.events import payload_sha256
from smartflow.health import SourceHealthPolicy
from smartflow.normalizers.sec import normalize_form4, normalize_form144
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.edgar_xml import parse_form4_xml
from smartflow.parsers.form144_xml import parse_form144_xml


class SECParserError(ValueError):
    pass


class SECSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class SECIngestionResult:
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    run_id: int


SOURCE_POLICIES = {
    "sec_form4": SourceHealthPolicy("sec_form4", 300, 900),
    "sec_form144": SourceHealthPolicy("sec_form144", 3600, 10800),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ingest_sec_xml(
    session: Session,
    *,
    source: str,
    xml_content: str,
    accession: str,
    source_url: str,
    filed_at: datetime | None,
    observed_at: datetime,
    http_status: int,
    parse: Callable[[str], dict[str, Any] | None],
    normalize: Callable[..., list[dict[str, Any]]],
) -> SECIngestionResult:
    if not accession.strip():
        raise ValueError("SEC accession is required")

    started_at = _utc_now()
    raw_payload = {"content_type": "application/xml", "xml": xml_content}
    raw_event = {
        "source": source,
        "source_event_id": accession,
        "source_url": source_url,
        "payload": raw_payload,
        "payload_sha256": payload_sha256(raw_payload),
        "http_status": http_status,
        "retrieved_at": observed_at,
    }

    normalized_events: list[dict[str, Any]] = []
    persist_result = BatchPersistResult(0, 0)
    stage = "parser"
    try:
        parsed = parse(xml_content)
        if parsed is None:
            raise SECParserError(f"{source} parser rejected accession {accession}")

        stage = "schema"
        normalized_events = normalize(
            parsed,
            accession=accession,
            filed_at=filed_at,
            observed_at=observed_at,
            source_url=source_url,
        )
        if not normalized_events:
            raise SECSchemaError(f"{source} produced no normalized events for {accession}")

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
            collector=source,
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
            policy=SOURCE_POLICIES[source],
            run=run,
            checked_at=finished_at,
        )
        raise

    finished_at = _utc_now()
    run = record_collector_outcome(
        session,
        collector=source,
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
        policy=SOURCE_POLICIES[source],
        run=run,
        checked_at=finished_at,
    )
    return SECIngestionResult(
        raw_inserted=persist_result.raw_inserted,
        normalized_inserted=persist_result.normalized_inserted,
        normalized_observed=len(normalized_events),
        run_id=run.id,
    )


def ingest_form4_xml(
    session: Session,
    *,
    xml_content: str,
    accession: str,
    source_url: str,
    filed_at: datetime | None,
    observed_at: datetime,
    http_status: int = 200,
) -> SECIngestionResult:
    return _ingest_sec_xml(
        session,
        source="sec_form4",
        xml_content=xml_content,
        accession=accession,
        source_url=source_url,
        filed_at=filed_at,
        observed_at=observed_at,
        http_status=http_status,
        parse=parse_form4_xml,
        normalize=normalize_form4,
    )


def ingest_form144_xml(
    session: Session,
    *,
    xml_content: str,
    accession: str,
    source_url: str,
    filed_at: datetime | None,
    observed_at: datetime,
    http_status: int = 200,
    cik_ticker_cache: dict[str, str] | None = None,
) -> SECIngestionResult:
    def parse(content: str):
        return parse_form144_xml(content, cik_ticker_cache=cik_ticker_cache)

    return _ingest_sec_xml(
        session,
        source="sec_form144",
        xml_content=xml_content,
        accession=accession,
        source_url=source_url,
        filed_at=filed_at,
        observed_at=observed_at,
        http_status=http_status,
        parse=parse,
        normalize=normalize_form144,
    )
