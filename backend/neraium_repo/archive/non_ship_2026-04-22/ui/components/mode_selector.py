from __future__ import annotations


def render_mode_selector(mode: str) -> dict[str, str]:
    resolved = mode if mode in {"pilot", "operations", "demo"} else "pilot"
    return {"mode": resolved, "surface": "system_navigation_surface"}
