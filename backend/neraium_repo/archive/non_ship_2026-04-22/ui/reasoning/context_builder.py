from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ui.reasoning.models import AdmittedEvent
from ui.core_integration import SystemState


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_event_admitted(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return None


def _summarize_event(event: AdmittedEvent, *, drift_threshold: float, stability_threshold: float) -> str:
    reasons: list[str] = []
    if event.drift >= drift_threshold:
        reasons.append(f"drift {event.drift:.3f} exceeded {drift_threshold:.3f}")
    if event.stability <= stability_threshold:
        reasons.append(f"stability {event.stability:.3f} stayed below {stability_threshold:.3f}")
    if not reasons:
        reasons.append("no admission threshold breach was observed")
    return "; ".join(reasons)


def _state_summary(row: dict[str, Any] | None) -> str:
    source = row or {}
    drift = _as_float(source.get("structural_drift_score", source.get("drift")), 0.0)
    stability = _as_float(source.get("relational_stability_score", source.get("stability")), 1.0)
    regime = str(source.get("regime_name") or source.get("regime") or "unknown")
    return f"regime={regime}, drift={drift:.3f}, stability={stability:.3f}"


def build_admitted_events(
    records: list[dict[str, Any]] | None,
    *,
    drift_threshold: float = 0.55,
    stability_threshold: float = 0.45,
) -> list[AdmittedEvent]:
    events: list[AdmittedEvent] = []
    rows = records or []
    for idx, row in enumerate(rows):
        previous = rows[idx - 1] if idx > 0 else None
        drift = _as_float(row.get("structural_drift_score", row.get("drift", 0.0)), 0.0)
        stability = _as_float(row.get("relational_stability_score", row.get("stability", 1.0)), 1.0)
        admitted_from_row = _parse_event_admitted(row.get("event_admitted"))
        event_admitted = admitted_from_row if admitted_from_row is not None else bool(
            drift >= drift_threshold and stability <= stability_threshold
        )
        event = AdmittedEvent(
            timestamp=str(row.get("timestamp") or "unknown"),
            drift=round(drift, 6),
            stability=round(stability, 6),
            regime=str(row.get("regime_name") or row.get("regime") or "unknown"),
            event_admitted=event_admitted,
            evidence_summary=str(
                row.get("evidence_summary")
                or _summarize_event(
                    AdmittedEvent(
                        timestamp="",
                        drift=drift,
                        stability=stability,
                        regime="",
                        event_admitted=event_admitted,
                        evidence_summary="",
                    ),
                    drift_threshold=drift_threshold,
                    stability_threshold=stability_threshold,
                )
            ),
            previous_state_summary=_state_summary(previous),
            current_state_summary=_state_summary(row),
            transition_type=str(row.get("transition_type") or ("TRANSITION" if previous is not None else "STABLE")),
        )
        events.append(event)
    return events


def _trend_fact(metric: str, previous: float | None, current: float) -> str:
    if previous is None:
        return f"{metric} has no prior sample (current {current:.3f})"

    displayed_previous = round(previous, 3)
    displayed_current = round(current, 3)
    delta = displayed_current - displayed_previous
    if delta > 0:
        verb = "increased"
    elif delta < 0:
        verb = "decreased"
    else:
        verb = "was unchanged"

    if delta == 0:
        return f"{metric} {verb} at {displayed_current:.3f}"
    return f"{metric} {verb} from {previous:.3f} → {current:.3f}"


def build_reasoning_context(
    state: SystemState,
    records: list[dict[str, Any]] | None = None,
    *,
    gate_decision: dict[str, Any] | None = None,
    max_recent_events: int = 6,
) -> dict[str, Any]:
    admitted_events = [event for event in build_admitted_events(records) if event.event_admitted]

    gate = gate_decision or {}
    decision = str(gate.get("decision") or "SUPPRESS").upper()
    latest_timestamp = str(records[-1].get("timestamp")) if records else None
    if decision == "SUPPRESS" and latest_timestamp is not None:
        admitted_events = [event for event in admitted_events if event.timestamp != latest_timestamp]

    transition_point = admitted_events[0].timestamp if admitted_events else None

    top_signals = None
    if records:
        latest = records[-1]
        candidate = latest.get("top_contributing_signals") or latest.get("signal_attribution")
        if isinstance(candidate, list):
            top_signals = candidate[:5]

    drift_direction = "elevated"
    if state.velocity[0] < 0:
        drift_direction = "easing"

    stability_direction = "low"
    if state.velocity[1] < 0:
        stability_direction = "recovering"

    transition = gate.get("transition") if isinstance(gate.get("transition"), dict) else {}
    has_previous_row = bool(records and len(records) > 1)
    previous_row = records[-2] if has_previous_row else {}
    current_row = records[-1] if records else {}
    prev_drift = _as_float(previous_row.get("structural_drift_score", previous_row.get("drift")), 0.0) if has_previous_row else None
    curr_drift = _as_float(current_row.get("structural_drift_score", current_row.get("drift")), 0.0)
    prev_stability = _as_float(previous_row.get("relational_stability_score", previous_row.get("stability")), 1.0) if has_previous_row else None
    curr_stability = _as_float(current_row.get("relational_stability_score", current_row.get("stability")), 1.0)
    context = {
        "current_state": {
            "timestamp": state.position.t,
            "regime": state.regime_state,
            "system_health": state.system_health,
            "confidence": round(state.confidence, 4),
            "drift": round(state.drift_intensity, 4),
            "stability": round(1.0 - state.position.y, 4),
            "velocity": {"dx": round(state.velocity[0], 6), "dy": round(state.velocity[1], 6)},
        },
        "gate_decision": {
            "decision": gate.get("decision"),
            "reason": gate.get("refusal_reason") or gate.get("explanation") or gate.get("reason"),
            "doctrine_version": gate.get("doctrine_version"),
            "confidence_label": gate.get("confidence_label"),
        },
        "recent_admitted_events": [asdict(event) for event in admitted_events[-max_recent_events:]],
        "transition_point": transition_point,
        "drift_summary": f"Structural drift is currently {drift_direction}.",
        "stability_summary": f"Relational stability remains {stability_direction}.",
        "top_contributing_signals": top_signals,
        "chart_replay_summary": {
            "trajectory_points": len(state.trajectory_history),
            "projected_points": len(state.projected_cone),
            "current_position": {"x": state.position.x, "y": state.position.y},
        },
        "temporal_facts": [
            _trend_fact("Drift", prev_drift, curr_drift),
            _trend_fact("Stability", prev_stability, curr_stability),
        ],
        "transition": transition,
    }
    return context
