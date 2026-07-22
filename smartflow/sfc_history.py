"""Bounded, idempotent reconstruction of SFC history from the official archive."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from smartflow.ingestion.sfc import ingest_sfc_short_csv
from smartflow.ingestion.sfc_live import (
    SFC_SHORT_INDEX_URL,
    discover_sfc_short_csv_links,
    fetch_sfc_text,
)


@dataclass(frozen=True)
class SFCBackfillSummary:
    from_date: date
    to_date: date
    reports_selected: int
    reports_inserted: int
    events_observed: int
    events_inserted: int


def reprocess_sfc_short_history(
    session: Session,
    *,
    http_session: Any,
    from_date: date,
    observed_at: datetime,
    to_date: date | None = None,
    index_url: str = SFC_SHORT_INDEX_URL,
) -> SFCBackfillSummary:
    """Rebuild an inclusive date range, oldest first, from official CSV evidence."""
    if to_date is not None and to_date < from_date:
        raise ValueError("SFC history to_date cannot be earlier than from_date")

    index_html = fetch_sfc_text(http_session, url=index_url)
    discovered = discover_sfc_short_csv_links(index_html, index_url=index_url)
    effective_to_date = to_date or discovered[0].reporting_date
    selected = sorted(
        (
            link
            for link in discovered
            if from_date <= link.reporting_date <= effective_to_date
        ),
        key=lambda link: link.reporting_date,
    )
    if not selected:
        raise ValueError(
            f"SFC archive has no reports between {from_date} and {effective_to_date}"
        )

    reports_inserted = 0
    events_observed = 0
    events_inserted = 0
    for link in selected:
        csv_content = fetch_sfc_text(http_session, url=link.url)
        result = ingest_sfc_short_csv(
            session,
            csv_content=csv_content,
            source_url=link.url,
            published_at=None,
            observed_at=observed_at,
            expected_reporting_date=link.reporting_date,
        )
        reports_inserted += result.raw_inserted
        events_observed += result.normalized_observed
        events_inserted += result.normalized_inserted

    return SFCBackfillSummary(
        from_date=selected[0].reporting_date,
        to_date=selected[-1].reporting_date,
        reports_selected=len(selected),
        reports_inserted=reports_inserted,
        events_observed=events_observed,
        events_inserted=events_inserted,
    )
