"""Run bounded SEC ingestion against an existing isolated v2 shadow DB."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.v2_engine import open_v2_shadow_engine
from smartflow.ingestion.sec import SOURCE_POLICIES
from smartflow.runtime_v2 import run_in_process_with_v2_timeout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--source",
        choices=("sec_form4", "sec_form144", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=240)
    args = parser.parse_args()

    sources = (
        ("sec_form4", "sec_form144") if args.source == "all" else (args.source,)
    )
    engine = open_v2_shadow_engine(args.database)
    engine.dispose()
    session_factory = sessionmaker(bind=engine)
    try:
        results = [
            run_in_process_with_v2_timeout(
                "smartflow.sec_shadow_job:run_sec_shadow_job",
                policy=SOURCE_POLICIES[source],
                session_factory=session_factory,
                args=(str(args.database.resolve()), source, args.limit),
                timeout_seconds=args.timeout_seconds,
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
