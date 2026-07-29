"""Coverage metrics for the fixed Hong Kong concentration-event universe."""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class SFCConcentrationCase:
    stock_code: str
    company_name: str
    announcement_date: date
    information_date: date
    notice_lag_calendar_days: int
    issued_shares_in_scope: int
    reported_other_shareholders_shares: int
    reported_other_shareholders_pct: float
    pre_notice_rerating_pct: float
    share_class_scope: str
    source_url: str

    def __post_init__(self) -> None:
        if len(self.stock_code) != 5 or not self.stock_code.isdigit():
            raise ValueError("stock_code must be five digits")
        if self.announcement_date <= self.information_date:
            raise ValueError("announcement_date must follow information_date")
        if (
            self.announcement_date - self.information_date
        ).days != self.notice_lag_calendar_days:
            raise ValueError("notice_lag_calendar_days does not match case dates")
        if (
            not 0
            < self.reported_other_shareholders_shares
            <= self.issued_shares_in_scope
        ):
            raise ValueError("reported other-shareholder shares are outside issued shares")
        calculated_pct = (
            self.reported_other_shareholders_shares
            / self.issued_shares_in_scope
            * 100
        )
        if abs(calculated_pct - self.reported_other_shareholders_pct) > 0.02:
            raise ValueError("reported_other_shareholders_pct does not reconcile")
        if self.pre_notice_rerating_pct < 0:
            raise ValueError("pre_notice_rerating_pct cannot be negative")
        if self.share_class_scope not in {
            "LISTED_ORDINARY_SHARES",
            "H_SHARES_ONLY",
        }:
            raise ValueError("unsupported share_class_scope")
        if not self.source_url.startswith(
            "https://www.sfc.hk/-/media/EN/files/ENF/HighCon/"
        ):
            raise ValueError("source_url must be an official SFC notice")


@dataclass(frozen=True)
class SFCUniverseCoverage:
    case_count: int
    exact_other_shareholder_residual_count: int
    notice_before_100pct_rerating_count: int
    other_shareholders_at_or_below_10pct_count: int
    median_notice_lag_calendar_days: float
    min_notice_lag_calendar_days: int
    max_notice_lag_calendar_days: int
    median_reported_other_shareholders_pct: float
    median_pre_notice_rerating_pct: float
    min_pre_notice_rerating_pct: float
    max_pre_notice_rerating_pct: float
    h_share_only_case_count: int


def load_sfc_concentration_cases(path: Path) -> tuple[SFCConcentrationCase, ...]:
    cases = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            cases.append(
                SFCConcentrationCase(
                    stock_code=row["stock_code"],
                    company_name=row["company_name"],
                    announcement_date=date.fromisoformat(row["announcement_date"]),
                    information_date=date.fromisoformat(row["information_date"]),
                    notice_lag_calendar_days=int(row["notice_lag_calendar_days"]),
                    issued_shares_in_scope=int(row["issued_shares_in_scope"]),
                    reported_other_shareholders_shares=int(
                        row["reported_other_shareholders_shares"]
                    ),
                    reported_other_shareholders_pct=float(
                        row["reported_other_shareholders_pct"]
                    ),
                    pre_notice_rerating_pct=float(row["pre_notice_rerating_pct"]),
                    share_class_scope=row["share_class_scope"],
                    source_url=row["source_url"],
                )
            )
    if not cases:
        raise ValueError("coverage universe cannot be empty")
    return tuple(cases)


def summarize_sfc_universe(
    cases: tuple[SFCConcentrationCase, ...],
) -> SFCUniverseCoverage:
    lags = [case.notice_lag_calendar_days for case in cases]
    residuals = [case.reported_other_shareholders_pct for case in cases]
    reratings = [case.pre_notice_rerating_pct for case in cases]
    return SFCUniverseCoverage(
        case_count=len(cases),
        exact_other_shareholder_residual_count=len(cases),
        notice_before_100pct_rerating_count=sum(
            case.pre_notice_rerating_pct < 100 for case in cases
        ),
        other_shareholders_at_or_below_10pct_count=sum(
            case.reported_other_shareholders_pct <= 10 for case in cases
        ),
        median_notice_lag_calendar_days=statistics.median(lags),
        min_notice_lag_calendar_days=min(lags),
        max_notice_lag_calendar_days=max(lags),
        median_reported_other_shareholders_pct=statistics.median(residuals),
        median_pre_notice_rerating_pct=statistics.median(reratings),
        min_pre_notice_rerating_pct=min(reratings),
        max_pre_notice_rerating_pct=max(reratings),
        h_share_only_case_count=sum(
            case.share_class_scope == "H_SHARES_ONLY" for case in cases
        ),
    )
