from __future__ import annotations

from ui.core_integration import SystemState


def render_attribution_viz(state: SystemState) -> dict[str, object]:
    """Contextual attribution callouts anchored to recent trajectory segments."""
    speed = round(min(1.0, abs(state.velocity[0]) + abs(state.velocity[1])), 4)
    factors = [
        {"factor": "drift_intensity", "value": round(state.drift_intensity, 4), "tone": "warm"},
        {"factor": "trajectory_speed", "value": speed, "tone": "neutral"},
        {"factor": "confidence", "value": round(state.confidence, 4), "tone": "cool"},
    ]

    popups = []
    for idx, point in enumerate(state.trajectory_history[-3:]):
        strength = round(0.2 + (idx + 1) / 3 * 0.8, 4)
        popups.append(
            {
                "anchor": {"x": point.x, "y": point.y, "t": point.t},
                "context": sorted(factors, key=lambda x: x["value"], reverse=True)[:2],
                "intensity": strength,
                "offset": {"dx": round(0.01 * (idx + 1), 4), "dy": round(-0.012 * (idx + 1), 4)},
            }
        )

    return {
        "overlay": "trajectory_context_popups",
        "placement": "contextual",
        "popups": popups,
        "style": {"chrome": "minimal", "connector": "hairline_glow", "panel": "none"},
    }
