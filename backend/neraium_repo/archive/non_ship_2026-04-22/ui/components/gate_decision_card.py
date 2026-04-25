from __future__ import annotations

from datetime import datetime
from typing import Any


def _reality_status(decision: str | None) -> str:
    normalized = (decision or "SUPPRESS").upper()
    if normalized == "ADMIT":
        return "ADMITTED AS REAL"
    if normalized in {"ADMISSIBILITY_VOID", "VOID"}:
        return "Signal invalid"
    return "Not confirmed as real"


def _authority_level(decision: str | None) -> str:
    normalized = (decision or "SUPPRESS").upper()
    if normalized == "ADMIT":
        return "ADMITTED"
    if normalized in {"ADMISSIBILITY_VOID", "VOID"}:
        return "VOID"
    return "SUPPRESSED"


def _decision_label(authority_level: str) -> str:
    if authority_level == "ADMITTED":
        return "COHERENT SYSTEM CHANGE DETECTED"
    if authority_level == "VOID":
        return "SIGNAL INVALID"
    return "VARIATION SUPPRESSED"


def _format_timestamp(timestamp: Any) -> str:
    if not timestamp:
        return "—"
    raw = str(timestamp).strip()
    if not raw:
        return "—"
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw
    return parsed.strftime("%b %d, %I:%M:%S %p")


def _authority_statement(authority_level: str) -> str:
    if authority_level == "ADMITTED":
        return "Coherent reorganization confirmed in replay telemetry."
    if authority_level == "VOID":
        return "Observed signal failed coherence checks."
    return "Observed variation is below confirmation threshold."


def _supporting_line(authority_level: str, transition_type: str, risk_direction: str) -> str:
    """Short supporting line explaining what happened, readable in 1-2 seconds.

    Uses clear, authoritative language:
    - Change Intensity: magnitude of system movement
    - System Movement: detected directional shift
    - System Change: the actual transition event
    """
    if authority_level == "ADMITTED":
        if risk_direction == "DEGRADING":
            return "System moving away from baseline. Change intensity increasing."
        elif risk_direction == "UNCERTAIN":
            return "System change confirmed; direction stabilizing."
        return "Coherent system change with stable trajectory."
    if authority_level == "VOID":
        return "Insufficient signal integrity for determination."
    # SUPPRESSED
    if risk_direction == "STABLE":
        return "System remains within normal operating baseline."
    return "No sustained system movement detected."


def _confidence_label(raw_confidence: str | None) -> str:
    normalized = (raw_confidence or "LOW").upper()
    if normalized in {"HIGH", "MEDIUM", "LOW"}:
        return normalized
    return "LOW"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _transition_intensity(transition: dict[str, Any], persistence_minutes: Any) -> str:
    drift = abs(_to_float(transition.get("delta_drift")) or 0.0)
    stability_drop = max(0.0, -(_to_float(transition.get("delta_stability")) or 0.0))
    persistence = max(0.0, _to_float(persistence_minutes) or 0.0)

    if drift >= 0.30 or stability_drop >= 0.30 or persistence >= 60:
        return "HIGH"
    if drift >= 0.12 or stability_drop >= 0.12 or persistence >= 20:
        return "MODERATE"
    return "LOW"


def _normalize_transition_type(transition_type: Any) -> str:
    """Normalize transition type to canonical forms.

    Returns one of: STABLE, TRANSITION, REORGANIZATION
    """
    if isinstance(transition_type, str):
        normalized = transition_type.strip().upper()
        # Canonicalize variations
        if normalized in {"STABLE", "BASELINE", "COHERENCE", "STABLE_BASELINE"}:
            return "STABLE"
        if normalized in {"TRANSITION", "DRIFT", "TRANSITION_ACTIVE", "DRIFT_WATCH"}:
            return "TRANSITION"
        if normalized in {"REORGANIZATION", "REORGANIZATION_UNDERWAY", "DIVERGENCE"}:
            return "REORGANIZATION"
        if normalized:
            return normalized
    return "STABLE"


