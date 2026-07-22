"""Build a new standalone v2 database from a bounded official SFC archive range."""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_schema import create_v2_schema
from smartflow.sfc_history import reprocess_sfc_short_history


def iso_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--from-date", required=True, type=iso_date)
    parser.add_argument("--to-date", type=iso_date)
    args = parser.parse_args()

    database = args.database.resolve()
    if database.exists():
        raise FileExistsError(f"refusing to overwrite existing database: {database}")
    database.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{database}")
    try:
        create_v2_schema(engine)
        with Session(engine) as session:
            summary = reprocess_sfc_short_history(
                session,
                http_session=requests.Session(),
                from_date=args.from_date,
                to_date=args.to_date,
                observed_at=datetime.now(timezone.utc),
            )
        output = asdict(summary)
        output["database"] = str(database)
        print(json.dumps(output, indent=2, default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
