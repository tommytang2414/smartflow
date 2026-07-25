"""Bounded official House PTR acquisition and aggregate v2 run semantics."""

from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from smartflow.db.v2_repository import persist_event_batch
from smartflow.events import make_source_event_id, payload_sha256
from smartflow.ingestion.congress import (
    CONGRESS_POLICY,
    CongressIngestionStageError,
    CongressIngestionResult,
    ingest_house_ptr_pdf,
)
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.congress_house import (
    HOUSE_INDEX_URL,
    HouseDisclosureError,
    parse_house_index_xml,
)


HOUSE_HOST = "disclosures-clerk.house.gov"
HOUSE_USER_AGENT = "SmartFlow personal research (tommytang.cc@gmail.com)"
MAX_HOUSE_INDEX_BYTES = 2 * 1024 * 1024
MAX_HOUSE_INDEX_XML_BYTES = 10 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
CONTENT_TYPES = {
    "index": {
        "application/x-zip-compressed",
        "application/zip",
        "application/octet-stream",
    },
    "pdf": {
        "application/pdf",
        "application/octet-stream",
    },
}


class HouseSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HouseBatchResult:
    reports_observed: int
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    warning_events: int
    run_id: int


def _official_house_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == HOUSE_HOST


def fetch_house_bytes(
    http_session: Any,
    *,
    url: str,
    expected_kind: str,
    timeout_seconds: float = 30,
) -> bytes:
    """Fetch one exact official object without redirects or unbounded bodies."""
    if not _official_house_url(url):
        raise HouseSourceError(f"non-official House URL rejected: {url}")
    if expected_kind not in {"index", "pdf"}:
        raise ValueError(f"unsupported House payload kind: {expected_kind}")
    try:
        response = http_session.get(
            url,
            headers={"User-Agent": HOUSE_USER_AGENT},
            timeout=timeout_seconds,
            allow_redirects=False,
            stream=True,
        )
    except Exception as error:
        raise HouseSourceError(f"House request failed: {error}") from error
    status = int(response.status_code)
    if 300 <= status < 400:
        raise HouseSourceError(f"House redirect rejected: HTTP {status}")
    if status < 200 or status >= 300:
        raise HouseSourceError(f"House returned HTTP {status}")
    maximum = (
        MAX_HOUSE_INDEX_BYTES
        if expected_kind == "index"
        else 10 * 1024 * 1024
    )
    content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
    if content_type not in CONTENT_TYPES[expected_kind]:
        raise HouseSourceError(
            f"House {expected_kind} content type is invalid: {content_type or 'missing'}"
        )
    content_length = str(response.headers.get("Content-Length", "")).strip()
    if content_length:
        try:
            if int(content_length) <= 0 or int(content_length) > maximum:
                raise HouseSourceError(
                    f"House {expected_kind} payload size is invalid"
                )
        except ValueError as error:
            raise HouseSourceError(
                f"House {expected_kind} Content-Length is invalid"
            ) from error
    chunks = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=READ_CHUNK_BYTES):
            if not chunk:
                continue
            total += len(chunk)
            if total > maximum:
                raise HouseSourceError(
                    f"House {expected_kind} payload size is invalid"
                )
            chunks.append(bytes(chunk))
    except HouseSourceError:
        raise
    except Exception as error:
        raise HouseSourceError(f"House response read failed: {error}") from error
    payload = b"".join(chunks)
    if not payload or len(payload) > maximum:
        raise HouseSourceError(f"House {expected_kind} payload size is invalid")
    if expected_kind == "index" and not payload.startswith(b"PK"):
        raise HouseSourceError("House index payload is not a ZIP archive")
    if expected_kind == "pdf" and not payload.startswith(b"%PDF-"):
        raise HouseSourceError("House PTR payload is not a PDF")
    return payload


def parse_house_index_zip(payload: bytes, *, year: int) -> list[dict]:
    """Read only the exact official index member and reject archive expansion."""
    expected_name = f"{year}FD.xml"
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            if expected_name not in names:
                raise HouseDisclosureError(
                    f"House index archive is missing {expected_name}"
                )
            info = archive.getinfo(expected_name)
            if info.file_size <= 0 or info.file_size > MAX_HOUSE_INDEX_XML_BYTES:
                raise HouseDisclosureError("House index XML size is invalid")
            xml_content = archive.read(expected_name).decode("utf-8-sig")
    except (zipfile.BadZipFile, UnicodeDecodeError) as error:
        raise HouseDisclosureError("invalid House index ZIP archive") from error
    return parse_house_index_xml(xml_content, expected_year=year)


