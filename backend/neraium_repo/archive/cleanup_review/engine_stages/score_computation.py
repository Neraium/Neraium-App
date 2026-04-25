from __future__ import annotations

from dataclasses import dataclass

from neraium_core.scoring import (
    canonicalize_components,
    canonicalize_weights,
    composite_instability_score_normalized,
)


@dataclass(frozen=True)
class ScoreComputationInput:
    base_components: dict[str, float]
    raw_components: dict[str, float]
    evidence_confidence: float
    correlation_ready: bool
    regime_factor: float
    transition_aware_enabled: bool


@dataclass(frozen=True)
class ScoreComputationResult:
    components: dict[str, float]
    component_confidence: dict[str, float]
    weights_for_composite: dict[str, float]
    components_for_decision: dict[str, float]
    composite_score: float


def compute_scores(stage_input: ScoreComputationInput) -> ScoreComputationResult:
    base_components = dict(stage_input.base_components)
    raw_canonical = canonicalize_components(stage_input.raw_components)
    raw_canonical["early_warning"] = float(base_components.get("early_warning", 0.0))
    base_components.update(raw_canonical)
    components = base_components

    tier1_components = {"relational_drift", "regime_drift", "spectral", "early_warning"}
    if stage_input.transition_aware_enabled:
        tier1_components.add("transition_pressure")

    component_confidence: dict[str, float] = {k: 0.0 for k in components.keys()}
    component_confidence["relational_drift"] = stage_input.evidence_confidence if stage_input.correlation_ready else 0.0
    component_confidence["spectral"] = stage_input.evidence_confidence if stage_input.correlation_ready else 0.0
    component_confidence["early_warning"] = stage_input.evidence_confidence
    component_confidence["regime_drift"] = (
        stage_input.evidence_confidence * stage_input.regime_factor if stage_input.correlation_ready else 0.0
    )
    if stage_input.transition_aware_enabled:
        component_confidence["transition_pressure"] = (
            stage_input.evidence_confidence if stage_input.correlation_ready else 0.0
        )

    for k in list(component_confidence.keys()):
        if k not in tier1_components:
            component_confidence[k] = 0.0

    base_weights = canonicalize_weights()
    weights_for_composite = {k: float(w) * float(component_confidence.get(k, 0.0)) for k, w in base_weights.items()}
    components_for_decision = {
        k: float(v) * float(component_confidence.get(k, 0.0)) if k in component_confidence else float(v)
        for k, v in components.items()
    }
    composite = float(composite_instability_score_normalized(components, weights=weights_for_composite))

    return ScoreComputationResult(
        components=components,
        component_confidence=component_confidence,
        weights_for_composite=weights_for_composite,
        components_for_decision=components_for_decision,
        composite_score=composite,
    )
