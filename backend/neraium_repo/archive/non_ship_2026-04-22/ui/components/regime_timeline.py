from __future__ import annotations

from ui.core_integration import SystemState


def render_regime_timeline(state: SystemState) -> dict[str, object]:
    """Thin bottom-edge motion cue overlay."""
    events = [
        {
            "timestamp": event.t,
            "regime": event.regime,
            "drift_acceleration": event.drift_delta,
            "reaction_window_minutes": event.reaction_window_minutes,
        }
        for event in state.timeline
    ]
    return {
        "overlay": "timeline_strip",
        "placement": "bottom_edge",
        "thickness": "hairline",
        "events": events,
        "style": {
            "density": "compact",
            "background": "transparent",
            "separator": "soft_glow",
            "labels": "minimal",
            "hierarchy": {
                "history_track": {"opacity": 0.44, "priority": "secondary"},
                "latest_marker": {"opacity": 0.92, "priority": "primary"},
            },
            "tones": {
                "baseline": "#6E7D9D",
                "transition": "#8F87FF",
                "reorganization": "#FF9E78",
            },
        },
    }