def _preserve_rejected_index(
    session: Session,
    *,
    payload: bytes,
    url: str,
    observed_at: datetime,
) -> None:
    raw_payload = {
        "content_type": "application/zip",
        "encoding": "base64",
        "body_base64": base64.b64encode(payload).decode("ascii"),
    }
    persist_event_batch(
        session,
        raw_event={
            "source": "congress",
            "source_event_id": make_source_event_id(
                "congress_house_index_rejected",
                payload_sha256(raw_payload),
            ),
            "source_url": url,
            "payload": raw_payload,
            "payload_sha256": payload_sha256(raw_payload),
            "http_status": 200,
            "retrieved_at": observed_at,
        },
        normalized_events=[],
    )


def _record_batch(
    session: Session,
    *,
    started_at: datetime,
    status: str,
    failure_kind: str | None,
    observed_at: datetime,
    reports_observed: int,
    normalized_observed: int,
    normalized_inserted: int,
    warning_events: int,
    error: Exception | None = None,
):
    run = record_collector_outcome(
        session,
        collector="congress",
        started_at=started_at,
        finished_at=observed_at,
        status=status,
        failure_kind=failure_kind,
        records_observed=reports_observed,
        records_normalized=normalized_observed,
        records_persisted=normalized_inserted,
        error=error,
        details={"chamber": "house", "warning_events": warning_events},
    )
    refresh_source_health(
        session,
        policy=CONGRESS_POLICY,
        run=run,
        checked_at=observed_at,
    )
    return run


def ingest_house_ptr_batch(
    session: Session,
    *,
    http_session: Any,
    observed_at: datetime,
    year: int,
    max_reports: int = 25,
) -> HouseBatchResult:
    """Fetch and ingest a bounded newest-first House PTR batch."""
    if max_reports <= 0 or max_reports > 100:
        raise ValueError("max_reports must be between 1 and 100")
    started_at = datetime.now(timezone.utc)
    index_url = HOUSE_INDEX_URL.format(year=year)
    reports_observed = 0
    raw_inserted = 0
    normalized_inserted = 0
    normalized_observed = 0
    warning_events = 0
    failure_kind = "source"
    try:
        index_payload = fetch_house_bytes(
            http_session,
            url=index_url,
            expected_kind="index",
        )
        failure_kind = "parser"
        try:
            reports = parse_house_index_zip(index_payload, year=year)
        except HouseDisclosureError:
            _preserve_rejected_index(
                session,
                payload=index_payload,
                url=index_url,
                observed_at=observed_at,
            )
            raise
        selected = sorted(
            reports,
            key=lambda report: (report["filing_date"], report["doc_id"]),
            reverse=True,
        )[:max_reports]
        for report in selected:
            reports_observed += 1
            failure_kind = "source"
            pdf_content = fetch_house_bytes(
                http_session,
                url=report["source_url"],
                expected_kind="pdf",
            )
            failure_kind = "parser"
            result: CongressIngestionResult = ingest_house_ptr_pdf(
                session,
                pdf_content=pdf_content,
                report=report,
                observed_at=observed_at,
                record_outcome=False,
            )
            raw_inserted += result.raw_inserted
            normalized_inserted += result.normalized_inserted
            normalized_observed += result.normalized_observed
            warning_events += result.warning_events
        run = _record_batch(
            session,
            started_at=started_at,
            status="success",
            failure_kind=None,
            observed_at=observed_at,
            reports_observed=reports_observed,
            normalized_observed=normalized_observed,
            normalized_inserted=normalized_inserted,
            warning_events=warning_events,
        )
    except Exception as error:
        if isinstance(error, CongressIngestionStageError):
            failure_kind = error.failure_kind
        _record_batch(
            session,
            started_at=started_at,
            status="error",
            failure_kind=failure_kind,
            observed_at=observed_at,
            reports_observed=reports_observed,
            normalized_observed=normalized_observed,
            normalized_inserted=normalized_inserted,
            warning_events=warning_events,
            error=error,
        )
        raise

    return HouseBatchResult(
        reports_observed=reports_observed,
        raw_inserted=raw_inserted,
        normalized_inserted=normalized_inserted,
        normalized_observed=normalized_observed,
        warning_events=warning_events,
        run_id=run.id,
    )
