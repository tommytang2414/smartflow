"""Evaluate all maintained point-in-time Hong Kong float-squeeze cases."""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartflow.hk_float_cases import load_float_squeeze_case
from smartflow.hk_float_squeeze import assess_float_squeeze


def _metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "case_directory",
        nargs="?",
        type=Path,
        default=ROOT / "examples" / "hk_float_squeeze",
    )
    args = parser.parse_args()

    paths = sorted(args.case_directory.glob("*.json"))
    if not paths:
        raise SystemExit(f"No case JSON files found in {args.case_directory}")

    states: Counter[str] = Counter()
    outcomes: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"5d": [], "20d": []}
    )
    print("case_id | available_at | state | score | 5d | 20d")
    for path in paths:
        case = load_float_squeeze_case(path)
        assessment = assess_float_squeeze(case.snapshot)
        states[assessment.state] += 1
        five_day = case.outcome["forward_5d_pct"] if case.outcome else None
        twenty_day = case.outcome["forward_20d_pct"] if case.outcome else None
        if five_day is not None:
            outcomes[assessment.state]["5d"].append(float(five_day))
        if twenty_day is not None:
            outcomes[assessment.state]["20d"].append(float(twenty_day))
        print(
            f"{case.case_id} | {case.available_at.isoformat()} | "
            f"{assessment.state} | {assessment.score} | "
            f"{_metric(five_day)} | {_metric(twenty_day)}"
        )

    print("\nState counts:")
    for state, count in sorted(states.items()):
        print(f"- {state}: {count}")
    print("Descriptive outcomes by state (small research sample; not inference):")
    for state, horizons in sorted(outcomes.items()):
        for horizon, values in horizons.items():
            if values:
                print(
                    f"- {state} {horizon}: n={len(values)}, "
                    f"mean={statistics.mean(values):+.2f}%, "
                    f"median={statistics.median(values):+.2f}%"
                )


if __name__ == "__main__":
    main()
