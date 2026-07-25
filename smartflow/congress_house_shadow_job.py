"""Importable child-process entry point for one House Congress shadow run."""

from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.congress_live import HouseBatchResult, ingest_house_ptr_batch


def run_congress_house_shadow_job(
    database_path: str,
    year: int,
    limit: int,
) -> HouseBatchResult:
    engine = open_v2_shadow_engine(Path(database_path))
    try:
        with requests.Session() as http_session, Session(engine) as database_session:
            return ingest_house_ptr_batch(
                database_session,
                http_session=http_session,
                observed_at=datetime.now(timezone.utc),
                year=year,
                max_reports=limit,
            )
    finally:
        engine.dispose()
