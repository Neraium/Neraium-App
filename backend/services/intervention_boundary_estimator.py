"""Forward-only intervention boundary estimation.

This is not RUL or failure prediction. It estimates when continued inaction may
become operationally risky or economically inefficient, using only current and
past structural signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


BOUNDARY_STATES = ("CLEAR", "APPROACHING", "ACTIONABLE", "CRITICAL")


@dataclass
class InterventionBoundaryEstimator:
    window: int = 12
    drift_history: List[float] = field(default_factory=list)
    stability_history: List[float] = field(default_factory=list)
    covariance_history: List[float] = field(default_factory=list)
    degradation_history: List[float] = field(default_factory=list)
    recovery_history: List[float] = field(default_factory=list)
    lock_in_history: List[float] = field(default_factory=list)
    state_history: List[str] = field(default_factory=list)
    cycle_history: List[int] = field(default_factory=list)

    def update(
        self,
        *,
        cycle: int,
        structural_drift_score: float,
        relational_stability_score: float,
        covariance_shift: float,
        drift_velocity: Optional[float] = None,
        drift_acceleration: Optional[float] = None,
        trajectory_classification: Optional[str] = None,
        recovery_probability: float = 0.0,
        degradation_probability: float = 0.0,
        lock_in_probability: float = 0.0,
        current_state: Optional[str] = None,
        baseline_ready: bool = True,
    ) -> Dict[str, Any]:
        drift = self._clamp(structural_drift_score)
        stability = self._clamp(relational_stability_score)
        covariance = self._clamp(covariance_shift)
        recovery = self._clamp(recovery_probability)
        degradation = self._clamp(degradation_probability)
        lock_in = self._clamp(lock_in_probability)

        previous_drift = self.drift_history[-1] if self.drift_history else drift
        previous_velocity = self._recent_velocity() if self.drift_history else 0.0
        velocity = float(drift_velocity) if drift_velocity is not None else drift - previous_drift
        acceleration = float(drift_acceleration) if drift_acceleration is not None else velocity - previous_velocity

        self.drift_history.append(drift)
        self.stability_history.append(stability)
        self.covariance_history.append(covariance)
        self.recovery_history.append(recovery)
        self.degradation_history.append(degradation)
        self.lock_in_history.append(lock_in)
        self.state_history.append(str(current_state or "UNKNOWN"))
        self.cycle_history.append(int(cycle))

        if not baseline_ready or len(self.drift_history) < max(4, min(self.window, 6)):
            return self._frame(
                pressure=0.0,
                boundary_state="CLEAR",
                time_to_boundary=None,
                confidence="LOW",
                band=None,
                reason_codes=["BASELINE_FORMING"],
                operator_message="Intervention boundary not estimated while baseline is forming.",
                if_ignored="No intervention boundary indicated yet.",
            )

        recent_drift = np.asarray(self.drift_history[-self.window :], dtype=float)
        recent_stability = np.asarray(self.stability_history[-self.window :], dtype=float)
        recent_covariance = np.asarray(self.covariance_history[-self.window :], dtype=float)
        recent_degradation = np.asarray(self.degradation_history[-self.window :], dtype=float)
        recent_recovery = np.asarray(self.recovery_history[-self.window :], dtype=float)
        recent_lock_in = np.asarray(self.lock_in_history[-self.window :], dtype=float)

        drift_persistence = float(np.mean(recent_drift >= 0.32))
        covariance_persistence = float(np.mean(recent_covariance >= 0.32))
        stability_decline = max(0.0, float(recent_stability[0] - recent_stability[-1])) if len(recent_stability) > 1 else 0.0
        degradation_rise = max(0.0, float(recent_degradation[-1] - recent_degradation[0])) if len(recent_degradation) > 1 else 0.0
        recovery_fall = max(0.0, float(recent_recovery[0] - recent_recovery[-1])) if len(recent_recovery) > 1 else 0.0
        lock_in_rise = max(0.0, float(recent_lock_in[-1] - recent_lock_in[0])) if len(recent_lock_in) > 1 else 0.0

        reason_codes: List[str] = []
        if drift_persistence >= 0.5:
            reason_codes.append("PERSISTENT_DRIFT")
        if velocity > 0.01:
            reason_codes.append("RISING_DRIFT_VELOCITY")
        if acceleration > 0.002:
            reason_codes.append("POSITIVE_ACCELERATION")
        if stability_decline > 0.08 or stability < 0.55:
            reason_codes.append("DECLINING_RELATIONAL_STABILITY")
        if covariance_persistence >= 0.5:
            reason_codes.append("PERSISTENT_COVARIANCE_SHIFT")
        if degradation_rise > 0.05 or degradation >= 0.60:
            reason_codes.append("DEGRADATION_PROBABILITY_RISING")
        if recovery_fall > 0.05 or recovery <= 0.25:
            reason_codes.append("RECOVERY_PROBABILITY_FALLING")
        if lock_in_rise > 0.05 or lock_in >= 0.35 or trajectory_classification == "LOCK_IN":
            reason_codes.append("LOCK_IN_PROBABILITY_RISING")

        pressure = (
            0.22 * drift
            + 0.16 * covariance
            + 0.14 * (1.0 - stability)
            + 0.12 * drift_persistence
            + 0.08 * covariance_persistence
            + 0.08 * max(0.0, min(1.0, velocity * 8.0))
            + 0.08 * max(0.0, min(1.0, acceleration * 20.0))
            + 0.08 * degradation
            + 0.04 * lock_in
        )
        pressure = self._clamp(pressure)
        boundary_state = self._boundary_state(pressure, current_state, trajectory_classification)
        confidence = self._confidence(reason_codes, drift_persistence, covariance_persistence, current_state)
        time_to_boundary, band = self._time_estimate(
            pressure=pressure,
            velocity=velocity,
            acceleration=acceleration,
            confidence=confidence,
            boundary_state=boundary_state,
        )

        return self._frame(
            pressure=pressure,
            boundary_state=boundary_state,
            time_to_boundary=time_to_boundary,
            confidence=confidence,
            band=band,
            reason_codes=reason_codes or ["BASELINE_HOLDING"],
            operator_message=self._operator_message(boundary_state),
            if_ignored=self._if_ignored(boundary_state),
        )

    def _recent_velocity(self) -> float:
        if len(self.drift_history) < 2:
            return 0.0
        return float(self.drift_history[-1] - self.drift_history[-2])

    @staticmethod
    def _clamp(value: float) -> float:
        return float(max(0.0, min(1.0, float(value))))

    @staticmethod
    def _boundary_state(pressure: float, current_state: Optional[str], trajectory: Optional[str]) -> str:
        if current_state == "LOCK_IN" or trajectory == "LOCK_IN" or pressure >= 0.78:
            return "CRITICAL"
        if current_state == "ACTIONABLE" or pressure >= 0.58:
            if current_state in {"DETECTED", "CONFIRMING"}:
                return "APPROACHING"
            return "ACTIONABLE"
        if current_state in {"DETECTED", "CONFIRMING"} or pressure >= 0.34:
            return "APPROACHING"
        return "CLEAR"

    @staticmethod
    def _confidence(reason_codes: List[str], drift_persistence: float, covariance_persistence: float, current_state: Optional[str]) -> str:
        if current_state == "LOCK_IN":
            return "HIGH"
        if current_state == "ACTIONABLE":
            return "HIGH" if len(reason_codes) >= 4 else "MEDIUM"
        if current_state in {"DETECTED", "CONFIRMING"}:
            return "MEDIUM"
        if drift_persistence >= 0.5 and covariance_persistence >= 0.5 and len(reason_codes) >= 3:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _time_estimate(
        *,
        pressure: float,
        velocity: float,
        acceleration: float,
        confidence: str,
        boundary_state: str,
    ) -> tuple[Optional[int], Optional[List[int]]]:
        if confidence == "LOW" or boundary_state == "CLEAR":
            return None, None
        if boundary_state in {"ACTIONABLE", "CRITICAL"}:
            return 0, [0, 0]
        effective_rate = max(velocity + max(acceleration, 0.0), 0.005)
        cycles = int(np.ceil(max(0.0, 0.58 - pressure) / effective_rate))
        cycles = max(cycles, 1)
        spread = max(3, int(np.ceil(cycles * 0.45)))
        return cycles, [max(0, cycles - spread), cycles + spread]

    @staticmethod
    def _operator_message(boundary_state: str) -> str:
        if boundary_state == "CLEAR":
            return "No intervention boundary indicated. Continue monitoring."
        if boundary_state == "APPROACHING":
            return "Intervention boundary approaching. Prepare operational review."
        if boundary_state == "ACTIONABLE":
            return "Intervention boundary reached. Plan inspection or mitigation."
        return "Intervention boundary critical. Escalate operational response."

    @staticmethod
    def _if_ignored(boundary_state: str) -> str:
        if boundary_state == "CLEAR":
            return "Continued monitoring remains appropriate."
        if boundary_state == "APPROACHING":
            return "Delay may reduce maintenance flexibility."
        if boundary_state == "ACTIONABLE":
            return "Inaction may become operationally risky or inefficient."
        return "Inaction may create avoidable operational exposure."

    @staticmethod
    def _frame(
        *,
        pressure: float,
        boundary_state: str,
        time_to_boundary: Optional[int],
        confidence: str,
        band: Optional[List[int]],
        reason_codes: List[str],
        operator_message: str,
        if_ignored: str,
    ) -> Dict[str, Any]:
        return {
            "intervention_pressure_score": round(float(pressure), 6),
            "intervention_boundary_state": boundary_state,
            "time_to_intervention_boundary_cycles": time_to_boundary,
            "confidence": confidence,
            "confidence_band_cycles": band,
            "reason_codes": reason_codes,
            "operator_message": operator_message,
            "if_ignored": if_ignored,
        }
