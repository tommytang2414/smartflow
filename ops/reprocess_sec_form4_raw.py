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
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--accession")
    selection.add_argument("--manifest", type=Path, help="Exact accession/hash allowlist; retained as release evidence")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()

    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if set(manifest) != {"release_id", "source", "items"} or manifest["source"] != "sec_form4":
            raise ValueError("invalid reprocessing manifest")
        items = manifest["items"]
        if not isinstance(items, list) or not 1 <= len(items) <= 500 or any(
            not isinstance(item, dict) or set(item) != {"accession", "payload_sha256"} for item in items
        ) or len({item["accession"] for item in items}) != len(items):
            raise ValueError("invalid reprocessing selection")
    else:
        if not args.expected_sha256:
            parser.error("--accession requires --expected-sha256")
        items = [{"accession": args.accession, "payload_sha256": args.expected_sha256}]

    engine = open_v2_shadow_engine(args.database)
    try:
        with Session(engine) as session:
            for item in items:
                result = reprocess_transactionless_form4(
                    session, accession=item["accession"], expected_sha256=item["payload_sha256"])
                print(json.dumps(asdict(result)), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
