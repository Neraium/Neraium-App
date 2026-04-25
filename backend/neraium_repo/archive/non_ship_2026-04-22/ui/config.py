from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class UIConfig:
    title: str = "Neraium SII Navigator"
    api_base_url: str = "http://127.0.0.1:8000"
    ws_endpoint: str = "ws://127.0.0.1:8000/ws/telemetry"
    trajectory_tail: int = 36
    projection_horizon_steps: int = 6
    reaction_window_default_minutes: float = 30.0


def load_ui_config() -> UIConfig:
    return UIConfig(
        title=os.getenv("NERAIUM_UI_TITLE", UIConfig.title),
        api_base_url=os.getenv("NERAIUM_UI_API_BASE_URL", UIConfig.api_base_url),
        ws_endpoint=os.getenv("NERAIUM_UI_WS_ENDPOINT", UIConfig.ws_endpoint),
        trajectory_tail=int(os.getenv("NERAIUM_UI_TRAJECTORY_TAIL", str(UIConfig.trajectory_tail))),
        projection_horizon_steps=int(
            os.getenv("NERAIUM_UI_PROJECTION_HORIZON_STEPS", str(UIConfig.projection_horizon_steps))
        ),
        reaction_window_default_minutes=float(
            os.getenv(
                "NERAIUM_UI_REACTION_WINDOW_DEFAULT_MINUTES",
                str(UIConfig.reaction_window_default_minutes),
            )
        ),
    )
