"""Reprocess one hash-pinned transactionless Form 4 raw event."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.sec_reprocessing import reprocess_transactionless_form4


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    engine = open_v2_shadow_engine(args.database)
    try:
        with Session(engine) as session:
            result = reprocess_transactionless_form4(
                session,
                accession=args.accession,
                expected_sha256=args.expected_sha256,
            )
        print(json.dumps(asdict(result), indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
