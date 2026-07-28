"""Score one local Hong Kong float-squeeze research snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartflow.hk_float_cases import load_float_squeeze_case
from smartflow.hk_float_squeeze import assess_float_squeeze, render_owner_brief


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()

    case = load_float_squeeze_case(args.snapshot)
    assessment = assess_float_squeeze(case.snapshot)
    print(render_owner_brief(case.snapshot, assessment))
    print(
        f"Point-in-time: information_date={case.information_date.isoformat()} | "
        f"available_at={case.available_at.isoformat()}"
    )
    if case.ownership_reconciliation is not None:
        item = case.ownership_reconciliation
        print(
            "Ownership reconciliation: "
            f"{item.attribution} | shares_delta={item.holder_share_delta:+,} | "
            f"holder_delta/prior_issued={item.holder_delta_pct_of_prior_issued:+.4f}% | "
            f"ownership_pct={item.ownership_pct_change_points:+.4f}pp | "
            f"issued_shares={item.issued_share_change_pct:+.4f}% | "
            f"window={item.window_days}d | quality={item.quality}"
        )
    if case.outcome is not None:
        print(
            "Observed outcome: "
            f"5d={case.outcome['forward_5d_pct']}% | "
            f"20d={case.outcome['forward_20d_pct']}%"
        )
    print("Research evidence:")
    for item in case.research:
        print(f"- {item['fact']} | {item['source']}")


if __name__ == "__main__":
    main()
