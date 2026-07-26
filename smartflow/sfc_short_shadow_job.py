"""Importable child-process entry point for one SFC short shadow run."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.sfc_live import ingest_latest_sfc_short_report


@dataclass(frozen=True)
class SFCShortShadowRunResult:
    reporting_date: str
    cache_hit: bool
    raw_inserted: int
    normalized_inserted: int
    normalized_observed: int
    run_id: int


def run_sfc_short_shadow_job(database_path: str) -> SFCShortShadowRunResult:
    engine = open_v2_shadow_engine(Path(database_path))
    try:
        with requests.Session() as http_session, Session(engine) as database_session:
            link, result = ingest_latest_sfc_short_report(
                database_session,
                http_session=http_session,
                observed_at=datetime.now(timezone.utc),
            )
            return SFCShortShadowRunResult(
                reporting_date=link.reporting_date.isoformat(),
                cache_hit=result.normalized_observed == 0,
                raw_inserted=result.raw_inserted,
                normalized_inserted=result.normalized_inserted,
                normalized_observed=result.normalized_observed,
                run_id=result.run_id,
            )
    finally:
        engine.dispose()