def _trend_indicator(delta: Any, *, invert: bool = False) -> dict[str, str]:
    value = _to_float(delta) or 0.0
    if abs(value) < 0.01:
        return {"direction": "flat", "arrow": "→", "label": "Stable"}
    rising = value > 0
    if invert:
        rising = not rising
    if rising:
        return {"direction": "up", "arrow": "↑", "label": "Increasing"}
    return {"direction": "down", "arrow": "↓", "label": "Decreasing"}


def _map_system_state(transition_type: str, authority_level: str, drift_delta: float) -> str:
    normalized_transition = transition_type.upper()
    if normalized_transition in {"INSTABILITY", "REORGANIZATION", "DIVERGENCE"} or drift_delta >= 0.30:
        return "Alert"
    if normalized_transition in {"TRANSITION", "DRIFT"} or drift_delta >= 0.12:
        return "Drifting"
    if authority_level == "SUPPRESSED":
        return "Baseline"
    return "Stable"


def _insight_text(system_state: str, authority_level: str, drift_trend: str) -> str:
    if system_state == "Alert":
        return "Relational instability emerging"
    if system_state == "Drifting":
        if drift_trend == "up":
            return "Drift increasing but below alert threshold"
        return "System movement detected; monitor for threshold escalation"
    if system_state == "Stable" and authority_level == "ADMITTED":
        return "System remains within baseline structure"
    return "System remains within baseline structure"


def _operator_takeaway(
    authority_level: str,
    transition_type: str,
    transition_intensity: str,
    risk_direction: str,
) -> str:
    if authority_level == "ADMITTED":
        if risk_direction == "UNCERTAIN":
            return "Confirmed transition; direction still forming."
        return f"{transition_intensity} intensity {transition_type} transition."
    if authority_level == "VOID":
        return "Signal invalid for persistent transition."
    return "No persistent baseline break confirmed."


def _risk_direction(transition_type: str, transition: dict[str, Any], authority_level: str) -> str:
    if authority_level == "VOID":
        return "UNCERTAIN"

    drift = _to_float(transition.get("delta_drift")) or 0.0
    stability_delta = _to_float(transition.get("delta_stability")) or 0.0
    coherence_delta = _to_float(transition.get("delta_coherence")) or 0.0
    normalized_transition = (transition_type or "STABLE").upper()

    degrading_transition = normalized_transition in {"INSTABILITY", "DEGRADING", "DIVERGENCE"}
    stable_transition = normalized_transition in {"STABLE", "RECOVERY"}
    no_directional_evidence = drift == 0.0 and stability_delta == 0.0 and coherence_delta == 0.0

    if degrading_transition or drift >= 0.12 or stability_delta <= -0.12:
        return "DEGRADING"
    if authority_level == "ADMITTED" and no_directional_evidence:
        return "UNCERTAIN"
    if stable_transition and abs(drift) < 0.12 and abs(stability_delta) < 0.12:
        return "STABLE"
    return "UNCERTAIN"


def _trajectory_statement(authority_level: str, risk_direction: str) -> str:
    if authority_level == "VOID":
        return "Trajectory unresolved under current coherence."
    if authority_level == "SUPPRESSED" and risk_direction == "STABLE":
        return "No sustained directional shift detected."
    if risk_direction == "DEGRADING":
        return "System moving away from stable conditions."
    if risk_direction == "STABLE":
        return "System trajectory remains within stable conditions."
    return "Directional trajectory remains uncertain."


def _if_sustained_statement(risk_direction: str, authority_level: str) -> str:
    if authority_level == "VOID" or risk_direction == "UNCERTAIN":
        return "If sustained: projection remains withheld."
    if risk_direction == "DEGRADING":
        return "If sustained: regime transition likely."
    return "If sustained: no regime change expected."


