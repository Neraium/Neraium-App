"""Discretionary exposure guidance derived from governance outputs."""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class RiskGuidanceInput:
    action_permission: str
    validity_score: float
    confidence_score: float
    fragility_score: float
    transition_state: str
    data_quality_score: float
    regime_stability_score: float


@dataclass(slots=True)
class RiskGuidanceResult:
    exposure_guidance: str
    risk_budget_score: float
    size_multiplier: float
    rationale: str


def evaluate_risk_guidance(data: RiskGuidanceInput) -> RiskGuidanceResult:
    risk_budget_score = _clamp(
        0.30 * data.validity_score
        + 0.22 * data.confidence_score
        + 0.16 * data.data_quality_score
        + 0.16 * data.regime_stability_score
        + 0.16 * (1.0 - data.fragility_score)
        - (0.15 if data.transition_state == "transition" else 0.0)
    )

    if data.action_permission == "AVOID" or risk_budget_score < 0.35:
        exposure_guidance = "NO_EXPOSURE"
        size_multiplier = 0.0
    elif data.fragility_score > 0.68 or data.transition_state == "transition":
        exposure_guidance = "PROBE"
        size_multiplier = 0.25
    elif data.action_permission == "REDUCE" or risk_budget_score < 0.62:
        exposure_guidance = "REDUCED"
        size_multiplier = 0.50
    else:
        exposure_guidance = "FULL"
        size_multiplier = min(1.0, round(0.65 + 0.35 * risk_budget_score, 2))

    rationale = (
        f"Exposure guidance is {exposure_guidance.lower()} because validity={data.validity_score:.2f}, "
        f"confidence={data.confidence_score:.2f}, fragility={data.fragility_score:.2f}, "
        f"data_quality={data.data_quality_score:.2f}, regime_stability={data.regime_stability_score:.2f}."
    )
    return RiskGuidanceResult(
        exposure_guidance=exposure_guidance,
        risk_budget_score=risk_budget_score,
        size_multiplier=size_multiplier,
        rationale=rationale,
    )
