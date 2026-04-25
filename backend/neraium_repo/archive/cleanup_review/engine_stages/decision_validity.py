"""Decision-validity stage for market action governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ActionPermission = Literal["ACT", "WAIT", "REDUCE", "AVOID"]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class DecisionValidityInput:
    asset: str
    timeframe: str
    regime: str
    state: str
    structural_drift_score: float
    instability_score: float
    coherence_score: float
    confidence_score: float
    data_quality_score: float
    persistence_score: float
    contradiction_penalty: float = 0.0
    breadth_score: float = 0.5
    vix_change: float = 0.0
    sample_count: int = 0
    baseline_count: int = 60
    recent_count: int = 20
    drift_components: dict[str, float] = field(default_factory=dict)
    context_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DecisionValidityResult:
    is_valid: bool
    action_permission: ActionPermission
    validity_score: float
    confidence_score: float
    fragility_score: float
    abstain: bool
    invalidating_factors: list[str]
    justification: str
    structural_summary: str
    transition_state: str


def evaluate_decision_validity(data: DecisionValidityInput) -> DecisionValidityResult:
    expected_samples = max(1, data.baseline_count + data.recent_count)
    sample_ratio = _clamp(data.sample_count / expected_samples)
    data_sufficiency = _clamp(min(data.data_quality_score, sample_ratio))
    transition_pressure = _clamp(
        0.45 * data.structural_drift_score
        + 0.35 * data.instability_score
        + 0.20 * max(0.0, data.contradiction_penalty * 2.0)
    )
    if data.state in {"transitioning", "unstable"}:
        transition_pressure = _clamp(transition_pressure + 0.15)
    if "transition" in data.regime or "stress" in data.regime:
        transition_pressure = _clamp(transition_pressure + 0.1)

    regime_stability = _clamp(1.0 - 0.65 * data.structural_drift_score - 0.35 * data.instability_score)
    confidence_agreement = _clamp(1.0 - abs(data.confidence_score - data.coherence_score))
    false_stability_detected = (
        data.regime == "false_calm"
        or (
            data.structural_drift_score < 0.30
            and data.instability_score < 0.35
            and data.breadth_score < 0.45
            and data.vix_change > 0.0
        )
    )
    fragmentation_detected = bool(data.breadth_score < 0.42 and data.structural_drift_score > 0.35)

    invalidating_factors: list[str] = []
    if data_sufficiency < 0.55:
        invalidating_factors.append("insufficient data quality or warmup depth")
    if data.confidence_score < 0.46:
        invalidating_factors.append("confidence is too weak to justify action")
    if data.coherence_score < 0.45:
        invalidating_factors.append("structural coherence is weak")
    if transition_pressure > 0.62:
        invalidating_factors.append("transition pressure is too elevated")
    if regime_stability < 0.45:
        invalidating_factors.append("regime stability is not established")
    if confidence_agreement < 0.55:
        invalidating_factors.append("confidence and coherence do not agree")
    if false_stability_detected:
        invalidating_factors.append("false-stability conditions detected")
    if fragmentation_detected:
        invalidating_factors.append("participation is fragmented")

    fragility_score = _clamp(
        0.30 * transition_pressure
        + 0.20 * (1.0 - regime_stability)
        + 0.20 * (1.0 - confidence_agreement)
        + 0.15 * (1.0 - data_sufficiency)
        + 0.15 * (1.0 - data.coherence_score)
    )
    if false_stability_detected:
        fragility_score = _clamp(fragility_score + 0.12)

    validity_score = _clamp(
        0.26 * data.coherence_score
        + 0.22 * data.confidence_score
        + 0.20 * data_sufficiency
        + 0.16 * confidence_agreement
        + 0.16 * regime_stability
        - 0.18 * transition_pressure
    )

    transition_state = "transition" if transition_pressure > 0.62 else "settled"
    abstain = bool(invalidating_factors or validity_score < 0.50 or fragility_score > 0.72)

    if data_sufficiency < 0.55 or transition_pressure > 0.80:
        action_permission: ActionPermission = "AVOID"
    elif abstain and fragility_score > 0.60:
        action_permission = "REDUCE"
    elif abstain:
        action_permission = "WAIT"
    else:
        action_permission = "ACT"

    is_valid = not abstain and action_permission == "ACT"

    top_components = sorted(data.drift_components.items(), key=lambda item: item[1], reverse=True)[:2]
    component_text = ", ".join(f"{name}={value:.2f}" for name, value in top_components) if top_components else "limited component detail"
    structural_summary = (
        f"{data.asset} {data.timeframe} is {data.state} inside {data.regime}; "
        f"drift={data.structural_drift_score:.2f}, instability={data.instability_score:.2f}, "
        f"coherence={data.coherence_score:.2f}, strongest shifts: {component_text}."
    )

    posture_text = {
        "ACT": "structure is coherent enough to permit action",
        "WAIT": "structure is not yet trustworthy enough to act",
        "REDUCE": "existing risk should be reduced rather than expanded",
        "AVOID": "current conditions invalidate new exposure",
    }[action_permission]
    factor_text = "; ".join(invalidating_factors[:3]) if invalidating_factors else "no major invalidators detected"
    justification = (
        f"{posture_text}. Data sufficiency={data_sufficiency:.2f}, confidence agreement={confidence_agreement:.2f}, "
        f"transition pressure={transition_pressure:.2f}, fragility={fragility_score:.2f}. {factor_text}."
    )
    if data.context_notes:
        justification = f"{justification} Context: {'; '.join(data.context_notes[:2])}."

    return DecisionValidityResult(
        is_valid=is_valid,
        action_permission=action_permission,
        validity_score=validity_score,
        confidence_score=_clamp(data.confidence_score),
        fragility_score=fragility_score,
        abstain=abstain,
        invalidating_factors=invalidating_factors,
        justification=justification,
        structural_summary=structural_summary,
        transition_state=transition_state,
    )
