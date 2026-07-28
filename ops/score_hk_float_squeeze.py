"""Score one local Hong Kong float-squeeze research snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartflow.hk_float_squeeze import (
    FloatSqueezeSnapshot,
    assess_float_squeeze,
    render_owner_brief,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    research = payload.pop("research")
    as_of = date.fromisoformat(payload.pop("as_of"))
    snapshot = FloatSqueezeSnapshot(
        **payload,
        as_of=as_of,
    )
    assessment = assess_float_squeeze(snapshot)
    print(render_owner_brief(snapshot, assessment))
    print("Research evidence:")
    for item in research:
        print(f"- {item['fact']} | {item['source']}")


if __name__ == "__main__":
    main()
