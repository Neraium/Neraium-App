"""Monotonic time-to-failure probability distribution layer.

This is not a point RUL estimate. It maps current and past structural dynamics
to calibrated-looking, monotonic horizon probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


@dataclass(frozen=True)
class FailureTimeDistributionModel:
    """Simple constrained monotonic model over structural trajectory features."""

    def predict(
        self,
        *,
        drift_score: float,
        drift_velocity: float,
        acceleration: float,
        time_in_watch: int,
        time_in_alert: int,
        trajectory: str,
        recovery_probability: float,
        degradation_probability: float,
        lock_in_probability: float,
        baseline_ready: bool,
    ) -> Dict[str, Any]:
        drift = self._clamp(drift_score)
        velocity = max(float(drift_velocity), 0.0)
        accel = max(float(acceleration), 0.0)
        watch = max(int(time_in_watch), 0)
        alert = max(int(time_in_alert), 0)
        recovery = self._clamp(recovery_probability)
        degradation = self._clamp(degradation_probability)
        lock_in = self._clamp(lock_in_probability)

        state_pressure = min(watch / 60.0, 1.0) * 0.35 + min(alert / 35.0, 1.0) * 0.65
        trajectory_pressure = {
            "STABLE": 0.0,
            "RECOVERY": 0.08,
            "DEGRADATION": 0.45,
            "LOCK_IN": 0.85,
        }.get(str(trajectory or "STABLE"), 0.20)

        monotonic_score = (
            0.30 * drift
            + 0.14 * min(velocity * 8.0, 1.0)
            + 0.12 * min(accel * 25.0, 1.0)
            + 0.15 * state_pressure
            + 0.13 * degradation
            + 0.10 * lock_in
            + 0.06 * (1.0 - recovery)
            + 0.10 * trajectory_pressure
        )
        monotonic_score = self._clamp(monotonic_score)

        if not baseline_ready:
            confidence = "LOW"
            reason_codes = ["BASELINE_FORMING"]
        elif monotonic_score < 0.25:
            confidence = "LOW"
            reason_codes = ["LOW_STRUCTURAL_PRESSURE"]
        elif alert > 0 or lock_in >= 0.35 or trajectory == "LOCK_IN":
            confidence = "HIGH"
            reason_codes = ["ALERT_TIME_ACCUMULATED", "TRAJECTORY_PRESSURE"]
        else:
            confidence = "MEDIUM"
            reason_codes = ["WATCH_TIME_ACCUMULATED", "MONOTONIC_DRIFT_PRESSURE"]

        probabilities = {
            "within_50_cycles": self._sigmoid(-4.0 + 4.0 * monotonic_score),
            "within_100_cycles": self._sigmoid(-3.2 + 4.2 * monotonic_score),
            "within_200_cycles": self._sigmoid(-2.6 + 4.4 * monotonic_score),
        }
        # Enforce horizon monotonicity explicitly.
        probabilities["within_100_cycles"] = max(probabilities["within_100_cycles"], probabilities["within_50_cycles"])
        probabilities["within_200_cycles"] = max(probabilities["within_200_cycles"], probabilities["within_100_cycles"])

        return {
            "model": "monotonic_constrained_v0",
            "is_point_prediction": False,
            "is_rul": False,
            "horizons": {key: round(float(value), 3) for key, value in probabilities.items()},
            "features": {
                "drift_score": round(float(drift), 6),
                "drift_velocity": round(float(drift_velocity), 6),
                "acceleration": round(float(acceleration), 6),
                "time_in_watch_cycles": watch,
                "time_in_alert_cycles": alert,
            },
            "confidence": confidence,
            "reason_codes": reason_codes,
            "operator_message": "Probability distribution over failure horizons; not a remaining-life point estimate.",
        }

    @staticmethod
    def _clamp(value: float) -> float:
        return float(max(0.0, min(1.0, float(value))))

    @staticmethod
    def _sigmoid(value: float) -> float:
        return float(1.0 / (1.0 + np.exp(-float(value))))
