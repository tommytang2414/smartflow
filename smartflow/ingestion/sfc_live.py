"""Read-only SFC index discovery and latest-report ingestion adapter."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from smartflow.db.v2_repository import persist_event_batch
from smartflow.events import make_source_event_id, payload_sha256
from smartflow.ingestion.sfc import (
    SFC_SHORT_POLICY,
    SFCShortIngestionResult,
    ingest_sfc_short_csv,
)
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.parsers.sfc_short_csv import SFCShortCSVError


SFC_SHORT_INDEX_URL = (
    "https://www.sfc.hk/en/Regulatory-functions/Market/Short-position-reporting/"
    "Aggregated-reportable-short-positions-of-specified-shares"
)
SFC_USER_AGENT = "SmartFlow research collector (tommytang.cc@gmail.com)"
_REPORT_PATH = re.compile(r"/spr/(\d{4})/(\d{2})/(\d{2})/[^?]+\.csv$", re.IGNORECASE)


class SFCSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SFCShortReportLink:
    reporting_date: date
    url: str


def _is_official_sfc_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname == "sfc.hk" or hostname.endswith(".sfc.hk")


def discover_sfc_short_csv_links(
    index_html: str,
    *,
    index_url: str = SFC_SHORT_INDEX_URL,
) -> list[SFCShortReportLink]:
    """Extract dated official CSV links from the SFC archive table."""
    links: dict[tuple[date, str], SFCShortReportLink] = {}
    soup = BeautifulSoup(index_html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        url = urljoin(index_url, anchor["href"])
        if not _is_official_sfc_url(url):
            continue
        match = _REPORT_PATH.search(urlparse(url).path)
        if match is None:
            continue
        try:
            reporting_date = date(*(int(part) for part in match.groups()))
        except ValueError as error:
            raise SFCShortCSVError(f"invalid dated SFC CSV link: {url}") from error
        link = SFCShortReportLink(reporting_date=reporting_date, url=url)
        links[(reporting_date, url)] = link

    if not links:
        raise SFCShortCSVError("SFC index contains no dated official CSV links")
    return sorted(links.values(), key=lambda link: (link.reporting_date, link.url), reverse=True)


def _fetch_text(http_session: Any, *, url: str, timeout_seconds: float = 30) -> str:
    try:
        response = http_session.get(
            url,
            headers={"User-Agent": SFC_USER_AGENT},
            timeout=timeout_seconds,
        )
    except Exception as error:
        raise SFCSourceError(f"SFC request failed: {error}") from error
    status_code = int(response.status_code)
    if status_code < 200 or status_code >= 300:
        raise SFCSourceError(f"SFC returned HTTP {status_code}")
    return response.text


def _record_failure(
    session: Session,
    *,
    started_at: datetime,
    failure_kind: str,
    error: Exception,
) -> None:
    finished_at = datetime.now(timezone.utc)
    run = record_collector_outcome(
        session,
        collector="sfc_short",
        started_at=started_at,
        finished_at=finished_at,
        status="error",
        failure_kind=failure_kind,
        error=error,
    )
    refresh_source_health(
        session,
        policy=SFC_SHORT_POLICY,
        run=run,
        checked_at=finished_at,
    )


def ingest_latest_sfc_short_report(
    session: Session,
    *,
    http_session: Any,
    observed_at: datetime,
    index_url: str = SFC_SHORT_INDEX_URL,
) -> tuple[SFCShortReportLink, SFCShortIngestionResult]:
    """Discover and ingest the newest dated report without guessing its URL."""
    started_at = datetime.now(timezone.utc)
    try:
        index_html = _fetch_text(http_session, url=index_url)
    except SFCSourceError as error:
        _record_failure(
            session,
            started_at=started_at,
            failure_kind="source",
            error=error,
        )
        raise

    try:
        latest = discover_sfc_short_csv_links(index_html, index_url=index_url)[0]
    except SFCShortCSVError as error:
        raw_payload = {"content_type": "text/html", "html": index_html}
        persist_event_batch(
            session,
            raw_event={
                "source": "sfc_short",
                "source_event_id": make_source_event_id(
                    "sfc_short_index_rejected", payload_sha256(raw_payload)
                ),
                "source_url": index_url,
                "payload": raw_payload,
                "payload_sha256": payload_sha256(raw_payload),
                "http_status": 200,
                "retrieved_at": observed_at,
            },
            normalized_events=[],
        )
        _record_failure(
            session,
            started_at=started_at,
            failure_kind="parser",
            error=error,
        )
        raise

    try:
        csv_content = _fetch_text(http_session, url=latest.url)
    except SFCSourceError as error:
        _record_failure(
            session,
            started_at=started_at,
            failure_kind="source",
            error=error,
        )
        raise

    result = ingest_sfc_short_csv(
        session,
        csv_content=csv_content,
        source_url=latest.url,
        published_at=None,
        observed_at=observed_at,
        expected_reporting_date=latest.reporting_date,
        started_at=started_at,
    )
    return latest, result
