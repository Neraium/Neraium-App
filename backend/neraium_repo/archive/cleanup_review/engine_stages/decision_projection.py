from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from neraium_core.explanation_layer import build_explanation_text
from neraium_core.staged_pipeline import AttributionStage, DecisionStage

TRANSITION_EMERGING_THRESHOLD = 0.85
TRANSITION_SUSTAINED_THRESHOLD = 1.15


class DecisionProjectionContext(Protocol):
    transition_aware_enabled: bool


@dataclass(frozen=True)
class DecisionProjectionInput:
    result: dict[str, Any]
    analytics: dict[str, Any]
    decision: dict[str, Any]
    components: dict[str, float]
    temporal_quality: dict[str, Any]
    data_quality_timestamp_irregularity: float
    forecast_trend: float
    stabilized_confidence: float
    composite_score: float


def apply_transition_state_mapping(context: DecisionProjectionContext, result: dict[str, Any]) -> None:
    if not context.transition_aware_enabled:
        return
    transition_pressure = float(result.get("transition_pressure", 0.0))
    transition_state = str(result.get("transition_state", "NONE"))
    state_rank = {"STABLE": 0, "WATCH": 1, "ALERT": 2}
    current_state = str(result.get("state", "STABLE"))
    target_state = current_state
    if transition_state == "WARMUP":
        target_state = current_state
    elif transition_state == "SUSTAINED_TRANSITION" and transition_pressure >= TRANSITION_SUSTAINED_THRESHOLD:
        target_state = "ALERT"
    elif transition_state == "EMERGING_TRANSITION" and transition_pressure >= TRANSITION_EMERGING_THRESHOLD:
        target_state = "WATCH"
    if state_rank.get(target_state, 0) > state_rank.get(current_state, 0):
        result["state"] = target_state
        result["drift_alert"] = target_state == "ALERT"


def project_decision_and_explanation(
    stage_input: DecisionProjectionInput,
) -> tuple[str, dict[str, float]]:
    result = stage_input.result
    analytics = stage_input.analytics

    stage_interpreted = DecisionStage.interpreted_state(
        structural=float(stage_input.components.get("drift", 0.0)),
        relational=float(stage_input.components.get("relational_drift", 0.0)),
        regime_distance=float(stage_input.components.get("regime_drift", 0.0)),
        temporal_distortion=float(stage_input.components.get("temporal_distortion", 0.0)),
        localization=1.0,
        trend=float(stage_input.forecast_trend),
    )
    if str(result.get("interpreted_state", "NOMINAL_STRUCTURE")) == "NOMINAL_STRUCTURE":
        if stage_interpreted != "NOMINAL_STRUCTURE":
            result["interpreted_state"] = stage_interpreted
        else:
            rel = float(stage_input.components.get("relational_drift", 0.0))
            drf = float(stage_input.components.get("drift", 0.0))
            if rel > 0.9:
                result["interpreted_state"] = "COUPLING_INSTABILITY_OBSERVED"
            elif drf > 1.1:
                result["interpreted_state"] = "STRUCTURAL_INSTABILITY_OBSERVED"

    result["confidence_score"] = round(stage_input.stabilized_confidence, 4)
    result["latest_instability"] = round(float(stage_input.composite_score), 4)
    result["relational_instability_score"] = round(float(stage_input.components.get("relational_drift", 0.0)), 4)
    result["temporal_distortion_score"] = round(
        float(stage_input.components.get("temporal_distortion", stage_input.data_quality_timestamp_irregularity)), 4
    )
    result["temporal_consistency_score"] = round(float(stage_input.temporal_quality.get("temporal_consistency_score", 0.0)), 4)
    result["ordering_stability_score"] = round(float(stage_input.temporal_quality.get("ordering_stability_score", 0.0)), 4)
    result["timestamp_gap_irregularity"] = round(float(stage_input.temporal_quality.get("timestamp_gap_irregularity", 0.0)), 4)
    result["alignment_confidence"] = round(float(stage_input.temporal_quality.get("alignment_confidence", 0.0)), 4)
    result["effective_sampling_density"] = round(
        float(stage_input.temporal_quality.get("effective_sampling_density", 0.0)),
        4,
    )
    result["localization_score"] = 0.0

    explain_components = {
        "structural_drift_score": float(result.get("structural_drift_score", 0.0)),
        "relational_instability_score": float(result.get("relational_instability_score", 0.0)),
        "regime_distance": float(result.get("regime_distance", 0.0) or 0.0),
        "temporal_distortion_score": float(result.get("temporal_distortion_score", 0.0)),
    }
    msg, contrib = AttributionStage.explain(explain_components, str(result.get("state", "STABLE")))
    result["explanation"] = msg
    analytics["component_contributions"] = contrib
    if contrib:
        result["dominant_driver"] = max(contrib.items(), key=lambda item: item[1])[0]

    recommended_action = None
    recs = result.get("response_recommendations")
    if isinstance(recs, list) and recs:
        first_rec = recs[0]
        if isinstance(first_rec, dict):
            recommended_action = str(first_rec.get("action", "") or "").strip() or None

    result["explanation_text"] = build_explanation_text(
        current_decision=str(result.get("interpreted_state", "NOMINAL_STRUCTURE")),
        attribution=result.get("attribution") if isinstance(result.get("attribution"), dict) else None,
        risk=result.get("risk_level"),
        confidence=result.get("confidence"),
        recommended_action=recommended_action,
    )
    result["geometry"] = analytics.get("geometry", {}) if isinstance(analytics, dict) else {}
    result["state_space_statistics"] = analytics.get("state_space_statistics", {}) if isinstance(analytics, dict) else {}
    result["state_graph"] = analytics.get("state_graph", {}) if isinstance(analytics, dict) else {}
    result["geometry_explanations"] = analytics.get("geometry_explanations", {}) if isinstance(analytics, dict) else {}
    return msg, contrib
