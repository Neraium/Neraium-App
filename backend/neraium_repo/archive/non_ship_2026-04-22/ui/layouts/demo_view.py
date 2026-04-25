from __future__ import annotations

from ui.core_integration import SystemState
from ui.layouts.responsive import build_navigation_surface


def build_demo_view(state: SystemState, *, width_px: int = 1440) -> dict[str, object]:
    return build_navigation_surface(state, mode="demo", width_px=width_px)
