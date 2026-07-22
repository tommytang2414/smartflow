"""Importable child-process entry point for one SEC shadow source run."""

import os
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.sec_shadow import SECShadowRunResult, run_sec_shadow_source


def run_sec_shadow_job(
    database_path: str,
    source: str,
    limit: int,
) -> SECShadowRunResult:
    engine = open_v2_shadow_engine(Path(database_path))
    try:
        with requests.Session() as http_session, Session(engine) as database_session:
            return run_sec_shadow_source(
                database_session,
                source=source,
                limit=limit,
                contact_email=os.getenv("SEC_EDGAR_EMAIL", ""),
                http_session=http_session,
            )
    finally:
        engine.dispose()
