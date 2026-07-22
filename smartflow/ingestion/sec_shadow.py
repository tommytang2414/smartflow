"""Bounded SEC feed discovery and aggregate ingestion for the v2 shadow DB."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from lxml import etree
from sqlalchemy.orm import Session

from smartflow.db.v2_repository import EvidenceConflictError
from smartflow.ingestion.sec import (
    SOURCE_POLICIES,
    SECParserError,
    SECSchemaError,
    ingest_form4_xml,
    ingest_form144_xml,
)
from smartflow.ingestion.sec_live import SECAuthenticationError, SECSourceError
from smartflow.outcomes import record_collector_outcome, refresh_source_health
from smartflow.utils import RateLimiter


SEC_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ALLOWED_SEC_PATH_PREFIXES = ("/Archives/", "/cgi-bin/browse-edgar", "/files/")
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")
MAX_RESPONSE_BYTES = 10_000_000


class SECDiscoveryError(ValueError):
    pass


class SECMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class SECFilingReference:
    accession: str
    index_url: str
    filed_at: datetime


@dataclass(frozen=True)
class SECShadowRunResult:
    source: str
    status: str
    filings_observed: int
    raw_inserted: int
    normalized_observed: int
    normalized_inserted: int
    run_id: int


def _validate_sec_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.sec.gov"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or not any(parsed.path.startswith(prefix) for prefix in ALLOWED_SEC_PATH_PREFIXES)
    ):
        raise SECDiscoveryError("SEC URL is outside the approved HTTPS allowlist")
    return url


def build_sec_user_agent(contact_email: str) -> str:
    email = contact_email.strip()
    if not EMAIL_PATTERN.fullmatch(email) or any(ord(char) < 32 for char in email):
        raise SECAuthenticationError("valid SEC contact email is required")
    return f"SmartFlow/2.0 ({email})"


class SECClient:
    """Small SEC-only HTTP client with allowlisting, throttling, and size limits."""

    def __init__(
        self,
        http_session: Any,
        *,
        contact_email: str,
        timeout_seconds: float = 30,
    ):
        self.http_session = http_session
        self.user_agent = build_sec_user_agent(contact_email)
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = RateLimiter(2)

    def get_text(self, url: str) -> str:
        allowed_url = _validate_sec_url(url)
        self.rate_limiter.wait()
        try:
            response = self.http_session.get(
                allowed_url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
        except Exception as error:
            raise SECSourceError("SEC request failed") from error

        status_code = int(response.status_code)
        if status_code in {401, 403}:
            raise SECAuthenticationError(f"SEC returned HTTP {status_code}")
        if status_code < 200 or status_code >= 300:
            raise SECSourceError(f"SEC returned HTTP {status_code}")
        content = response.content
        if len(content) > MAX_RESPONSE_BYTES:
            raise SECSourceError("SEC response exceeded the 10 MB safety limit")
        return response.text

    def get_json(self, url: str) -> dict:
        try:
            payload = json.loads(self.get_text(url))
        except json.JSONDecodeError as error:
            raise SECMetadataError("SEC metadata response is not valid JSON") from error
        if not isinstance(payload, dict):
            raise SECMetadataError("SEC metadata response must be an object")
        return payload


def _feed_url(form_type: str) -> str:
    return f"{SEC_FEED_URL}?{urlencode({'action': 'getcurrent', 'type': form_type, 'owner': 'only', 'count': 100, 'output': 'atom'})}"


def parse_sec_atom_feed(
    xml_content: str,
    *,
    expected_form: str,
    limit: int,
) -> list[SECFilingReference]:
    if expected_form not in {"4", "144"}:
        raise ValueError(f"unsupported SEC form: {expected_form}")
    if limit < 1 or limit > 25:
        raise ValueError("SEC filing limit must be between 1 and 25")
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
        root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    except (ValueError, etree.XMLSyntaxError) as error:
        raise SECDiscoveryError("SEC Atom feed is malformed") from error

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    filings = []
    seen_accessions = set()
    for entry in root.findall("atom:entry", namespace):
        category = entry.find("atom:category", namespace)
        if category is None or category.get("term") != expected_form:
            continue
        entry_id = entry.findtext("atom:id", default="", namespaces=namespace)
        accession = entry_id.rsplit("accession-number=", 1)[-1].strip()
        if not ACCESSION_PATTERN.fullmatch(accession):
            raise SECDiscoveryError("SEC feed contains an invalid accession")
        if accession in seen_accessions:
            continue
        link = entry.find("atom:link[@rel='alternate']", namespace)
        index_url = link.get("href", "") if link is not None else ""
        _validate_sec_url(index_url)

        summary = entry.findtext("atom:summary", default="", namespaces=namespace)
        filed_match = re.search(r"Filed:</b>\s*(\d{4}-\d{2}-\d{2})", summary)
        if filed_match:
            filed_at = datetime.strptime(filed_match.group(1), "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        else:
            updated = entry.findtext("atom:updated", default="", namespaces=namespace)
            try:
                filed_at = datetime.fromisoformat(updated).astimezone(timezone.utc)
            except ValueError as error:
                raise SECDiscoveryError("SEC feed entry has no valid filing time") from error

        filings.append(SECFilingReference(accession, index_url, filed_at))
        seen_accessions.add(accession)
        if len(filings) == limit:
            break
    return filings


def resolve_primary_xml_url(index_html: str, *, index_url: str, form_type: str) -> str:
    soup = BeautifulSoup(index_html, "lxml")
    candidates = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4 or cells[3].get_text(strip=True) != form_type:
            continue
        link = cells[2].find("a", href=True)
        if link is None:
            continue
        candidate = urljoin(index_url, link["href"])
        path = urlparse(candidate).path.casefold()
        if path.endswith(".xml") and "/xsl" not in path:
            candidates.append(_validate_sec_url(candidate))
    if len(candidates) != 1:
        raise SECDiscoveryError(
            f"SEC filing index yielded {len(candidates)} raw {form_type} XML documents"
        )
    return candidates[0]


def build_cik_ticker_cache(payload: dict) -> dict[str, str]:
    cache = {}
    for record in payload.values():
        if not isinstance(record, dict):
            raise SECMetadataError("SEC ticker metadata contains a non-object record")
        cik = record.get("cik_str")
        ticker = record.get("ticker")
        if not isinstance(cik, int) or not isinstance(ticker, str) or not ticker.strip():
            raise SECMetadataError("SEC ticker metadata record is incomplete")
        cache[str(cik)] = ticker.strip().upper()
    if not cache:
        raise SECMetadataError("SEC ticker metadata is empty")
    return cache


def _failure_kind(error: Exception) -> str:
    if isinstance(error, SECAuthenticationError):
        return "auth"
    if isinstance(error, SECSourceError):
        return "source"
    if isinstance(error, (SECDiscoveryError, SECParserError)):
        return "parser"
    if isinstance(error, (SECMetadataError, SECSchemaError, ValueError)):
        return "schema"
    if isinstance(error, EvidenceConflictError):
        return "persistence"
    return "internal"


def run_sec_shadow_source(
    session: Session,
    *,
    source: str,
    limit: int,
    contact_email: str | None = None,
    http_session: Any | None = None,
    client: Any | None = None,
    observed_at: datetime | None = None,
) -> SECShadowRunResult:
    """Run one bounded source and record one aggregate operational outcome."""
    source_specs = {
        "sec_form4": ("4", ingest_form4_xml),
        "sec_form144": ("144", ingest_form144_xml),
    }
    if source not in source_specs:
        raise ValueError(f"unsupported SEC source: {source}")
    form_type, ingest_xml = source_specs[source]
    started_at = datetime.now(timezone.utc)
    observed_at = observed_at or started_at
    raw_inserted = 0
    normalized_observed = 0
    normalized_inserted = 0
    selected_filings = 0

    try:
        active_client = client or SECClient(
            http_session,
            contact_email=contact_email or "",
        )
        feed_content = active_client.get_text(_feed_url(form_type))
        filings = parse_sec_atom_feed(
            feed_content,
            expected_form=form_type,
            limit=limit,
        )
        selected_filings = len(filings)
        ticker_cache = None
        if source == "sec_form144" and filings:
            ticker_cache = build_cik_ticker_cache(active_client.get_json(SEC_TICKERS_URL))

        for filing in filings:
            index_html = active_client.get_text(filing.index_url)
            xml_url = resolve_primary_xml_url(
                index_html,
                index_url=filing.index_url,
                form_type=form_type,
            )
            xml_content = active_client.get_text(xml_url)
            arguments = {
                "xml_content": xml_content,
                "accession": filing.accession,
                "source_url": xml_url,
                "filed_at": filing.filed_at,
                "observed_at": observed_at,
                "http_status": 200,
                "record_outcome": False,
            }
            if ticker_cache is not None:
                arguments["cik_ticker_cache"] = ticker_cache
            result = ingest_xml(session, **arguments)
            raw_inserted += result.raw_inserted
            normalized_observed += result.normalized_observed
            normalized_inserted += result.normalized_inserted
    except Exception as error:
        finished_at = datetime.now(timezone.utc)
        run = record_collector_outcome(
            session,
            collector=source,
            started_at=started_at,
            finished_at=finished_at,
            status="error",
            failure_kind=_failure_kind(error),
            records_observed=selected_filings,
            records_normalized=normalized_observed,
            records_persisted=normalized_inserted,
            error=error,
            details={
                "mode": "v2_shadow",
                "limit": limit,
                "raw_inserted": raw_inserted,
            },
        )
        refresh_source_health(
            session,
            policy=SOURCE_POLICIES[source],
            run=run,
            checked_at=finished_at,
        )
        raise

    finished_at = datetime.now(timezone.utc)
    status = "success" if selected_filings else "empty"
    run = record_collector_outcome(
        session,
        collector=source,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        failure_kind=None,
        records_observed=selected_filings,
        records_normalized=normalized_observed,
        records_persisted=normalized_inserted,
        details={
            "mode": "v2_shadow",
            "limit": limit,
            "raw_inserted": raw_inserted,
        },
    )
    refresh_source_health(
        session,
        policy=SOURCE_POLICIES[source],
        run=run,
        checked_at=finished_at,
    )
    return SECShadowRunResult(
        source=source,
        status=status,
        filings_observed=selected_filings,
        raw_inserted=raw_inserted,
        normalized_observed=normalized_observed,
        normalized_inserted=normalized_inserted,
        run_id=run.id,
    )
