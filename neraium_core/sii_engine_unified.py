"""
System Instability Intelligence (SII) Engine: Unified Mathematical Pipeline

This engine models system behavior by tracking deformation of relational structure
over time, producing an instability score that detects regime shifts before failure occurs.

The pipeline consolidates all metrics and calculations into a single mathematical framework:
  1. Input ingestion (raw sensor vector, forward-fill missing values)
  2. Baseline modeling (μ₀, Σ₀)
  3. Rolling structure (Σ_t)
  4. Structural drift S_t = ||Σ_t - Σ₀||_F
  5. Drift velocity V_t = dS_t/dt
  6. Transition pressure P_t = function(S_t, V_t, d²S_t/dt²)
  7. Unified instability score I_t = α*S_t + β*V_t + γ*P_t
  8. Regime classification (STABLE, TRANSITION, UNSTABLE, LOCK_IN)
  9. Urgency mapping (based on regime + velocity)
  10. Comprehensive state output

All outputs derive from the unified instability score I_t.
No duplicate logic. No independent scoring systems. No UI-specific code.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


# Configuration: 5-factor core formula weights
# S(t) = w₁·D_M(t) + w₂·D_cov(t) + w₃·V_d(t) + w₄·P_t(t) + w₅·κ(t)
DEFAULT_MAHALANOBIS_WEIGHT = 0.25  # w₁: Distance from baseline state
DEFAULT_DRIFT_WEIGHT = 0.30        # w₂: Covariance breakdown
DEFAULT_VELOCITY_WEIGHT = 0.20     # w₃: Rate of destabilization
DEFAULT_PRESSURE_WEIGHT = 0.15     # w₄: Likelihood of state shift
DEFAULT_CURVATURE_WEIGHT = 0.10    # w₅: Structural bending

# Regularization and stability
COVARIANCE_REGULARIZATION = 1e-4
EPSILON = 1e-9

# Regime thresholds (for I_t classification)
STABLE_THRESHOLD = 0.30
TRANSITION_THRESHOLD = 0.65
UNSTABLE_THRESHOLD = 0.85
LOCK_IN_THRESHOLD = 0.95

# Urgency levels
URGENCY_NOMINAL = "NOMINAL"
URGENCY_WATCH = "WATCH"
URGENCY_ALERT = "ALERT"
URGENCY_CRITICAL = "CRITICAL"


@dataclass
class BaselineProfile:
    """Baseline statistics computed from initial window."""
    mean: Optional[np.ndarray] = None
    cov: Optional[np.ndarray] = None
    cov_inv: Optional[np.ndarray] = None
    sample_count: int = 0
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None

    def is_valid(self) -> bool:
        """Check if baseline has sufficient data."""
        return (
            self.mean is not None
            and self.cov is not None
            and self.cov_inv is not None
            and self.sample_count > 0
        )


@dataclass
class SystemState:
    """Current system state snapshot."""
    timestamp: float
    sensor_vector: np.ndarray
    structural_drift: float = 0.0
    drift_velocity: float = 0.0
    transition_pressure: float = 0.0
    instability_score: float = 0.0
    regime: str = "WARMUP"
    urgency: str = URGENCY_NOMINAL
    confidence: float = 0.0
    gradient_norm: float = 0.0
    recovery_alignment: float = 0.0


@dataclass
class SIIEngineOutput:
    """Unified output object with all derived metrics."""
    timestamp: float
    instability_score: float
    structural_drift: float  # D_cov(t)
    drift_velocity: float    # V_d(t)
    transition_pressure: float  # P_t(t)
    regime: str
    urgency: str
    confidence: float
    mahalanobis_distance: float = 0.0  # D_M(t): distance from baseline state
    curvature: float = 0.0  # κ(t): second derivative of drift
    gradient_norm: float = 0.0
    recovery_alignment: float = 0.0
    velocity_history: list[float] = field(default_factory=list)
    instability_history: list[float] = field(default_factory=list)
    regime_history: list[str] = field(default_factory=list)

    # Irreversibility layer: I(t) = S(t) * R(t)
    structural_inevitability_score: float = 0.0  # I(t): instability * irreversibility
    irreversibility_factor: float = 0.0  # R(t): composite irreversibility
    persistence_score: float = 0.0  # Component 1: drift persistence
    drift_acceleration_score: float = 0.0  # Component 2: acceleration of drift
    covariance_persistence_score: float = 0.0  # Component 3: covariance persistence
    failure_alignment_score: float = 0.0  # Component 4: alignment with failure modes

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "instability_score": float(self.instability_score),
            "structural_drift": float(self.structural_drift),
            "drift_velocity": float(self.drift_velocity),
            "transition_pressure": float(self.transition_pressure),
            "mahalanobis_distance": float(self.mahalanobis_distance),
            "curvature": float(self.curvature),
            "regime": self.regime,
            "urgency": self.urgency,
            "confidence": float(self.confidence),
            "gradient_norm": float(self.gradient_norm),
            "recovery_alignment": float(self.recovery_alignment),
            "velocity_history": [float(v) for v in self.velocity_history[-50:]],
            "instability_history": [float(i) for i in self.instability_history[-50:]],
            "regime_history": self.regime_history[-50:],
            # Irreversibility layer
            "structural_inevitability_score": float(self.structural_inevitability_score),
            "irreversibility_factor": float(self.irreversibility_factor),
            "persistence_score": float(self.persistence_score),
            "drift_acceleration_score": float(self.drift_acceleration_score),
            "covariance_persistence_score": float(self.covariance_persistence_score),
            "failure_alignment_score": float(self.failure_alignment_score),
        }


class SIIEngine:
    """
    System Instability Intelligence Engine.

    A unified pipeline that consolidates all structural intelligence into one
    coherent mathematical framework. The engine produces a single unified
    instability score I_t from which all other outputs are derived.
    """

    def __init__(
        self,
        baseline_window: int = 50,
        recent_window: int = 12,
        mahalanobis_weight: float = DEFAULT_MAHALANOBIS_WEIGHT,
        drift_weight: float = DEFAULT_DRIFT_WEIGHT,
        velocity_weight: float = DEFAULT_VELOCITY_WEIGHT,
        pressure_weight: float = DEFAULT_PRESSURE_WEIGHT,
        curvature_weight: float = DEFAULT_CURVATURE_WEIGHT,
    ):
        """
        Initialize the SII engine with 5-factor core formula.

        S(t) = w₁·D_M(t) + w₂·D_cov(t) + w₃·V_d(t) + w₄·P_t(t) + w₅·κ(t)

        Args:
            baseline_window: Number of samples for initial baseline period
            recent_window: Number of samples to maintain for rolling covariance
            mahalanobis_weight: w₁ - Distance from baseline state
            drift_weight: w₂ - Covariance breakdown
            velocity_weight: w₃ - Rate of destabilization
            pressure_weight: w₄ - Likelihood of state shift
            curvature_weight: w₅ - Structural bending
        """
        self.baseline_window = baseline_window
        self.recent_window = recent_window

        # Normalize weights to sum to 1
        weights_sum = (
            mahalanobis_weight + drift_weight + velocity_weight
            + pressure_weight + curvature_weight
        )
        self.mahalanobis_weight = mahalanobis_weight / weights_sum
        self.drift_weight = drift_weight / weights_sum
        self.velocity_weight = velocity_weight / weights_sum
        self.pressure_weight = pressure_weight / weights_sum
        self.curvature_weight = curvature_weight / weights_sum

        # Baseline profile (fixed after warmup)
        self.baseline = BaselineProfile()

        # Rolling history buffers
        self.sensor_history: deque[np.ndarray] = deque(maxlen=recent_window)
        self.timestamp_history: deque[float] = deque(maxlen=recent_window)

        # Scalar history for velocity and acceleration
        self.drift_history: deque[float] = deque(maxlen=recent_window)
        self.velocity_history: deque[float] = deque(maxlen=recent_window)
        self.instability_history: deque[float] = deque(maxlen=120)
        self.regime_history: deque[str] = deque(maxlen=120)

        # Previous frame state (for derivatives)
        self._prev_drift: Optional[float] = None
        self._prev_velocity: Optional[float] = None

        # Warmup tracking
        self.frame_count: int = 0
        self.baseline_ready: bool = False

        # Irreversibility tracking
        self.covariance_history: deque[np.ndarray] = deque(maxlen=recent_window)
        self._prev_acceleration: Optional[float] = None

    def fit_baseline(self, data: np.ndarray) -> None:
        """
        Compute baseline from a batch of data (baseline_window samples).

        Args:
            data: Shape (N, d) where N >= baseline_window, d = num features
        """
        if data.shape[0] < self.baseline_window:
            raise ValueError(
                f"Need at least {self.baseline_window} samples, got {data.shape[0]}"
            )

        # Take first baseline_window samples
        baseline_data = data[: self.baseline_window]

        # Forward-fill missing values within each column
        baseline_data = self._forward_fill(baseline_data)

        # Compute baseline mean and covariance
        self.baseline.mean = np.mean(baseline_data, axis=0, dtype=float)
        self.baseline.cov = np.cov(baseline_data.T, dtype=float)
        self.baseline.sample_count = self.baseline_window

        # Ensure covariance is 2D (handle single-feature case)
        if self.baseline.cov.ndim == 1:
            self.baseline.cov = np.diag(self.baseline.cov)

        # Compute regularized inverse covariance
        self.baseline.cov_inv = self._safe_inverse_covariance(self.baseline.cov)

        if self.baseline.is_valid():
            self.baseline_ready = True

    def fit_baseline_adaptive(self, data: np.ndarray, min_samples: int = 5) -> bool:
        """
        Compute baseline from available data, using as much as possible.

        Does not raise on insufficient data; returns success/failure instead.

        Args:
            data: Shape (N, d) where N >= min_samples, d = num features
            min_samples: Minimum samples required (default 5)

        Returns:
            True if baseline was successfully created, False otherwise
        """
        if data.shape[0] < min_samples:
            return False

        # Use available data, up to baseline_window
        actual_baseline_size = min(data.shape[0], self.baseline_window)
        baseline_data = data[:actual_baseline_size]

        # Forward-fill missing values
        baseline_data = self._forward_fill(baseline_data)

        # Compute baseline mean and covariance
        self.baseline.mean = np.mean(baseline_data, axis=0, dtype=float)
        self.baseline.cov = np.cov(baseline_data.T, dtype=float)
        self.baseline.sample_count = actual_baseline_size

        # Ensure covariance is 2D
        if self.baseline.cov.ndim == 1:
            self.baseline.cov = np.diag(self.baseline.cov)

        # Compute regularized inverse covariance
        self.baseline.cov_inv = self._safe_inverse_covariance(self.baseline.cov)

        if self.baseline.is_valid():
            self.baseline_ready = True
            return True

        return False

    def finalize_baseline(self) -> bool:
        """
        Finalize baseline from accumulated history (for end-of-stream).

        Returns:
            True if baseline was successfully created, False otherwise
        """
        if self.baseline_ready:
            return True

        if len(self.sensor_history) > 0:
            baseline_matrix = np.array(list(self.sensor_history), dtype=float)
            return self.fit_baseline_adaptive(baseline_matrix, min_samples=5)

        return False

    def update(
        self,
        x_t: np.ndarray,
        timestamp: float,
    ) -> SIIEngineOutput:
        """
        Process one frame and compute unified instability score.

        Args:
            x_t: Sensor vector (d,)
            timestamp: Timestamp for this frame

        Returns:
            SIIEngineOutput with all computed metrics
        """
        self.frame_count += 1
        x_t = np.asarray(x_t, dtype=float)

        # Forward-fill missing values in this frame
        x_t = self._forward_fill_frame(x_t)

        # During warmup, accumulate history
        if not self.baseline_ready and self.frame_count <= self.baseline_window:
            self.sensor_history.append(x_t)
            self.timestamp_history.append(timestamp)

            # Fit baseline when warmup window is full
            if self.frame_count == self.baseline_window:
                baseline_matrix = np.array(list(self.sensor_history), dtype=float)
                try:
                    # Try strict baseline first
                    self.fit_baseline(baseline_matrix)
                except ValueError:
                    # Fall back to adaptive if not enough samples
                    self.fit_baseline_adaptive(baseline_matrix, min_samples=5)

            return self._warmup_output(timestamp)

        # After baseline is ready, update rolling history
        self.sensor_history.append(x_t)
        self.timestamp_history.append(timestamp)

        # ======================================================================
        # PIPELINE STAGE 1: Compute rolling covariance (Σ_t)
        # ======================================================================
        cov_t = self.compute_covariance(
            np.array(list(self.sensor_history), dtype=float)
        )

        # ======================================================================
        # PIPELINE STAGE 2: Structural drift S_t = ||Σ_t - Σ₀||_F
        # ======================================================================
        S_t = self.compute_structural_drift(cov_t)
        self.drift_history.append(S_t)

        # ======================================================================
        # PIPELINE STAGE 3: Drift velocity V_t = dS_t/dt
        # ======================================================================
        V_t = self.compute_velocity(S_t, timestamp)

        # ======================================================================
        # PIPELINE STAGE 3.5: Mahalanobis distance D_M(t)
        # ======================================================================
        D_M = self.compute_mahalanobis_distance(x_t)

        # ======================================================================
        # PIPELINE STAGE 4: Transition pressure P_t
        # ======================================================================
        P_t = self.compute_transition_pressure(S_t, V_t)

        # ======================================================================
        # PIPELINE STAGE 4.5: Curvature κ(t) = dV_t/dt
        # ======================================================================
        kappa = self.compute_curvature(V_t, timestamp)

        # ======================================================================
        # PIPELINE STAGE 5: 5-factor instability score S(t)
        # ======================================================================
        I_t = self.compute_instability_score(D_M, S_t, V_t, P_t, kappa)
        self.instability_history.append(I_t)

        # Store covariance for irreversibility
        self.covariance_history.append(cov_t)

        # ======================================================================
        # PIPELINE STAGE 5.5: Irreversibility layer R(t)
        # ======================================================================
        persistence_score = self._compute_persistence_score(S_t)
        drift_acceleration_score = self._compute_drift_acceleration_score(V_t)
        covariance_persistence_score = self._compute_covariance_persistence_score()
        failure_alignment_score = self._compute_failure_alignment_score(P_t, V_t)

        irreversibility_factor = self._compute_irreversibility_factor(
            persistence_score,
            drift_acceleration_score,
            covariance_persistence_score,
            failure_alignment_score
        )

        # Inevitability score: S(t) * R(t)
        inevitability_score = I_t * irreversibility_factor

        # ======================================================================
        # PIPELINE STAGE 6: Regime classification
        # ======================================================================
        regime = self.classify_regime(I_t)
        self.regime_history.append(regime)

        # ======================================================================
        # PIPELINE STAGE 7: Urgency mapping
        # ======================================================================
        urgency = self.compute_urgency(regime, V_t)

        # ======================================================================
        # PIPELINE STAGE 8: Compute confidence and auxiliary metrics
        # ======================================================================
        confidence = self._compute_confidence(I_t)
        gradient_norm = self._compute_gradient_norm(x_t)
        recovery_alignment = self._compute_recovery_alignment(x_t)

        # ======================================================================
        # PIPELINE STAGE 9: Assemble output
        # ======================================================================
        output = SIIEngineOutput(
            timestamp=timestamp,
            instability_score=I_t,
            structural_drift=S_t,
            drift_velocity=V_t,
            transition_pressure=P_t,
            mahalanobis_distance=D_M,
            curvature=kappa,
            regime=regime,
            urgency=urgency,
            confidence=confidence,
            gradient_norm=gradient_norm,
            recovery_alignment=recovery_alignment,
            velocity_history=list(self.velocity_history),
            instability_history=list(self.instability_history),
            regime_history=list(self.regime_history),
            # Irreversibility layer
            structural_inevitability_score=inevitability_score,
            irreversibility_factor=irreversibility_factor,
            persistence_score=persistence_score,
            drift_acceleration_score=drift_acceleration_score,
            covariance_persistence_score=covariance_persistence_score,
            failure_alignment_score=failure_alignment_score,
        )

        return output

    def compute_covariance(self, data: np.ndarray) -> np.ndarray:
        """
        Compute covariance matrix from data.

        Args:
            data: Shape (N, d) where N = samples, d = features

        Returns:
            Covariance matrix (d, d)
        """
        if data.shape[0] < 2:
            # Return identity scaled by variance of baseline
            if self.baseline.cov is not None:
                return self.baseline.cov.copy()
            return np.eye(data.shape[1])

        data = self._forward_fill(data)
        cov = np.cov(data.T, dtype=float)

        # Ensure 2D
        if cov.ndim == 1:
            cov = np.diag(cov)

        return cov

    def compute_structural_drift(self, cov_t: np.ndarray) -> float:
        """
        Compute structural drift as Frobenius norm of covariance change.

        S_t = ||Σ_t - Σ₀||_F / (||Σ₀||_F + ε)

        Measures how much the correlation structure has deformed from baseline.

        Args:
            cov_t: Rolling covariance matrix

        Returns:
            Normalized drift score in [0, 1]
        """
        if not self.baseline.is_valid():
            return 0.0

        cov_0 = self.baseline.cov
        diff = cov_t - cov_0

        # Frobenius norm: sqrt(sum of squared elements)
        frob_diff = float(np.linalg.norm(diff, "fro"))
        frob_baseline = float(np.linalg.norm(cov_0, "fro"))

        # Normalize by baseline norm
        drift = frob_diff / (frob_baseline + EPSILON)
        return float(np.clip(drift, 0.0, 1.0))

    def compute_velocity(self, S_t: float, timestamp: float) -> float:
        """
        Compute drift velocity: rate of change of structural drift.

        V_t = dS_t/dt (approximated as finite difference)

        Measures how fast the system is deforming. High velocity suggests
        rapid regime transition or shock.

        Args:
            S_t: Current structural drift
            timestamp: Current timestamp

        Returns:
            Drift velocity (unbounded, typically < 1)
        """
        if self._prev_drift is None:
            self._prev_drift = S_t
            V_t = 0.0
        else:
            # Compute time delta (avoid division by zero)
            if len(self.timestamp_history) >= 2:
                dt = self.timestamp_history[-1] - self.timestamp_history[-2]
                dt = max(dt, EPSILON)
            else:
                dt = 1.0

            # Finite difference: (S_t - S_{t-1}) / dt
            V_t = (S_t - self._prev_drift) / dt

        self._prev_drift = S_t
        self.velocity_history.append(V_t)
        return float(V_t)

    def compute_transition_pressure(self, S_t: float, V_t: float) -> float:
        """
        Compute transition pressure: combined effect of drift magnitude and velocity.

        P_t = (1 - exp(-S_t)) * |V_t|

        High pressure indicates the system is actively deforming. Combines:
        - Nonlinear drift magnitude: exp(-S_t) creates urgency as drift increases
        - Velocity: multiplies by absolute velocity to weight rapid changes

        Args:
            S_t: Structural drift
            V_t: Drift velocity

        Returns:
            Transition pressure (in [0, 1])
        """
        # Nonlinear term: increases with drift, saturates at 1
        drift_component = 1.0 - np.exp(-S_t)

        # Velocity component: how fast is it changing
        # Use tanh to bound to [-1, 1], then take absolute value
        velocity_component = float(np.tanh(V_t))

        # Combine: pressure is the product
        P_t = drift_component * abs(velocity_component)
        return float(np.clip(P_t, 0.0, 1.0))

    def compute_mahalanobis_distance(self, x_t: np.ndarray) -> float:
        """
        Compute Mahalanobis distance from baseline.

        D_M(t) = sqrt((x_t - μ₀)ᵀ Σ₀⁻¹ (x_t - μ₀))

        Measures how far current observation is from baseline state.

        Args:
            x_t: Current sensor vector

        Returns:
            Mahalanobis distance [0, ∞), clipped to [0, 1]
        """
        if not self.baseline.is_valid():
            return 0.0

        delta = x_t - self.baseline.mean
        try:
            mahal_sq = float(np.dot(delta, np.dot(self.baseline.cov_inv, delta)))
            mahal = float(np.sqrt(np.clip(mahal_sq, 0.0, 1e10)))
            return float(np.clip(mahal / 10.0, 0.0, 1.0))
        except:
            return 0.0

    def compute_curvature(self, V_t: float, timestamp: float) -> float:
        """
        Compute curvature: second derivative of drift.

        κ(t) = dV_t/dt = d²S_t/dt²

        Measures how the rate of drift is changing (structural bending).

        Args:
            V_t: Current drift velocity
            timestamp: Current timestamp

        Returns:
            Curvature [0, 1]
        """
        if self._prev_velocity is None:
            self._prev_velocity = V_t
            return 0.0
        else:
            if len(self.timestamp_history) >= 2:
                dt = self.timestamp_history[-1] - self.timestamp_history[-2]
                dt = max(dt, EPSILON)
            else:
                dt = 1.0

            kappa = (V_t - self._prev_velocity) / dt
            self._prev_velocity = V_t
            return float(np.clip(abs(kappa), 0.0, 1.0))

    def compute_instability_score(
        self,
        D_M: float,
        D_cov: float,
        V_d: float,
        P_t: float,
        kappa: float,
    ) -> float:
        """
        Compute 5-factor core instability score.

        S(t) = w₁·D_M(t) + w₂·D_cov(t) + w₃·V_d(t) + w₄·P_t(t) + w₅·κ(t)

        where:
        - D_M(t) = Mahalanobis distance (distance from baseline state)
        - D_cov(t) = Covariance drift (structural breakdown)
        - V_d(t) = Drift velocity (rate of destabilization)
        - P_t(t) = Transition pressure (likelihood of state shift)
        - κ(t) = Curvature (structural bending)

        Args:
            D_M: Mahalanobis distance [0, 1]
            D_cov: Covariance drift [0, 1]
            V_d: Drift velocity (bounded contribution)
            P_t: Transition pressure [0, 1]
            kappa: Curvature [0, 1]

        Returns:
            Instability score [0, 1]
        """
        # Bound velocity to [-1, 1] for contribution
        V_d_bounded = float(np.tanh(V_d))

        # 5-factor weighted combination
        S_t = (
            self.mahalanobis_weight * D_M
            + self.drift_weight * D_cov
            + self.velocity_weight * abs(V_d_bounded)
            + self.pressure_weight * P_t
            + self.curvature_weight * kappa
        )

        return float(np.clip(S_t, 0.0, 1.0))

    def classify_regime(self, I_t: float) -> str:
        """
        Classify system regime based on instability score.

        STABLE:      I_t <= 0.30  (normal operation)
        TRANSITION:  0.30 < I_t <= 0.65  (system changing)
        UNSTABLE:    0.65 < I_t <= 0.85  (high risk)
        LOCK_IN:     I_t > 0.85  (critical state or failure imminent)

        Args:
            I_t: Instability score

        Returns:
            Regime label
        """
        if I_t <= STABLE_THRESHOLD:
            return "STABLE"
        elif I_t <= TRANSITION_THRESHOLD:
            return "TRANSITION"
        elif I_t <= UNSTABLE_THRESHOLD:
            return "UNSTABLE"
        else:
            return "LOCK_IN"

    def compute_urgency(self, regime: str, velocity: float) -> str:
        """
        Map regime and velocity to urgency level.

        NOMINAL:   STABLE + low velocity
        WATCH:     TRANSITION or elevated velocity
        ALERT:     UNSTABLE
        CRITICAL:  LOCK_IN

        Args:
            regime: Regime classification
            velocity: Drift velocity

        Returns:
            Urgency level
        """
        if regime == "LOCK_IN":
            return URGENCY_CRITICAL
        elif regime == "UNSTABLE":
            return URGENCY_ALERT
        elif regime == "TRANSITION":
            # Elevated velocity in transition pushes toward ALERT
            if abs(velocity) > 0.1:
                return URGENCY_ALERT
            return URGENCY_WATCH
        else:  # STABLE
            # Even in stable, high velocity warrants WATCH
            if abs(velocity) > 0.05:
                return URGENCY_WATCH
            return URGENCY_NOMINAL

    def get_state(self) -> dict[str, Any]:
        """
        Get serializable state snapshot for persistence/restoration.

        Returns:
            Dictionary with all internal state
        """
        return {
            "baseline": {
                "mean": self.baseline.mean.tolist() if self.baseline.mean is not None else None,
                "cov": self.baseline.cov.tolist() if self.baseline.cov is not None else None,
                "sample_count": self.baseline.sample_count,
            },
            "drift_history": list(self.drift_history),
            "velocity_history": list(self.velocity_history),
            "instability_history": list(self.instability_history),
            "regime_history": list(self.regime_history),
            "frame_count": self.frame_count,
            "baseline_ready": self.baseline_ready,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """
        Restore engine from state snapshot.

        Args:
            state: Dictionary from get_state()
        """
        baseline_data = state.get("baseline", {})
        if baseline_data.get("mean"):
            self.baseline.mean = np.array(baseline_data["mean"], dtype=float)
        if baseline_data.get("cov"):
            self.baseline.cov = np.array(baseline_data["cov"], dtype=float)
            self.baseline.cov_inv = self._safe_inverse_covariance(self.baseline.cov)
        self.baseline.sample_count = int(baseline_data.get("sample_count", 0))

        self.drift_history = deque(
            state.get("drift_history", []), maxlen=self.recent_window
        )
        self.velocity_history = deque(
            state.get("velocity_history", []), maxlen=self.recent_window
        )
        self.instability_history = deque(
            state.get("instability_history", []), maxlen=120
        )
        self.regime_history = deque(
            state.get("regime_history", []), maxlen=120
        )
        self.frame_count = int(state.get("frame_count", 0))
        self.baseline_ready = bool(state.get("baseline_ready", False))

    # ========================================================================
    # AUXILIARY COMPUTATIONS (derived metrics, not core pipeline)
    # ========================================================================

    def _compute_confidence(self, I_t: float) -> float:
        """
        Confidence in instability score based on baseline quality and history.

        Returns:
            Confidence in [0, 1]
        """
        if not self.baseline_ready:
            return 0.0

        # Confidence increases with history
        history_factor = min(self.frame_count / (2 * self.baseline_window), 1.0)

        # Confidence decreases if recent volatility is very high
        if len(self.velocity_history) >= 5:
            recent_volatility = np.std(list(self.velocity_history)[-5:])
            volatility_penalty = np.clip(recent_volatility, 0.0, 0.3)
        else:
            volatility_penalty = 0.0

        confidence = history_factor * (1.0 - volatility_penalty)
        return float(np.clip(confidence, 0.0, 1.0))

    def _compute_gradient_norm(self, x_t: np.ndarray) -> float:
        """
        Compute gradient norm (instability direction in sensor space).

        Gradient points in direction of increasing energy (instability).

        Args:
            x_t: Current sensor vector

        Returns:
            Norm of energy gradient
        """
        if not self.baseline.is_valid():
            return 0.0

        # Gradient = 2 * Σ_inv * (x - μ)
        delta = x_t - self.baseline.mean
        grad = 2.0 * (self.baseline.cov_inv @ delta)
        return float(np.linalg.norm(grad))

    def _compute_recovery_alignment(self, x_t: np.ndarray) -> float:
        """
        Compute alignment between velocity and recovery direction.

        Recovery force = -gradient (points toward baseline).
        High alignment means system is moving toward stability.

        Args:
            x_t: Current sensor vector

        Returns:
            Recovery alignment in [-1, 1]
        """
        if len(self.sensor_history) < 2 or not self.baseline.is_valid():
            return 0.0

        # Velocity in sensor space
        x_prev = self.sensor_history[-2]
        velocity = x_t - x_prev

        # Recovery force = -gradient
        delta = x_t - self.baseline.mean
        gradient = 2.0 * (self.baseline.cov_inv @ delta)
        recovery_force = -gradient

        # Cosine similarity
        v_norm = np.linalg.norm(velocity) + EPSILON
        r_norm = np.linalg.norm(recovery_force) + EPSILON
        alignment = float((velocity @ recovery_force) / (v_norm * r_norm))

        return float(np.clip(alignment, -1.0, 1.0))

    def _warmup_output(self, timestamp: float) -> SIIEngineOutput:
        """Return safe defaults during warmup phase."""
        return SIIEngineOutput(
            timestamp=timestamp,
            instability_score=0.0,
            structural_drift=0.0,
            drift_velocity=0.0,
            transition_pressure=0.0,
            regime="WARMUP",
            urgency=URGENCY_NOMINAL,
            confidence=0.0,
        )

    # ========================================================================
    # UTILITY FUNCTIONS
    # ========================================================================

    @staticmethod
    def _safe_inverse_covariance(cov: np.ndarray) -> np.ndarray:
        """
        Compute regularized inverse covariance via pseudo-inverse.

        Args:
            cov: Covariance matrix (d, d)

        Returns:
            Regularized inverse (d, d), or regularized cov if singular
        """
        try:
            dim = cov.shape[0]
            cov_reg = cov + COVARIANCE_REGULARIZATION * np.eye(dim)
            cov_inv = np.linalg.pinv(cov_reg)
            return cov_inv
        except (ValueError, np.linalg.LinAlgError):
            dim = cov.shape[0]
            return (1.0 / (COVARIANCE_REGULARIZATION + 1e-10)) * np.eye(dim)

    def _compute_persistence_score(self, S_t: float) -> float:
        """
        Compute persistence score: how long drift has been sustained.

        Based on the amount of time the drift has been above a threshold.
        Higher score indicates longer sustained instability.

        Args:
            S_t: Current structural drift

        Returns:
            Persistence score [0, 1]
        """
        if len(self.drift_history) < 2:
            return 0.0

        # Count how many recent frames have high drift (> 0.3)
        high_drift_count = sum(1 for d in self.drift_history if d > 0.3)
        persistence = high_drift_count / max(len(self.drift_history), 1)

        return float(np.clip(persistence, 0.0, 1.0))

    def _compute_drift_acceleration_score(self, V_t: float) -> float:
        """
        Compute drift acceleration score: magnitude of velocity change.

        Based on how quickly the drift velocity is changing. Indicates if
        the system is accelerating toward failure.

        Args:
            V_t: Current drift velocity

        Returns:
            Acceleration score [0, 1]
        """
        if self._prev_acceleration is None:
            self._prev_acceleration = 0.0
            return 0.0

        # Compute acceleration as change in velocity
        acceleration = abs(V_t - self._prev_acceleration)
        self._prev_acceleration = V_t

        # Bound and normalize
        accel_score = float(np.tanh(acceleration))
        return float(np.clip(accel_score, 0.0, 1.0))

    def _compute_covariance_persistence_score(self) -> float:
        """
        Compute covariance persistence score: consistency of covariance deviation.

        Based on how stable (or consistently changing) the covariance structure is.
        Higher score indicates more consistent deviation from baseline.

        Returns:
            Covariance persistence score [0, 1]
        """
        if len(self.covariance_history) < 2 or not self.baseline.is_valid():
            return 0.0

        # Compute distances from baseline for recent covariances
        cov_dists = []
        for cov in self.covariance_history:
            diff = cov - self.baseline.cov
            dist = float(np.linalg.norm(diff, "fro"))
            cov_dists.append(dist)

        if len(cov_dists) < 2:
            return 0.0

        # Persistence = inverse of variability (low variation = high persistence)
        mean_dist = np.mean(cov_dists)
        std_dist = np.std(cov_dists)

        if mean_dist < EPSILON:
            return 0.0

        # Consistency metric (inverse coefficient of variation)
        consistency = 1.0 / (1.0 + (std_dist / mean_dist))
        return float(np.clip(consistency, 0.0, 1.0))

    def _compute_failure_alignment_score(self, P_t: float, V_t: float) -> float:
        """
        Compute failure alignment score: how aligned state is with failure trajectory.

        Combines transition pressure and velocity as indicators that the system
        is following a path toward failure.

        Args:
            P_t: Transition pressure
            V_t: Drift velocity

        Returns:
            Failure alignment score [0, 1]
        """
        # Failure alignment = combination of pressure and sustained velocity
        V_bounded = float(np.tanh(V_t))

        # High pressure + positive velocity = strong failure alignment
        alignment = 0.6 * P_t + 0.4 * max(V_bounded, 0.0)

        return float(np.clip(alignment, 0.0, 1.0))

    def _compute_irreversibility_factor(
        self,
        persistence: float,
        acceleration: float,
        cov_persistence: float,
        failure_alignment: float,
    ) -> float:
        """
        Compute irreversibility factor R(t) from four components.

        R(t) = weighted combination of:
        - Persistence: how long drift has been sustained
        - Acceleration: how fast the change is happening
        - Covariance persistence: consistency of structural change
        - Failure alignment: how aligned with failure trajectory

        Higher R(t) means the instability is more irreversible (harder to recover from).

        Args:
            persistence: Drift persistence [0, 1]
            acceleration: Drift acceleration [0, 1]
            cov_persistence: Covariance persistence [0, 1]
            failure_alignment: Failure alignment [0, 1]

        Returns:
            Irreversibility factor [0, 1]
        """
        # Equal weighting of components
        R_t = 0.25 * (persistence + acceleration + cov_persistence + failure_alignment)

        # Amplify high irreversibility to emphasize persistent instability
        R_t = R_t ** 0.8  # Soften the amplification

        return float(np.clip(R_t, 0.0, 1.0))

    @staticmethod
    def _forward_fill(data: np.ndarray) -> np.ndarray:
        """
        Forward-fill NaN values column-wise.

        Args:
            data: Array with potential NaN values

        Returns:
            Array with NaNs replaced
        """
        data = data.copy()
        for col in range(data.shape[1]):
            col_data = data[:, col]
            mask = np.isnan(col_data)
            if np.any(mask):
                # Find first non-NaN
                non_nan_idx = np.where(~mask)[0]
                if len(non_nan_idx) == 0:
                    # All NaN: fill with 0
                    col_data[mask] = 0.0
                else:
                    # Forward fill
                    first_valid = non_nan_idx[0]
                    col_data[:first_valid] = col_data[first_valid]
                    for i in range(first_valid + 1, len(col_data)):
                        if np.isnan(col_data[i]):
                            col_data[i] = col_data[i - 1]
        return data

    @staticmethod
    def _forward_fill_frame(x_t: np.ndarray) -> np.ndarray:
        """
        Forward-fill NaN values in a single frame (1D array).

        Args:
            x_t: Sensor vector

        Returns:
            Vector with NaNs filled
        """
        x_t = x_t.copy()
        mask = np.isnan(x_t)
        if np.any(mask):
            # Find first non-NaN
            non_nan_idx = np.where(~mask)[0]
            if len(non_nan_idx) == 0:
                # All NaN: fill with 0
                x_t[mask] = 0.0
            else:
                # Forward fill
                first_valid = non_nan_idx[0]
                x_t[:first_valid] = x_t[first_valid]
                for i in range(first_valid + 1, len(x_t)):
                    if np.isnan(x_t[i]):
                        x_t[i] = x_t[i - 1]
        return x_t


__all__ = [
    "SIIEngine",
    "SIIEngineOutput",
    "SystemState",
    "BaselineProfile",
    "DEFAULT_DRIFT_WEIGHT",
    "DEFAULT_VELOCITY_WEIGHT",
    "DEFAULT_PRESSURE_WEIGHT",
]
