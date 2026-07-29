"""Deterministic prototype for Hong Kong locked-float squeeze research."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal


TRIGGERED = "TRIGGERED"
COILED = "COILED"
ACCUMULATING = "ACCUMULATING"
WATCH_DATA_GAP = "WATCH_DATA_GAP"
INVALIDATED = "INVALIDATED"
OVERHEATED = "OVERHEATED"
SCREEN_OUT = "SCREEN_OUT"
EFFECTIVE_TRADABLE = "EFFECTIVE_TRADABLE"
SFC_OTHER_SHAREHOLDERS_UPPER_BOUND = "SFC_OTHER_SHAREHOLDERS_UPPER_BOUND"


def _percentage(name: str, value: float | None) -> None:
    if value is not None and not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


def _signed_percentage(name: str, value: float | None) -> None:
    if value is not None and not -100 <= value <= 100:
        raise ValueError(f"{name} must be between -100 and 100")


@dataclass(frozen=True)
class FloatSqueezeSnapshot:
    ticker: str
    company_name: str
    as_of: date
    anchor_holder_pct: float
    disclosed_holders_pct: float
    confirmed_holder_delta_pct_of_issued: float | None
    issued_share_change_pct: float | None
    executed_buyback_pct: float | None
    buyback_announced: bool
    tradable_float_pct: float | None
    return_60d_pct: float
    return_252d_pct: float
    distance_to_20d_high_pct: float
    latest_volume_ratio_20d: float
    tradable_float_basis: Literal[
        "EFFECTIVE_TRADABLE",
        "SFC_OTHER_SHAREHOLDERS_UPPER_BOUND",
    ] | None = None
    ownership_window_days: int | None = None
    dual_listed: bool = False

    def __post_init__(self) -> None:
        if not self.ticker.strip() or not self.company_name.strip():
            raise ValueError("ticker and company_name are required")
        _percentage("anchor_holder_pct", self.anchor_holder_pct)
        _percentage("disclosed_holders_pct", self.disclosed_holders_pct)
        _percentage("tradable_float_pct", self.tradable_float_pct)
        _signed_percentage(
            "confirmed_holder_delta_pct_of_issued",
            self.confirmed_holder_delta_pct_of_issued,
        )
        _signed_percentage(
            "issued_share_change_pct",
            self.issued_share_change_pct,
        )
        _percentage("executed_buyback_pct", self.executed_buyback_pct)
        if self.disclosed_holders_pct < self.anchor_holder_pct:
            raise ValueError("disclosed_holders_pct cannot be below anchor_holder_pct")
        if self.latest_volume_ratio_20d < 0:
            raise ValueError("latest_volume_ratio_20d cannot be negative")
        if (self.tradable_float_pct is None) != (self.tradable_float_basis is None):
            raise ValueError(
                "tradable_float_pct and tradable_float_basis must be set together"
            )
        if self.ownership_window_days is not None and self.ownership_window_days <= 0:
            raise ValueError("ownership_window_days must be positive")


@dataclass(frozen=True)
class FloatSqueezeAssessment:
    score: int
    state: str
    confidence: str
    components: dict[str, int]
    data_gaps: tuple[str, ...]
    risks: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OwnershipPoint:
    as_of: date
    holder_name: str
    holder_shares: int
    holder_pct: float
    issued_shares: int
    issued_shares_quality: Literal["exact", "inferred"]

    def __post_init__(self) -> None:
        if not self.holder_name.strip():
            raise ValueError("holder_name is required")
        if self.holder_shares < 0:
            raise ValueError("holder_shares cannot be negative")
        if self.issued_shares <= 0:
            raise ValueError("issued_shares must be positive")
        if self.holder_shares > self.issued_shares:
            raise ValueError("holder_shares cannot exceed issued_shares")
        _percentage("holder_pct", self.holder_pct)
        if self.issued_shares_quality not in {"exact", "inferred"}:
            raise ValueError("issued_shares_quality must be exact or inferred")


@dataclass(frozen=True)
class OwnershipReconciliation:
    holder_name: str
    previous_as_of: date
    current_as_of: date
    window_days: int
    holder_share_delta: int
    holder_share_change_pct: float
    holder_delta_pct_of_prior_issued: float
    ownership_pct_change_points: float
    issued_share_change_pct: float
    attribution: str
    quality: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FloatStructure:
    issued_shares: int
    float_shares: int
    basis: Literal[
        "EFFECTIVE_TRADABLE",
        "SFC_OTHER_SHAREHOLDERS_UPPER_BOUND",
    ]

    def __post_init__(self) -> None:
        if self.issued_shares <= 0:
            raise ValueError("issued_shares must be positive")
        if not 0 <= self.float_shares <= self.issued_shares:
            raise ValueError("float_shares must be between zero and issued_shares")
        if self.basis not in {
            EFFECTIVE_TRADABLE,
            SFC_OTHER_SHAREHOLDERS_UPPER_BOUND,
        }:
            raise ValueError("unsupported float basis")

    @property
    def tradable_float_pct(self) -> float:
        return self.float_shares / self.issued_shares * 100


def reconcile_ownership(
    previous: OwnershipPoint,
    current: OwnershipPoint,
) -> OwnershipReconciliation:
    """Separate actual holder-share movement from issuer-denominator movement."""
    if previous.holder_name != current.holder_name:
        raise ValueError("ownership points must refer to the same holder")
    if current.as_of <= previous.as_of:
        raise ValueError("current ownership point must be later than previous")

    holder_delta = current.holder_shares - previous.holder_shares
    if previous.holder_shares:
        holder_change_pct = holder_delta / previous.holder_shares * 100
    elif holder_delta:
        holder_change_pct = 100.0
    else:
        holder_change_pct = 0.0
    holder_delta_pct_of_issued = holder_delta / previous.issued_shares * 100
    ownership_pct_change = current.holder_pct - previous.holder_pct
    issued_change_pct = (
        (current.issued_shares - previous.issued_shares)
        / previous.issued_shares
        * 100
    )

    if holder_delta > 0:
        attribution = "CONFIRMED_ACCUMULATION"
    elif holder_delta < 0:
        attribution = "CONFIRMED_DISTRIBUTION"
    elif ownership_pct_change:
        attribution = "DENOMINATOR_ONLY"
    else:
        attribution = "UNCHANGED"

    quality = (
        "EXACT"
        if previous.issued_shares_quality == current.issued_shares_quality == "exact"
        else "INCLUDES_INFERRED_ISSUED_SHARES"
    )
    return OwnershipReconciliation(
        holder_name=current.holder_name,
        previous_as_of=previous.as_of,
        current_as_of=current.as_of,
        window_days=(current.as_of - previous.as_of).days,
        holder_share_delta=holder_delta,
        holder_share_change_pct=holder_change_pct,
        holder_delta_pct_of_prior_issued=holder_delta_pct_of_issued,
        ownership_pct_change_points=ownership_pct_change,
        issued_share_change_pct=issued_change_pct,
        attribution=attribution,
        quality=quality,
    )


def _ownership_lock_score(snapshot: FloatSqueezeSnapshot) -> int:
    if snapshot.anchor_holder_pct >= 25:
        anchor = 15
    elif snapshot.anchor_holder_pct >= 15:
        anchor = 10
    elif snapshot.anchor_holder_pct >= 5:
        anchor = 5
    else:
        anchor = 0

    if snapshot.disclosed_holders_pct >= 60:
        disclosed = 10
    elif snapshot.disclosed_holders_pct >= 40:
        disclosed = 7
    elif snapshot.disclosed_holders_pct >= 20:
        disclosed = 3
    else:
        disclosed = 0
    return anchor + disclosed


def _accumulation_score(value: float | None) -> int:
    if value is None:
        return 0
    if value >= 2:
        return 25
    if value >= 1:
        return 18
    if value >= 0.5:
        return 12
    if value > 0:
        return 6
    return 0


def _denominator_score(snapshot: FloatSqueezeSnapshot) -> int:
    issued_change = snapshot.issued_share_change_pct
    if issued_change is None:
        issued_score = 0
    elif issued_change <= -2:
        issued_score = 10
    elif issued_change <= -1:
        issued_score = 7
    elif issued_change < 0:
        issued_score = 3
    else:
        issued_score = 0

    buyback = snapshot.executed_buyback_pct
    if buyback is None:
        buyback_score = 2 if snapshot.buyback_announced else 0
    elif buyback >= 2:
        buyback_score = 5
    elif buyback >= 1:
        buyback_score = 3
    elif buyback > 0:
        buyback_score = 1
    else:
        buyback_score = 0
    return issued_score + buyback_score


def _float_score(value: float | None) -> int:
    if value is None:
        return 0
    if value <= 20:
        return 20
    if value <= 35:
        return 14
    if value <= 50:
        return 8
    if value <= 70:
        return 3
    return 0


def _trigger_score(snapshot: FloatSqueezeSnapshot) -> int:
    score = 0
    if snapshot.return_60d_pct >= 5:
        score += 4
    if snapshot.distance_to_20d_high_pct >= -2:
        score += 4
    if snapshot.latest_volume_ratio_20d >= 1.5:
        score += 7
    elif snapshot.latest_volume_ratio_20d >= 1:
        score += 4
    return score


def assess_float_squeeze(snapshot: FloatSqueezeSnapshot) -> FloatSqueezeAssessment:
    """Score evidence without treating percentage changes as confirmed buying."""
    components = {
        "ownership_lock": _ownership_lock_score(snapshot),
        "confirmed_accumulation": _accumulation_score(
            snapshot.confirmed_holder_delta_pct_of_issued
        ),
        "denominator_shrink": _denominator_score(snapshot),
        "tradable_float": _float_score(snapshot.tradable_float_pct),
        "market_trigger": _trigger_score(snapshot),
    }
    score = sum(components.values())

    gaps = []
    if snapshot.confirmed_holder_delta_pct_of_issued is None:
        gaps.append("actual_holder_share_delta")
    if snapshot.issued_share_change_pct is None:
        gaps.append("issued_share_change")
    if snapshot.tradable_float_pct is None:
        gaps.append("consolidated_tradable_float")

    risks = []
    if snapshot.dual_listed:
        risks.append("dual_listing_requires_consolidated_global_share_capital")
    if (
        snapshot.ownership_window_days is not None
        and snapshot.ownership_window_days > 365
    ):
        risks.append("ownership_comparison_window_exceeds_365_days")
    if (
        snapshot.confirmed_holder_delta_pct_of_issued is not None
        and snapshot.confirmed_holder_delta_pct_of_issued < 0
    ):
        risks.append("confirmed_holder_distribution")
    if (
        snapshot.issued_share_change_pct is not None
        and snapshot.issued_share_change_pct > 1
    ):
        risks.append("material_share_supply_increase")
    if snapshot.tradable_float_pct is not None and snapshot.tradable_float_pct <= 20:
        risks.append("low_float_can_amplify_drawdown_and_exit_slippage")
    if snapshot.tradable_float_basis == SFC_OTHER_SHAREHOLDERS_UPPER_BOUND:
        risks.append("tradable_float_is_sfc_other_shareholders_upper_bound")
    if snapshot.return_252d_pct >= 40:
        risks.append("price_has_already_rerated_materially")
    if (
        snapshot.distance_to_20d_high_pct >= -2
        and snapshot.latest_volume_ratio_20d < 0.75
    ):
        risks.append("near_high_without_volume_confirmation")

    if (
        snapshot.confirmed_holder_delta_pct_of_issued is not None
        and snapshot.confirmed_holder_delta_pct_of_issued < 0
    ) or (
        snapshot.issued_share_change_pct is not None
        and snapshot.issued_share_change_pct > 1
    ):
        state = INVALIDATED
    elif (
        snapshot.tradable_float_pct is not None
        and snapshot.tradable_float_pct <= 15
        and (
            snapshot.return_60d_pct >= 100
            or snapshot.return_252d_pct >= 200
        )
    ):
        state = OVERHEATED
    elif gaps:
        state = WATCH_DATA_GAP
    elif score >= 75 and components["market_trigger"] >= 10:
        state = TRIGGERED
    elif score >= 60:
        state = COILED
    elif score >= 40:
        state = ACCUMULATING
    else:
        state = SCREEN_OUT

    if len(gaps) >= 2:
        confidence = "LOW"
    elif gaps:
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    return FloatSqueezeAssessment(
        score=score,
        state=state,
        confidence=confidence,
        components=components,
        data_gaps=tuple(gaps),
        risks=tuple(risks),
    )


def render_owner_brief(
    snapshot: FloatSqueezeSnapshot,
    assessment: FloatSqueezeAssessment,
) -> str:
    component_text = ", ".join(
        f"{name}={score}" for name, score in assessment.components.items()
    )
    gap_text = ", ".join(assessment.data_gaps) or "none"
    risk_text = ", ".join(assessment.risks) or "none"
    if assessment.state == WATCH_DATA_GAP:
        conclusion = "未證實為float squeeze；保留觀察，唔應該因持股百分比上升而追入。"
    elif assessment.state == TRIGGERED:
        conclusion = "鎖貨、供應收縮及市場突破同時成立；進入重點研究名單。"
    elif assessment.state == COILED:
        conclusion = "float squeeze條件大致形成，但未有足夠市場突破確認。"
    elif assessment.state == ACCUMULATING:
        conclusion = "見到早期收貨或供應收縮，證據仍未形成完整setup。"
    elif assessment.state == INVALIDATED:
        conclusion = "大戶減持或股份供應增加，float squeeze假設失效。"
    elif assessment.state == OVERHEATED:
        conclusion = "高度集中資料出現時股價已大幅重估；只作追高及流動性風險警告，唔係早期買入訊號。"
    else:
        conclusion = "未達float squeeze研究門檻。"

    return "\n".join(
        [
            "=== HK FLOAT SQUEEZE PROTOTYPE ===",
            f"{snapshot.ticker} — {snapshot.company_name}",
            f"As of: {snapshot.as_of.isoformat()}",
            (
                f"Result: {assessment.state} | Score: {assessment.score}/100 | "
                f"Confidence: {assessment.confidence}"
            ),
            f"結論: {conclusion}",
            f"分數: {component_text}",
            f"資料缺口: {gap_text}",
            f"主要風險: {risk_text}",
        ]
    )
