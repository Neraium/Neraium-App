from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperatorDecisionSupport:
    concise_summary: str
    concern: str
    first_inspection_target: str
    recommended_actions: list[str]


def build_operator_decision_support(
    *,
    interpreted_state: str,
    decision_state: str,
    confidence: str,
    attribution: dict[str, Any],
    regime_memory: dict[str, Any],
    risk_assessment: dict[str, Any],
) -> OperatorDecisionSupport:
    top_sensor = "unknown"
    sensors = attribution.get("top_sensors") or []
    if isinstance(sensors, list) and sensors:
        top_sensor = str((sensors[0] or {}).get("sensor", "unknown"))

    primary_cluster = str((attribution.get("subsystem_impact") or {}).get("primary_cluster", "none"))
    trend = str(risk_assessment.get("projected_near_term_trend", "uncertain"))
    trajectory = str(risk_assessment.get("trajectory", "drifting"))
    novelty = bool(regime_memory.get("is_novel", True))

    concern = (
        f"State={interpreted_state}/{decision_state}; projected trajectory is {trajectory} ({trend} risk trend), "
        f"with leading structural contributor {top_sensor}."
    )
    summary = (
        f"{concern} Pattern is {'novel' if novelty else 'similar to prior regimes'}; confidence={confidence}."
    )

    actions = [
        f"Inspect subsystem/cluster first: {primary_cluster}.",
        f"Validate sensor quality and calibration for {top_sensor} and its strongest linked pair.",
    ]
    if novelty:
        actions.append("Escalate for engineering review as potentially new failure trajectory.")
    else:
        actions.append("Compare with matched prior regime runbook and verify expected mitigation response.")
    if trend == "increasing":
        actions.append("Increase monitoring cadence for next analysis windows.")

    return OperatorDecisionSupport(
        concise_summary=summary,
        concern=concern,
        first_inspection_target=primary_cluster,
        recommended_actions=actions,
    )
