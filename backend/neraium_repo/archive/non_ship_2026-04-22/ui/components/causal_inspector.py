from __future__ import annotations

from ui.core_integration import SystemState


def render_causal_inspector(state: SystemState) -> dict[str, object]:
    """Floating local causal cues, kept lightweight and trajectory-adjacent."""
    return {
        "overlay": "causal_annotations",
        "placement": "near_current_position",
        "badge": {
            "regime_name": state.regime_state,
            "system_health": state.system_health,
            "confidence": round(state.confidence, 4),
            "drift": round(state.drift_intensity, 4),
        },
        "relationship_markers": [
            {
                "edge": f"{edge.source}->{edge.target}",
                "strength": edge.strength,
                "trend": edge.trend,
                "display": "marker",
            }
            for edge in state.structural_relationships
        ],
        "style": {"container": "floating", "shadow": "soft", "border": "none", "density": "compact"},
    }
