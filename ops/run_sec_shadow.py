"""Run bounded SEC ingestion against an existing isolated v2 shadow DB."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import requests
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.sec_shadow import run_sec_shadow_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--source",
        choices=("sec_form4", "sec_form144", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    sources = (
        ("sec_form4", "sec_form144") if args.source == "all" else (args.source,)
    )
    engine = open_v2_shadow_engine(args.database)
    try:
        with requests.Session() as http_session, Session(engine) as database_session:
            results = [
                run_sec_shadow_source(
                    database_session,
                    source=source,
                    limit=args.limit,
                    contact_email=os.getenv("SEC_EDGAR_EMAIL", ""),
                    http_session=http_session,
                )
                for source in sources
            ]
    except Exception as error:
        print(json.dumps({"status": "error", "error_code": type(error).__name__}))
        raise SystemExit(1) from error
    finally:
        engine.dispose()

    print(json.dumps({"status": "success", "results": [asdict(result) for result in results]}, indent=2))


if __name__ == "__main__":
    main()