def render_gate_decision_card(decision: dict[str, Any] | None) -> dict[str, Any]:
    gate = decision or {}
    authority_level = _authority_level(gate.get("decision"))
    refusal_reason = gate.get("refusal_reason")
    reason = gate.get("reason") or gate.get("explanation") or refusal_reason

    transition = gate.get("transition") if isinstance(gate.get("transition"), dict) else {}
    transition_type = _normalize_transition_type(transition.get("type"))
    intensity = _transition_intensity(transition, gate.get("persistence_minutes"))
    drift_delta = _to_float(transition.get("delta_drift")) or 0.0
    stability_delta = _to_float(transition.get("delta_stability")) or 0.0
    coherence_delta = _to_float(transition.get("delta_coherence")) or 0.0
    risk_direction = _risk_direction(transition_type, transition, authority_level)
    timestamp = gate.get("timestamp")
    formatted_timestamp = _format_timestamp(timestamp)
    drift_trend = _trend_indicator(drift_delta)
    stability_trend = _trend_indicator(stability_delta, invert=True)
    coherence_trend = _trend_indicator(coherence_delta)
    duration_trend = _trend_indicator(gate.get("persistence_minutes"))
    phase_context = str(gate.get("phase_label") or transition_type.replace("_", " ").title())
    if phase_context.strip().lower() == "ramp up":
        phase_context = "Ramp Up (System stabilizing)"
    system_state = _map_system_state(transition_type, authority_level, drift_delta)

    return {
        "component": "gate_authority_banner",
        "visual_priority": "primary",
        "layout_weight": "dominant",
        "headline_priority": "maximum",
        "reality_status": _reality_status(gate.get("decision")),
        "authority_surface": "Aletheia's Gate",
        "authority_level": authority_level,
        "label": _decision_label(authority_level),
        "authority_badge": authority_level,
        "authority_statement": _authority_statement(authority_level),
        "supporting_line": _supporting_line(authority_level, transition_type, risk_direction),
        "confidence": _confidence_label(gate.get("confidence_label")),
        "transition_type": transition_type,
        "state_transition_label": "State Transition",
        "state_transition": "Confirmed",
        "decision_label": "Decision",
        "decision_status": "Accepted" if authority_level == "ADMITTED" else "Observed",
        "transition_intensity": intensity,
        "operator_takeaway_label": "Operator Takeaway",
        "operator_takeaway": _operator_takeaway(authority_level, transition_type, intensity, risk_direction),
        "operator_takeaway_brief": _operator_takeaway(authority_level, transition_type, intensity, risk_direction),
        "trajectory_statement": _trajectory_statement(authority_level, risk_direction),
        "risk_direction": risk_direction,
        "secondary_row": {
            "risk_direction": risk_direction,
            "transition_type": transition_type,
        },
        "if_sustained_statement": _if_sustained_statement(risk_direction, authority_level),
        "doctrine_version": gate.get("doctrine_version") or "unknown",
        "timestamp": timestamp,
        "timestamp_label": "Change evaluated at",
        "timestamp_display": f"Change evaluated at: {formatted_timestamp}" if formatted_timestamp != "—" else "Change evaluated at: unknown",
        "reason": reason,
        "refusal_reason": refusal_reason,
        "criteria_summary": gate.get("criteria_summary") or gate.get("observed_facts") or [],
        "what_changed": {
            "title": "What Changed",
            "structural_drift": transition.get("delta_drift"),
            "stability": transition.get("delta_stability"),
            "coherence": transition.get("delta_coherence"),
            "persistence_minutes": gate.get("persistence_minutes"),
            "transition_type": transition_type,
            "transition_intensity": intensity,
        },
        "system_insights": {
            "title": "System Insights",
            "system_state_label": "System State",
            "system_state": system_state,
            "phase_label": "Phase Context",
            "phase_context": phase_context,
            "decision": "Decision: Accepted" if authority_level == "ADMITTED" else "Signal Accepted",
            "state_transition": "State Transition: Confirmed",
            "metrics": [
                {"label": "Structural Drift", "value": round(drift_delta, 3), "trend": drift_trend},
                {"label": "Relational Stability", "value": round(stability_delta, 3), "trend": stability_trend},
                {"label": "Current State Duration", "value": round(_to_float(gate.get("persistence_minutes")) or 0.0, 1), "trend": duration_trend},
                {"label": "Coherence Shift", "value": round(coherence_delta, 3), "trend": coherence_trend},
            ],
            "timestamp_label": "Last Evaluated",
            "timestamp_display": formatted_timestamp,
            "insight_label": "System Insight",
            "insight_text": _insight_text(system_state, authority_level, drift_trend["direction"]),
        },
        "no_signal_admitted": authority_level == "SUPPRESSED",
        "absence_statement": (
            "No admissible system change detected."
            if authority_level == "SUPPRESSED"
            else None
        ),
    }
