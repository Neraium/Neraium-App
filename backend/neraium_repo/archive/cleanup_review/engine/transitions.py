"""Transition pressure and regime tracking.

Responsibilities:
- Transition pressure computation
- Shock detection and activity tracking
- Regime novelty and baseline updates
- Dominant mode and manifold tracking
- Transition state classification (NONE/EMERGING/SUSTAINED)
- Engine readiness assessment

Note: This module is complex and will be populated from alignment.py
_transition_metrics() and related methods. Stub for architecture clarity.
"""

from typing import Dict, Any, Optional
import numpy as np
from collections import deque

from .config import TRANSITION_EMERGING_THRESHOLD, TRANSITION_SUSTAINED_THRESHOLD


class TransitionMetricsComputer:
    """Computes transition pressure from drift, spectral, and regime signals."""

    def __init__(self):
        self._transition_pressure_ema: float = 0.0
        self._low_transition_activity_streak: int = 0
        self._prev_stable_novelty: float = 0.0
        self._prev_regime_novelty: float = 0.0
        self._shock_boost_steps_remaining: int = 0
        self._shock_refractory_steps: int = 0
        self._prev_spectral_radius: float | None = None

    def compute(
        self,
        drift_score: float,
        corr_recent: np.ndarray,
        regime_distance: Optional[float],
        temporal_features: Optional[Dict[str, Any]] = None,
        temporal_quality: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute transition pressure and related metrics.

        Args:
            drift_score: Structural drift score
            corr_recent: Recent correlation matrix
            regime_distance: Distance to nearest regime
            temporal_features: Temporal velocity/acceleration
            temporal_quality: Temporal consistency quality

        Returns:
            Dictionary with transition metrics including pressure
        """
        # Placeholder: Full implementation moved from alignment._transition_metrics()
        # This will include:
        # - Short horizon drift computation
        # - Acceleration from drift history
        # - Regime novelty from regime distance
        # - Edge flip rate from adjacency changes
        # - Dominant mode rotation
        # - Shock detection and boost
        # - Transition pressure EMA and gating

        return {
            "short_horizon_drift": 0.0,
            "consecutive_step_acceleration": 0.0,
            "correlation_spike": 0.0,
            "novelty_spike": 0.0,
            "corr_jump_raw": 0.0,
            "spectral_jump_raw": 0.0,
            "shock_triggered": 0.0,
            "shock_boost": 0.0,
            "stable_manifold_novelty": 0.0,
            "regime_novelty": 0.0,
            "graph_edge_flip_rate": 0.0,
            "dominant_mode_rotation": 0.0,
            "transition_pressure": 0.0,
            "temporal_consistency": 1.0,
            "timestamp_gap_irregularity": 0.0,
            "timing_velocity": 0.0,
            "timing_acceleration": 0.0,
        }


def classify_transition_state(
    pressure_history: deque[float],
) -> str:
    """Classify transition from recent pressure history.

    Args:
        pressure_history: Deque of recent transition pressures

    Returns:
        State: "NONE", "EMERGING_TRANSITION", or "SUSTAINED_TRANSITION"
    """
    if not pressure_history:
        return "NONE"

    history = list(pressure_history)
    recent = history[-min(4, len(history)) :]

    sustained = sum(1 for v in recent if v >= TRANSITION_SUSTAINED_THRESHOLD)
    emerging = sum(1 for v in recent if v >= TRANSITION_EMERGING_THRESHOLD)
    current = float(recent[-1])

    if (current >= TRANSITION_SUSTAINED_THRESHOLD and sustained >= 2) or sustained >= 3:
        return "SUSTAINED_TRANSITION"
    if (current >= TRANSITION_EMERGING_THRESHOLD and emerging >= 2):
        return "EMERGING_TRANSITION"
    return "NONE"
