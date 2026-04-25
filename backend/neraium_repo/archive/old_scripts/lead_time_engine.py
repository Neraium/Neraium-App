from __future__ import annotations

from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
import math
import numpy as np


@dataclass
class DetectorConfig:
    baseline_window: int = 120
    live_window: int = 24
    ema_alpha: float = 0.20
    ridge: float = 1e-4
    instability_boundary: float = 4.5
    target_fpr: float = 0.08
    adaptive_history_window: int = 240
    weak_signal_ratio: float = 0.82
    strong_persistence: int = 2
    weak_persistence: int = 3
    min_velocity: float = 1e-6
    warning_cap_hours: int = 240


@dataclass
class DetectionResult:
    site_id: str
    asset_id: str
    timestamp: str
    structural_drift_score: float
    smoothed_drift_score: float
    drift_velocity: float
    drift_acceleration: float
    relational_stability_score: float
    lead_time_hours: Optional[float]
    lead_time_lower_hours: Optional[float]
    lead_time_upper_hours: Optional[float]
    lead_time_confidence: float
    adaptive_threshold: float
    strong_signal: bool
    weak_signal: bool
    early_warning_mode: bool
    state: str
    structural_driver: str


class HybridSIIDetector:
    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self._frames: Dict[Tuple[str, str], Deque[np.ndarray]] = defaultdict(
            lambda: deque(maxlen=self.config.baseline_window)
        )
        self._smoothed: Dict[Tuple[str, str], float] = {}
        self._velocity: Dict[Tuple[str, str], float] = {}
        self._drift_history: Dict[Tuple[str, str], Deque[float]] = defaultdict(
            lambda: deque(maxlen=max(32, self.config.adaptive_history_window))
        )
        self._strong_streak: Dict[Tuple[str, str], int] = defaultdict(int)
        self._weak_streak: Dict[Tuple[str, str], int] = defaultdict(int)

    def _clean_vector(
        self,
        sensor_values: Tuple[Optional[float], ...],
    ) -> np.ndarray:
        vals = np.array(
            [0.0 if v is None or not math.isfinite(v) else float(v) for v in sensor_values],
            dtype=float,
        )
        return vals

    def _baseline_stats(self, history: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        X = np.vstack(history)
        mu = X.mean(axis=0)

        if X.shape[0] < 2:
            cov = np.eye(X.shape[1], dtype=float)
        else:
            cov = np.cov(X, rowvar=False)

        if cov.ndim == 0:
            cov = np.array([[float(cov)]], dtype=float)

        cov = cov + np.eye(cov.shape[0], dtype=float) * self.config.ridge
        return mu, cov

    def _mahalanobis(self, x: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> float:
        delta = x - mu
        inv = np.linalg.pinv(cov)
        score = float(np.sqrt(delta.T @ inv @ delta))
        return score

    def _ema(self, key: Tuple[str, str], drift: float) -> float:
        prev = self._smoothed.get(key, drift)
        s = self.config.ema_alpha * drift + (1.0 - self.config.ema_alpha) * prev
        self._smoothed[key] = s
        return s

    def _velocity_and_acceleration(self, key: Tuple[str, str], smoothed: float) -> Tuple[float, float]:
        prev_v = self._velocity.get(key, 0.0)
        prev_s = self._smoothed.get(key, smoothed)
        v = smoothed - prev_s
        a = v - prev_v
        self._velocity[key] = v
        return v, a

    def _relational_stability(self, history: List[np.ndarray]) -> float:
        if len(history) <= max(3, self.config.live_window):
            return 1.0

        recent = np.vstack(history[-self.config.live_window:])
        baseline = np.vstack(history[:-self.config.live_window])

        if baseline.shape[0] < 2 or recent.shape[0] < 2:
            return 1.0

        cov_recent = np.cov(recent, rowvar=False)
        cov_base = np.cov(baseline, rowvar=False)

        if cov_recent.ndim == 0:
            cov_recent = np.array([[float(cov_recent)]], dtype=float)
        if cov_base.ndim == 0:
            cov_base = np.array([[float(cov_base)]], dtype=float)

        diff = np.linalg.norm(cov_recent - cov_base, ord="fro")
        # Convert to a 0..1 stability score where lower covariance change = more stable
        score = 1.0 / (1.0 + diff)
        return float(score)

    def _lead_time(
        self,
        smoothed: float,
        velocity: float,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if velocity <= self.config.min_velocity:
            return None, None, None

        hours = (self.config.instability_boundary - smoothed) / velocity
        if not math.isfinite(hours):
            return None, None, None

        hours = max(0.0, min(float(hours), float(self.config.warning_cap_hours)))

        lower = max(0.0, hours * 0.75)
        upper = min(float(self.config.warning_cap_hours), hours * 1.25)
        return hours, lower, upper

    def _adaptive_boundary(self, key: Tuple[str, str], smoothed: float) -> float:
        scores = self._drift_history[key]
        scores.append(float(smoothed))

        if len(scores) < 16:
            return float(self.config.instability_boundary)

        quantile_level = float(max(0.50, min(0.995, 1.0 - self.config.target_fpr)))
        data = np.array(scores, dtype=float)
        threshold = float(np.quantile(data, quantile_level))
        # Keep threshold from collapsing too low, but allow adaptation under drift.
        floor = float(self.config.instability_boundary) * 0.55
        ceil = float(self.config.instability_boundary) * 1.65
        return max(floor, min(ceil, threshold))

    def _state_from_scores(
        self,
        key: Tuple[str, str],
        smoothed: float,
        stability: float,
        adaptive_threshold: float,
    ) -> Tuple[str, bool, bool, bool]:
        strong_signal = bool(smoothed >= adaptive_threshold or stability < 0.35)
        weak_threshold = adaptive_threshold * float(self.config.weak_signal_ratio)
        weak_signal = bool(smoothed >= weak_threshold or stability < 0.55)

        if strong_signal:
            self._strong_streak[key] += 1
        else:
            self._strong_streak[key] = 0

        if weak_signal:
            self._weak_streak[key] += 1
        else:
            self._weak_streak[key] = 0

        strong_persisted = self._strong_streak[key] >= int(self.config.strong_persistence)
        weak_persisted = self._weak_streak[key] >= int(self.config.weak_persistence)

        if strong_persisted:
            return "ALERT", strong_signal, weak_signal, False
        if weak_persisted:
            return "WATCH", strong_signal, weak_signal, False
        if weak_signal:
            return "EARLY_WARNING", strong_signal, weak_signal, True
        return "STABLE", strong_signal, weak_signal, False

    def _driver_name(
        self,
        x: np.ndarray,
        mu: np.ndarray,
        sensor_names: Tuple[str, ...],
    ) -> str:
        delta = np.abs(x - mu)
        idx = int(np.argmax(delta))
        return sensor_names[idx] if sensor_names else "unknown"

    def update(
        self,
        site_id: str,
        asset_id: str,
        timestamp: str,
        sensor_names: Tuple[str, ...],
        sensor_values: Tuple[Optional[float], ...],
        missing_fraction: float = 0.0,
    ) -> DetectionResult:
        key = (site_id, asset_id)
        x = self._clean_vector(sensor_values)

        history = self._frames[key]
        history.append(x)

        if len(history) < 8:
            return DetectionResult(
                site_id=site_id,
                asset_id=asset_id,
                timestamp=timestamp,
                structural_drift_score=0.0,
                smoothed_drift_score=0.0,
                drift_velocity=0.0,
                drift_acceleration=0.0,
                relational_stability_score=1.0,
                lead_time_hours=None,
                lead_time_lower_hours=None,
                lead_time_upper_hours=None,
                lead_time_confidence=0.0,
                adaptive_threshold=round(float(self.config.instability_boundary), 4),
                strong_signal=False,
                weak_signal=False,
                early_warning_mode=False,
                state="STABLE",
                structural_driver="warmup",
            )

        mu, cov = self._baseline_stats(list(history))
        raw_drift = self._mahalanobis(x, mu, cov)

        prev_smoothed = self._smoothed.get(key, raw_drift)
        smoothed = self._ema(key, raw_drift)
        velocity = smoothed - prev_smoothed
        prev_v = self._velocity.get(key, 0.0)
        acceleration = velocity - prev_v
        self._velocity[key] = velocity

        stability = self._relational_stability(list(history))
        adaptive_threshold = self._adaptive_boundary(key, smoothed)
        lead, lower, upper = self._lead_time(smoothed, velocity)

        confidence = max(
            0.05,
            min(
                0.99,
                1.0
                - (missing_fraction * 0.75)
                - min(abs(acceleration) * 0.05, 0.2),
            ),
        )

        state, strong_signal, weak_signal, early_warning_mode = self._state_from_scores(
            key=key,
            smoothed=smoothed,
            stability=stability,
            adaptive_threshold=adaptive_threshold,
        )
        driver = self._driver_name(x, mu, sensor_names)

        return DetectionResult(
            site_id=site_id,
            asset_id=asset_id,
            timestamp=timestamp,
            structural_drift_score=round(raw_drift, 4),
            smoothed_drift_score=round(smoothed, 4),
            drift_velocity=round(velocity, 4),
            drift_acceleration=round(acceleration, 4),
            relational_stability_score=round(stability, 4),
            lead_time_hours=None if lead is None else round(lead, 2),
            lead_time_lower_hours=None if lower is None else round(lower, 2),
            lead_time_upper_hours=None if upper is None else round(upper, 2),
            lead_time_confidence=round(confidence, 4),
            adaptive_threshold=round(adaptive_threshold, 4),
            strong_signal=strong_signal,
            weak_signal=weak_signal,
            early_warning_mode=early_warning_mode,
            state=state,
            structural_driver=driver,
        )
