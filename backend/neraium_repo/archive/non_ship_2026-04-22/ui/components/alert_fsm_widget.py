from __future__ import annotations

from ui.core_integration import SystemState


def render_alert_fsm_widget(state: SystemState) -> dict[str, object]:
    """Subtle local state markers for regime shifts (not banner alerts)."""
    if state.drift_intensity >= 0.7:
        phase = "divergence"
    elif state.drift_intensity >= 0.4:
        phase = "transition"
    else:
        phase = "coherence"

    return {
        "overlay": "state_markers",
        "phase": phase,
        "regime": state.regime_state,
        "drift": round(state.drift_intensity, 4),
        "marker": {
            "style": "pulse_dot",
            "severity": phase,
            "banner": False,
            "placement": "near_position",
            "intensity": round(min(1.0, 0.35 + state.drift_intensity * 0.9), 4),
        },
    }
