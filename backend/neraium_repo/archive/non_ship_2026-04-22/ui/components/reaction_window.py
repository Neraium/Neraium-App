from __future__ import annotations

from ui.core_integration import SystemState
from ui.utils import clamp, l2_norm


def render_reaction_window_indicator(state: SystemState) -> dict[str, object]:
    """Global directional indicator of remaining stability reaction margin."""
    velocity_mag = l2_norm(state.velocity)
    stable_ceiling = state.stability_regions.get("stable_basin", (0.0, 0.35))[1]
    distance_to_instability = max(0.0, stable_ceiling - state.position.x)
    directional_load = clamp(max(0.0, state.velocity[0]) + max(0.0, state.velocity[1]), 0.0, 1.0)
    pressure = clamp(
        state.drift_intensity * 0.55 + velocity_mag * 0.75 + directional_load * 0.45 + (1.0 - distance_to_instability) * 0.35,
        0.0,
        1.0,
    )

    return {
        "overlay": "reaction_window",
        "placement": "global_forward_field",
        "remaining": {
            "distance": round(distance_to_instability, 4),
            "minutes": round(max(1.0, (1.0 - pressure) * 60.0), 2),
            "pressure": round(pressure, 4),
        },
        "visual": {
            "indicator": "shrinking_arc",
            "forward_gradient": "pressure_field",
            "arc_completion": round(1.0 - pressure, 4),
            "boundary_fade": round(clamp(0.2 + pressure * 0.6, 0.2, 0.9), 4),
            "tone": "cool" if pressure < 0.4 else "transition" if pressure < 0.7 else "warm",
        },
    }
