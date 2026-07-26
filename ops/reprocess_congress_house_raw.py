"""Reprocess one hash-pinned House PTR from its preserved raw PDF."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import requests
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.congress_reprocessing import reprocess_house_ptr
from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.congress_live import (
    HOUSE_INDEX_URL,
    fetch_house_bytes,
    parse_house_index_zip,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()

    with requests.Session() as http:
        index_payload = fetch_house_bytes(
            http,
            url=HOUSE_INDEX_URL.format(year=args.year),
            expected_kind="index",
        )
    reports = parse_house_index_zip(index_payload, year=args.year)
    report = next(
        (item for item in reports if item["doc_id"] == args.doc_id),
        None,
    )
    if report is None:
        raise SystemExit("requested DocID is absent from the official House index")

    engine = open_v2_shadow_engine(args.database)
    try:
        with Session(engine) as session:
            result = reprocess_house_ptr(
                session,
                doc_id=args.doc_id,
                expected_sha256=args.expected_sha256,
                report=report,
            )
        print(json.dumps(asdict(result), indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
