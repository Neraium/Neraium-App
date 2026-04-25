"""Fragility and invalidation modeling for governed market decisions."""

from __future__ import annotations

from dataclasses import dataclass, field


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class FragilityInput:
    regime: str
    state: str
    drift_score: float
    instability_score: float
    coherence_score: float
    confidence_score: float
    data_quality_score: float
    validity_score: float
    transition_state: str
    breadth_score: float = 0.5
    vix_change: float = 0.0
    invalidating_factors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FragilityResult:
    fragility_score: float
    fragility_state: str
    fragility_sources: list[str]
    invalidation_conditions: list[str]
    dependency_map: dict[str, float]
    edge_dependencies: list[str]
    why_not_robust: str
    edge_stability_window: str


def evaluate_fragility(data: FragilityInput) -> FragilityResult:
    dependency_map = {
        "structural_coherence": _clamp(data.coherence_score),
        "confidence": _clamp(data.confidence_score),
        "regime_stability": _clamp(1.0 - 0.6 * data.drift_score - 0.4 * data.instability_score),
        "data_quality": _clamp(data.data_quality_score),
        "participation": _clamp(data.breadth_score),
    }

    fragility_sources: list[str] = []
    if data.transition_state == "transition":
        fragility_sources.append("transition-state pressure")
    if data.instability_score > 0.60:
        fragility_sources.append("elevated realized instability")
    if data.drift_score > 0.58:
        fragility_sources.append("structural drift is still active")
    if data.coherence_score < 0.55:
        fragility_sources.append("coherence is shallow")
    if data.confidence_score < 0.55:
        fragility_sources.append("confidence support is narrow")
    if data.data_quality_score < 0.70:
        fragility_sources.append("data support is limited")
    if data.breadth_score < 0.45:
        fragility_sources.append("participation is fragmented")
    if data.regime == "false_calm":
        fragility_sources.append("false calm regime")

    fragility_score = _clamp(
        0.25 * (1.0 - dependency_map["structural_coherence"])
        + 0.20 * (1.0 - dependency_map["confidence"])
        + 0.20 * (1.0 - dependency_map["regime_stability"])
        + 0.15 * (1.0 - dependency_map["data_quality"])
        + 0.10 * (1.0 - dependency_map["participation"])
        + 0.10 * (1.0 - data.validity_score)
    )
    if data.transition_state == "transition":
        fragility_score = _clamp(fragility_score + 0.10)

    if fragility_score >= 0.72:
        fragility_state = "FRAGILE"
        edge_stability_window = "narrow"
    elif fragility_score >= 0.42:
        fragility_state = "MODERATE"
        edge_stability_window = "developing"
    else:
        fragility_state = "ROBUST"
        edge_stability_window = "persistent"

    invalidation_conditions = list(data.invalidating_factors)
    if data.drift_score > 0.55:
        invalidation_conditions.append("fresh structural drift expansion")
    if data.instability_score > 0.55:
        invalidation_conditions.append("another volatility expansion wave")
    if data.coherence_score < 0.50:
        invalidation_conditions.append("coherence slipping below confirmation")
    if data.confidence_score < 0.50:
        invalidation_conditions.append("confidence dropping below trader minimums")
    if data.breadth_score < 0.42:
        invalidation_conditions.append("breadth narrowing further")
    if data.vix_change > 0.03:
        invalidation_conditions.append("volatility shock accelerating")
    if not invalidation_conditions:
        invalidation_conditions.append("support breaks if coherence or confidence rolls over")

    deduped_conditions = list(dict.fromkeys(invalidation_conditions))
    edge_dependencies = [
        "coherent structure persists",
        "confidence remains aligned with structure",
        "transition pressure does not re-accelerate",
        "data quality stays usable",
    ]
    why_not_robust = (
        "Edge is not fully robust because "
        + (", ".join(fragility_sources[:3]) if fragility_sources else "its support is broad and stable")
        + "."
    )

    return FragilityResult(
        fragility_score=fragility_score,
        fragility_state=fragility_state,
        fragility_sources=fragility_sources,
        invalidation_conditions=deduped_conditions,
        dependency_map=dependency_map,
        edge_dependencies=edge_dependencies,
        why_not_robust=why_not_robust,
        edge_stability_window=edge_stability_window,
    )
