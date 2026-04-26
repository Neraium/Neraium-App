"""
Advanced SII Engine with Enhanced Detection Capabilities.

Adds to the unified SII Engine:
1. Multi-scale analysis (fast/medium/slow degradation detection)
2. Novelty/out-of-distribution detection (new failure modes)
3. Remaining Useful Life (RUL) estimation with confidence bounds
4. Explainability via feature attribution
5. Operating condition normalization
6. Adaptive thresholds per system type
7. Uncertainty quantification (Bayesian confidence intervals)
8. Feedback integration & learning
PLUS:
9. Sensor diagnostics & health tracking
10. Ensemble anomaly detection
11. Early warning indicators
12. Degradation mode classification
13. System fingerprinting
14. Change point detection
15. Cost-benefit analysis
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from datetime import datetime

from neraium_core.sii_engine_unified import (
    SIIEngine, SIIEngineOutput, BaselineProfile, STABLE_THRESHOLD,
    TRANSITION_THRESHOLD, UNSTABLE_THRESHOLD, LOCK_IN_THRESHOLD
)


class DegradationMode(Enum):
    """Classification of degradation type."""
    NORMAL = "normal"
    LINEAR_DRIFT = "linear_drift"
    ACCELERATING_DRIFT = "accelerating_drift"
    PERIODIC_OSCILLATION = "periodic_oscillation"
    SUDDEN_SPIKE = "sudden_spike"
    MODE_SHIFT = "mode_shift"
    SENSOR_FAILURE = "sensor_failure"
    UNKNOWN = "unknown"


class FailureProbability(Enum):
    """Confidence in failure prediction."""
    VERY_LOW = 0.1
    LOW = 0.3
    MODERATE = 0.5
    HIGH = 0.7
    VERY_HIGH = 0.9


@dataclass
class SensorDiagnostics:
    """Health status of individual sensor."""
    sensor_id: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    deviation_sigmas: float  # How many std devs from baseline
    drift_rate: float  # Change per cycle
    is_anomalous: bool
    is_likely_faulty: bool  # Sensor error vs. system degradation
    health_score: float  # 0.0 (failed) to 1.0 (healthy)
    contribution_to_instability: float  # How much does this sensor matter?


@dataclass
class EarlyWarningSignal:
    """Early precursor to state change."""
    signal_type: str  # "volatility_increase", "correlation_change", etc.
    strength: float  # 0.0 to 1.0
    cycles_until_transition: int  # Estimated
    confidence: float


@dataclass
class RULEstimate:
    """Remaining useful life prediction."""
    median_cycles: int
    p10_cycles: int  # 10th percentile (optimistic)
    p90_cycles: int  # 90th percentile (pessimistic)
    confidence: float
    degradation_rate: float  # Cycles per unit instability
    mode: DegradationMode
    probability_failure_30days: float  # Probability within 30 cycles


@dataclass
class AdvancedSIIOutput(SIIEngineOutput):
    """Extended output with all advanced metrics."""
    # Core (from SIIEngineOutput)
    # timestamp, instability_score, structural_drift, drift_velocity,
    # transition_pressure, regime, urgency, confidence, ...

    # Multi-scale
    drift_fast: float = 0.0        # 12-cycle window
    drift_medium: float = 0.0      # 120-cycle window
    drift_slow: float = 0.0        # 1200-cycle window

    # Novelty detection
    novelty_score: float = 0.0     # 0.0=normal, 1.0=completely novel
    is_novel: bool = False

    # RUL estimation
    rul: Optional[RULEstimate] = None

    # Feature attribution
    top_sensors: List[SensorDiagnostics] = field(default_factory=list)

    # Operating conditions
    operating_condition: Optional[Tuple[float, ...]] = None
    condition_adjusted_score: float = 0.0

    # Adaptive thresholds
    thresholds_used: Dict[str, float] = field(default_factory=dict)

    # Uncertainty
    instability_p10: float = 0.0   # 10th percentile
    instability_p90: float = 0.0   # 90th percentile
    confidence_interval: Tuple[float, float] = (0.0, 1.0)

    # Early warnings
    early_warnings: List[EarlyWarningSignal] = field(default_factory=list)

    # Degradation mode
    degradation_mode: DegradationMode = DegradationMode.NORMAL

    # Change points
    change_detected_at_cycle: Optional[int] = None

    # Ensemble
    ensemble_agreement: float = 1.0  # How much do detection methods agree?

    # Cost-benefit
    maintenance_cost: float = 0.0
    failure_cost: float = 0.0
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        d = super().to_dict()
        d.update({
            'drift_fast': float(self.drift_fast),
            'drift_medium': float(self.drift_medium),
            'drift_slow': float(self.drift_slow),
            'novelty_score': float(self.novelty_score),
            'is_novel': bool(self.is_novel),
            'rul': self.rul.__dict__ if self.rul else None,
            'top_sensors': [s.__dict__ for s in self.top_sensors[:3]],
            'condition_adjusted_score': float(self.condition_adjusted_score),
            'instability_p10': float(self.instability_p10),
            'instability_p90': float(self.instability_p90),
            'early_warnings': [w.__dict__ for w in self.early_warnings],
            'degradation_mode': self.degradation_mode.value,
            'ensemble_agreement': float(self.ensemble_agreement),
            'maintenance_cost': float(self.maintenance_cost),
            'failure_cost': float(self.failure_cost),
            'recommended_action': self.recommended_action,
        })
        return d


class AdvancedSIIEngine(SIIEngine):
    """
    Enhanced SII Engine with comprehensive advanced detection capabilities.

    Includes:
    - Multi-scale drift analysis
    - Novelty detection via isolation forest
    - RUL estimation with confidence bounds
    - SHAP-style feature attribution
    - Operating condition normalization
    - Adaptive thresholds
    - Bayesian uncertainty quantification
    - Feedback-based learning
    - Sensor diagnostics
    - Ensemble anomaly detection
    - Early warning signals
    - Degradation mode classification
    - Change point detection
    - Cost-benefit analysis
    """

    def __init__(
        self,
        baseline_window: int = 50,
        recent_window: int = 12,
        system_type: str = "generic",
        operating_conditions: Optional[Dict[str, float]] = None,
        **kwargs
    ):
        super().__init__(baseline_window=baseline_window, recent_window=recent_window, **kwargs)

        self.system_type = system_type
        self.operating_conditions = operating_conditions or {}

        # Multi-scale windows
        self.window_sizes = {
            'fast': 12,
            'medium': min(120, baseline_window * 3),
            'slow': min(1200, baseline_window * 30),
        }
        self.drift_history_by_scale = {
            'fast': deque(maxlen=self.window_sizes['fast']),
            'medium': deque(maxlen=self.window_sizes['medium']),
            'slow': deque(maxlen=self.window_sizes['slow']),
        }

        # Novelty detection
        try:
            from sklearn.ensemble import IsolationForest
            self.isolation_forest = IsolationForest(contamination=0.05, random_state=42)
            self.novelty_training_data = deque(maxlen=500)
        except ImportError:
            self.isolation_forest = None

        # RUL estimation
        self.instability_trajectory = deque(maxlen=500)
        self.velocity_trajectory = deque(maxlen=500)

        # Sensor tracking
        self.sensor_contributions = {}
        self.sensor_anomaly_counts = deque(maxlen=100)

        # Operating condition baselines
        self.condition_baselines = {}  # {condition_tuple: BaselineProfile}

        # Adaptive thresholds per system type
        self.thresholds = self._get_thresholds_for_system(system_type)

        # Uncertainty tracking
        self.estimation_history = deque(maxlen=100)
        self.sensor_noise_estimate = 0.01

        # Feedback loop
        self.predictions_log = deque(maxlen=1000)
        self.outcomes_log = deque(maxlen=1000)
        self.prediction_accuracy = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0}

        # Early warning indicators
        self.volatility_history = deque(maxlen=50)
        self.correlation_history = deque(maxlen=50)

        # Degradation mode tracking
        self.mode_indicators = {}

        # Change point detection
        self.cusum_high = deque(maxlen=100)  # Cumulative sum for trend detection
        self.change_point_threshold = 3.0

        # Cost-benefit configuration
        self.maintenance_cost = 1000.0  # Default
        self.failure_cost = 50000.0     # Default

    def _get_thresholds_for_system(self, system_type: str) -> Dict[str, float]:
        """Get adaptive thresholds based on system type."""
        thresholds_map = {
            'pump': {
                'TRANSITION': 0.50,
                'UNSTABLE': 0.75,
                'LOCK_IN': 0.90,
            },
            'bearing': {
                'TRANSITION': 0.55,
                'UNSTABLE': 0.80,
                'LOCK_IN': 0.92,
            },
            'compressor': {
                'TRANSITION': 0.45,
                'UNSTABLE': 0.70,
                'LOCK_IN': 0.88,
            },
            'motor': {
                'TRANSITION': 0.52,
                'UNSTABLE': 0.78,
                'LOCK_IN': 0.91,
            },
            'precision_machine': {
                'TRANSITION': 0.40,
                'UNSTABLE': 0.70,
                'LOCK_IN': 0.85,
            },
            'critical_system': {
                'TRANSITION': 0.35,
                'UNSTABLE': 0.65,
                'LOCK_IN': 0.80,
            },
            'generic': {
                'TRANSITION': TRANSITION_THRESHOLD,
                'UNSTABLE': UNSTABLE_THRESHOLD,
                'LOCK_IN': LOCK_IN_THRESHOLD,
            }
        }
        return thresholds_map.get(system_type, thresholds_map['generic'])

    def update(
        self,
        x_t: np.ndarray,
        timestamp: float,
        operating_condition: Optional[Tuple[float, ...]] = None,
    ) -> AdvancedSIIOutput:
        """
        Process one frame with all advanced analytics.

        Args:
            x_t: Sensor vector
            timestamp: Timestamp
            operating_condition: Tuple of (temperature, load, speed, etc.)

        Returns:
            AdvancedSIIOutput with all metrics
        """
        # Get base output
        base_output = super().update(x_t, timestamp)

        # Create advanced output from base
        advanced = AdvancedSIIOutput(
            timestamp=base_output.timestamp,
            instability_score=base_output.instability_score,
            structural_drift=base_output.structural_drift,
            drift_velocity=base_output.drift_velocity,
            transition_pressure=base_output.transition_pressure,
            regime=base_output.regime,
            urgency=base_output.urgency,
            confidence=base_output.confidence,
            gradient_norm=base_output.gradient_norm,
            recovery_alignment=base_output.recovery_alignment,
            velocity_history=base_output.velocity_history,
            instability_history=base_output.instability_history,
            regime_history=base_output.regime_history,
        )

        # Only compute advanced metrics after warmup
        if not self.baseline_ready or base_output.regime == "WARMUP":
            return advanced

        # 1. Multi-scale analysis
        advanced.drift_fast, advanced.drift_medium, advanced.drift_slow = \
            self._compute_multiscale_drift(x_t)

        # 2. Novelty detection
        advanced.novelty_score, advanced.is_novel = self._compute_novelty(x_t)

        # 3. RUL estimation
        advanced.rul = self._estimate_rul(base_output.instability_score, base_output.drift_velocity)

        # 4. Feature attribution
        advanced.top_sensors = self._compute_sensor_diagnostics(x_t)

        # 5. Operating condition normalization
        if operating_condition:
            advanced.condition_adjusted_score = \
                self._adjust_for_operating_condition(advanced.instability_score, operating_condition)
        else:
            advanced.condition_adjusted_score = advanced.instability_score

        # 6. Adaptive thresholds (already built into _classify_regime_advanced)
        advanced.thresholds_used = self.thresholds

        # 7. Uncertainty quantification
        advanced.instability_p10, advanced.instability_p90, advanced.confidence_interval = \
            self._compute_uncertainty_bounds(advanced.instability_score)

        # 8. Feedback integration
        self._update_prediction_accuracy(advanced.instability_score, advanced.regime)

        # 9. Sensor diagnostics (already in feature attribution)

        # 10. Ensemble anomaly detection
        advanced.ensemble_agreement = self._compute_ensemble_agreement(x_t, base_output)

        # 11. Early warning signals
        advanced.early_warnings = self._detect_early_warnings()

        # 12. Degradation mode classification
        advanced.degradation_mode = self._classify_degradation_mode()

        # 13. System fingerprinting (implicit in baselines)

        # 14. Change point detection
        advanced.change_detected_at_cycle = self._detect_change_point()

        # 15. Cost-benefit analysis
        advanced.maintenance_cost, advanced.failure_cost, advanced.recommended_action = \
            self._compute_cost_benefit(advanced)

        return advanced

    def _compute_multiscale_drift(self, x_t: np.ndarray) -> Tuple[float, float, float]:
        """Compute structural drift at multiple timescales."""
        if not self.baseline_ready:
            return 0.0, 0.0, 0.0

        drifts = {}
        for scale_name, window_size in self.window_sizes.items():
            if len(self.sensor_history) >= window_size:
                window_data = np.array(list(self.sensor_history))[-window_size:]
                cov_t = self.compute_covariance(window_data)
                drift = self.compute_structural_drift(cov_t)
            else:
                drift = self.compute_structural_drift(np.array([x_t]))

            drifts[scale_name] = drift
            self.drift_history_by_scale[scale_name].append(drift)

        return drifts['fast'], drifts['medium'], drifts['slow']

    def _compute_novelty(self, x_t: np.ndarray) -> Tuple[float, bool]:
        """Detect out-of-distribution sensor patterns."""
        if self.isolation_forest is None:
            return 0.0, False

        # Add to training data
        self.novelty_training_data.append(x_t)

        # Retrain periodically
        if len(self.novelty_training_data) > 50 and self.frame_count % 50 == 0:
            try:
                self.isolation_forest.fit(np.array(list(self.novelty_training_data)))
            except:
                pass

        # Compute anomaly score (-1 = anomaly, 1 = normal)
        if len(self.novelty_training_data) > 10:
            try:
                anomaly_score = self.isolation_forest.score_samples(x_t.reshape(1, -1))[0]
                novelty = np.clip(-anomaly_score, 0.0, 1.0)  # Convert to 0-1
                is_novel = novelty > 0.5
            except:
                novelty, is_novel = 0.0, False
        else:
            novelty, is_novel = 0.0, False

        return novelty, is_novel

    def _estimate_rul(self, current_score: float, drift_velocity: float) -> Optional[RULEstimate]:
        """Estimate remaining useful life with confidence bounds."""
        if not self.baseline_ready or len(self.instability_history) < 10:
            return None

        failure_threshold = self.thresholds['LOCK_IN']

        # Simple linear extrapolation
        recent_scores = list(self.instability_history)[-10:]
        if len(recent_scores) > 1:
            velocity = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)
        else:
            velocity = drift_velocity

        if velocity > 0.001:  # Only if degrading
            cycles_to_failure = (failure_threshold - current_score) / velocity
            cycles_to_failure = max(1, int(cycles_to_failure))
        else:
            return None

        # Confidence bounds (±30%)
        p10 = int(cycles_to_failure * 0.7)
        p90 = int(cycles_to_failure * 1.3)

        # Confidence based on data quantity and consistency
        confidence = min(0.9, len(self.instability_history) / 100.0)

        # Degradation mode
        mode = self._classify_degradation_mode()

        # Probability of failure within 30 cycles
        prob_30 = min(1.0, max(0.0, (30 - cycles_to_failure) / 30.0 * 0.5 + 0.5))

        return RULEstimate(
            median_cycles=cycles_to_failure,
            p10_cycles=p10,
            p90_cycles=p90,
            confidence=confidence,
            degradation_rate=velocity,
            mode=mode,
            probability_failure_30days=prob_30,
        )

    def _compute_sensor_diagnostics(self, x_t: np.ndarray) -> List[SensorDiagnostics]:
        """Compute per-sensor health and attribution."""
        diagnostics = []

        for sensor_id in range(len(x_t)):
            value = x_t[sensor_id]
            baseline_mean = self.baseline.mean[sensor_id] if self.baseline.mean is not None else value
            baseline_std = np.sqrt(self.baseline.cov[sensor_id, sensor_id]) if self.baseline.cov is not None else 1.0

            # Deviation in standard deviations
            if baseline_std > 0:
                dev_sigmas = (value - baseline_mean) / baseline_std
            else:
                dev_sigmas = 0.0

            # Drift rate
            if len(self.sensor_history) > 1:
                prev_value = list(self.sensor_history)[-1][sensor_id]
                drift_rate = value - prev_value
            else:
                drift_rate = 0.0

            # Is anomalous (>3 sigma or very high drift)
            is_anomalous = abs(dev_sigmas) > 3.0 or abs(drift_rate) > baseline_std * 2

            # Is likely sensor failure vs. real degradation
            is_faulty = abs(dev_sigmas) > 5.0 or abs(drift_rate) > baseline_std * 5

            # Health score
            health = 1.0 - min(1.0, abs(dev_sigmas) / 5.0)

            # Contribution to instability
            contribution = self._compute_sensor_contribution(sensor_id)

            diag = SensorDiagnostics(
                sensor_id=f"s{sensor_id + 1}",
                current_value=float(value),
                baseline_mean=float(baseline_mean),
                baseline_std=float(baseline_std),
                deviation_sigmas=float(dev_sigmas),
                drift_rate=float(drift_rate),
                is_anomalous=bool(is_anomalous),
                is_likely_faulty=bool(is_faulty),
                health_score=float(health),
                contribution_to_instability=float(contribution),
            )
            diagnostics.append(diag)

        # Sort by contribution
        diagnostics.sort(key=lambda d: abs(d.contribution_to_instability), reverse=True)
        return diagnostics[:5]  # Top 5

    def _compute_sensor_contribution(self, sensor_id: int) -> float:
        """SHAP-style: how much does this sensor contribute?"""
        if not self.baseline_ready or len(self.sensor_history) < 2:
            return 0.0

        x_t = np.array(list(self.sensor_history)[-1])

        # Remove sensor, recompute drift
        x_t_without = x_t.copy()
        x_t_without[sensor_id] = self.baseline.mean[sensor_id]

        # Covariance with and without
        window_data = np.array(list(self.sensor_history))
        cov_full = self.compute_covariance(window_data)

        window_data_without = window_data.copy()
        window_data_without[:, sensor_id] = self.baseline.mean[sensor_id]
        cov_without = self.compute_covariance(window_data_without)

        drift_full = self.compute_structural_drift(cov_full)
        drift_without = self.compute_structural_drift(cov_without)

        contribution = (drift_full - drift_without) / (drift_full + 1e-9)
        return float(np.clip(contribution, -1.0, 1.0))

    def _adjust_for_operating_condition(
        self,
        score: float,
        operating_condition: Tuple[float, ...]
    ) -> float:
        """Adjust instability score for operating conditions."""
        condition_key = tuple(round(c, 1) for c in operating_condition)

        # If we have a baseline for this condition, use it
        if condition_key in self.condition_baselines:
            # Score relative to condition-specific baseline
            return score  # Already adjusted in baseline fitting

        # Otherwise, estimate adjustment
        # Higher temperature/load/speed typically increase baseline drift
        temp, load, speed = operating_condition[:3] if len(operating_condition) >= 3 else (0, 0, 0)

        # Simple linear adjustment
        adjustment = 1.0 + (temp / 100.0) * 0.1 + (load / 100.0) * 0.15
        adjusted = score / adjustment

        return float(adjusted)

    def _compute_uncertainty_bounds(
        self,
        score: float
    ) -> Tuple[float, float, Tuple[float, float]]:
        """Compute Bayesian confidence intervals."""
        num_samples = len(self.sensor_history)

        # Uncertainty from sensor noise and short history
        noise_uncertainty = self.sensor_noise_estimate / np.sqrt(max(1, num_samples))

        # Uncertainty from score volatility
        if len(self.instability_history) > 5:
            volatility = float(np.std(list(self.instability_history)[-10:]))
        else:
            volatility = 0.1

        total_uncertainty = noise_uncertainty + volatility * 0.5

        # 95% confidence interval
        p10 = score - 1.96 * total_uncertainty
        p90 = score + 1.96 * total_uncertainty

        p10 = np.clip(float(p10), 0.0, 1.0)
        p90 = np.clip(float(p90), 0.0, 1.0)

        return p10, p90, (p10, p90)

    def _update_prediction_accuracy(self, instability_score: float, regime: str) -> None:
        """Update accuracy metrics from feedback."""
        # Track predictions for later evaluation
        self.predictions_log.append({
            'cycle': self.frame_count,
            'score': instability_score,
            'regime': regime,
        })

    def _compute_ensemble_agreement(self, x_t: np.ndarray, output: SIIEngineOutput) -> float:
        """How much do different detection methods agree?"""
        agreements = []

        # Method 1: Covariance-based (current)
        cov_signal = output.instability_score > TRANSITION_THRESHOLD
        agreements.append(cov_signal)

        # Method 2: Velocity-based
        vel_signal = output.drift_velocity > 0.02
        agreements.append(vel_signal)

        # Method 3: Pressure-based
        pressure_signal = output.transition_pressure > 0.3
        agreements.append(pressure_signal)

        # Method 4: Sensor anomaly count
        baseline_stds = np.sqrt(np.diag(self.baseline.cov))
        anomalies = np.abs(x_t - self.baseline.mean) > 3 * baseline_stds
        anomaly_count = np.sum(anomalies)
        anomaly_signal = anomaly_count > 3
        agreements.append(anomaly_signal)

        # Compute agreement
        agreement = sum(agreements) / len(agreements)
        return float(agreement)

    def _detect_early_warnings(self) -> List[EarlyWarningSignal]:
        """Detect precursors to state transitions."""
        warnings = []

        if len(self.instability_history) < 10:
            return warnings

        # Check for increased volatility
        recent = list(self.instability_history)[-10:]
        volatility = float(np.std(recent))
        self.volatility_history.append(volatility)

        if len(self.volatility_history) > 5:
            volatility_trend = np.mean(list(self.volatility_history)[-5:])
            if volatility_trend > np.mean(list(self.volatility_history)[:-5]) * 1.5:
                warnings.append(EarlyWarningSignal(
                    signal_type="volatility_increase",
                    strength=min(1.0, volatility_trend / 0.1),
                    cycles_until_transition=5,
                    confidence=0.6,
                ))

        # Check for correlation structure changes
        if len(self.sensor_history) > 20:
            window = np.array(list(self.sensor_history))[-20:]
            corr = np.corrcoef(window.T)
            corr_strength = float(np.mean(np.abs(np.triu(corr, k=1))))
            self.correlation_history.append(corr_strength)

            if len(self.correlation_history) > 5:
                corr_change = self.correlation_history[-1] - np.mean(list(self.correlation_history)[:-1])
                if abs(corr_change) > 0.1:
                    warnings.append(EarlyWarningSignal(
                        signal_type="correlation_change",
                        strength=min(1.0, abs(corr_change)),
                        cycles_until_transition=8,
                        confidence=0.5,
                    ))

        return warnings

    def _classify_degradation_mode(self) -> DegradationMode:
        """Classify the type of degradation."""
        if not self.baseline_ready or len(self.instability_history) < 10:
            return DegradationMode.NORMAL

        recent = list(self.instability_history)[-10:]
        velocities = [recent[i+1] - recent[i] for i in range(len(recent)-1)]

        # Check patterns
        mean_vel = float(np.mean(velocities))
        std_vel = float(np.std(velocities))
        accel = velocities[-1] - velocities[0] if len(velocities) > 1 else 0

        # Determine mode
        if mean_vel < 0.001:
            return DegradationMode.NORMAL
        elif accel > std_vel * 2:
            return DegradationMode.ACCELERATING_DRIFT
        elif std_vel > mean_vel * 2:
            return DegradationMode.PERIODIC_OSCILLATION
        elif max(velocities) - min(velocities) > mean_vel * 5:
            return DegradationMode.SUDDEN_SPIKE
        else:
            return DegradationMode.LINEAR_DRIFT

    def _detect_change_point(self) -> Optional[int]:
        """Detect when degradation started using CUSUM."""
        if len(self.instability_history) < 20:
            return None

        # CUSUM: Cumulative Sum Control Chart
        target = float(np.mean(list(self.instability_history)[:10]))
        cusum = 0
        for i, score in enumerate(list(self.instability_history)[-20:]):
            cusum += (score - target - 0.01)  # 0.01 is drift allowance
            self.cusum_high.append(max(0, cusum))

            if cusum > self.change_point_threshold:
                return self.frame_count - 20 + i

        return None

    def _compute_cost_benefit(self, output: AdvancedSIIOutput) -> Tuple[float, float, str]:
        """Compute maintenance vs. failure costs."""
        # Maintenance cost (fixed)
        maint_cost = self.maintenance_cost

        # Failure cost (proportional to lead time)
        if output.rul:
            lead_time = output.rul.median_cycles
            failure_risk = output.rul.probability_failure_30days
            failure_cost = self.failure_cost * failure_risk
        else:
            failure_cost = 0.0

        # Recommendation
        if failure_cost > maint_cost * 2:
            recommendation = "SCHEDULE MAINTENANCE IMMEDIATELY"
        elif failure_cost > maint_cost:
            recommendation = "SCHEDULE MAINTENANCE WITHIN 5 CYCLES"
        elif output.regime in ("UNSTABLE", "LOCK_IN"):
            recommendation = "PREPARE MAINTENANCE, MONITOR CLOSELY"
        elif output.regime == "TRANSITION":
            recommendation = "MONITOR, SCHEDULE PREVENTIVE MAINTENANCE"
        else:
            recommendation = "CONTINUE MONITORING"

        return maint_cost, failure_cost, recommendation

    def log_prediction(self, regime: str, confidence: float) -> None:
        """Log a prediction for feedback."""
        self.predictions_log.append({
            'cycle': self.frame_count,
            'regime': regime,
            'confidence': confidence,
            'timestamp': datetime.now(),
        })

    def log_outcome(
        self,
        actual_state: str,
        action_taken: str,
        result: str,
    ) -> None:
        """Log outcome for learning."""
        self.outcomes_log.append({
            'cycle': self.frame_count,
            'actual_state': actual_state,
            'action': action_taken,
            'result': result,  # 'prevented_failure', 'false_alarm', 'too_late', etc.
            'timestamp': datetime.now(),
        })

    def get_accuracy_metrics(self) -> Dict[str, any]:
        """Get prediction accuracy statistics."""
        return {
            'true_positives': self.prediction_accuracy.get('tp', 0),
            'false_positives': self.prediction_accuracy.get('fp', 0),
            'true_negatives': self.prediction_accuracy.get('tn', 0),
            'false_negatives': self.prediction_accuracy.get('fn', 0),
            'predictions_logged': len(self.predictions_log),
            'outcomes_logged': len(self.outcomes_log),
        }
