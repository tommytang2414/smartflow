"""Run bounded House Congress ingestion against its isolated v2 shadow DB."""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.congress import CONGRESS_POLICY
from smartflow.runtime_v2 import run_in_process_with_v2_timeout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    args = parser.parse_args()

    if args.year < 2008 or args.year > datetime.now(timezone.utc).year:
        parser.error("year must be between 2008 and the current UTC year")
    if args.limit < 1 or args.limit > 100:
        parser.error("limit must be between 1 and 100")

    engine = open_v2_shadow_engine(args.database)
    session_factory = sessionmaker(bind=engine)
    try:
        result = run_in_process_with_v2_timeout(
            "smartflow.congress_house_shadow_job:run_congress_house_shadow_job",
            policy=CONGRESS_POLICY,
            session_factory=session_factory,
            args=(str(args.database.resolve()), args.year, args.limit),
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as error:
        print(json.dumps({"status": "error", "error_code": type(error).__name__}))
        raise SystemExit(1) from error
    finally:
        engine.dispose()

    print(json.dumps({"status": "success", "result": asdict(result)}, indent=2))


if __name__ == "__main__":
    main()
