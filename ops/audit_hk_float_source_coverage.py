"""Report timing coverage for the fixed SFC concentration-event universe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartflow.hk_float_coverage import (
    load_sfc_concentration_cases,
    summarize_sfc_universe,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "universe",
        nargs="?",
        type=Path,
        default=(
            ROOT
            / "research"
            / "hk_float_coverage"
            / "sfc_high_concentration_20250101_20260630.csv"
        ),
    )
    args = parser.parse_args()

    cases = load_sfc_concentration_cases(args.universe)
    result = summarize_sfc_universe(cases)
    print("=== HK FLOAT SOURCE COVERAGE AUDIT ===")
    print("Universe: all SFC concentration notices, 2025-01-01 to 2026-06-30")
    print(f"Cases: {result.case_count}")
    print(
        "Exact reported other-shareholder residual at SFC notice: "
        f"{result.exact_other_shareholder_residual_count}/{result.case_count}"
    )
    print(
        "Notice available before 100% rerating: "
        f"{result.notice_before_100pct_rerating_count}/{result.case_count}"
    )
    print(
        "Reported other shareholders <=10%: "
        f"{result.other_shareholders_at_or_below_10pct_count}/{result.case_count}"
    )
    print(
        "Notice lag: "
        f"median={result.median_notice_lag_calendar_days:.0f}d, "
        f"range={result.min_notice_lag_calendar_days}-"
        f"{result.max_notice_lag_calendar_days}d"
    )
    print(
        "Reported other-shareholder residual: "
        f"median={result.median_reported_other_shareholders_pct:.2f}%"
    )
    print(
        "Pre-notice rerating: "
        f"median={result.median_pre_notice_rerating_pct:.2f}%, "
        f"range={result.min_pre_notice_rerating_pct:.2f}-"
        f"{result.max_pre_notice_rerating_pct:.2f}%"
    )
    print(f"H-share-only denominator cases: {result.h_share_only_case_count}")
    print("SFC residual semantics: upper bound for tradable float, not exact free float")
    print("HKEX DI automation: BLOCKED_BY_TERMS (not measured as zero coverage)")
    print("Release recommendation: NO_GO for early-signal production")


if __name__ == "__main__":
    main()
