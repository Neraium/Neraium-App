"""
Baseline Comparison Runner: Validates SIIEngine against alternative detection methods.

Implements four independent detection approaches:
1. SIIEngine: Unified instability score from covariance drift + velocity + pressure
2. Static Threshold: Simple threshold on instability or drift metric
3. Z-Score Anomaly: Multi-dimensional z-score detection
4. PCA Reconstruction: Anomaly detection via PCA reconstruction error

Compares detection timing, lead times, and precision across all methods.

Output: CSV with unit_id, failure_cycle, detection timings and lead times for each method.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import numpy as np
from collections import deque

from neraium_core.sii_engine_unified import SIIEngine


@dataclass
class DetectionEvent:
    """Records when a detection method fired."""
    method: str
    cycle: int
    score: float
    timestamp: float
    confidence: float = 1.0


@dataclass
class ComparisonResult:
    """Results for a single test case (unit_id)."""
    unit_id: str
    failure_cycle: Optional[int]
    sii_detection_cycle: Optional[int]
    threshold_detection_cycle: Optional[int]
    zscore_detection_cycle: Optional[int]
    pca_detection_cycle: Optional[int]
    sii_lead_time: Optional[int]
    threshold_lead_time: Optional[int]
    zscore_lead_time: Optional[int]
    pca_lead_time: Optional[int]

    def to_csv_row(self) -> dict[str, Any]:
        """Convert to CSV row."""
        return {
            "unit_id": self.unit_id,
            "failure_cycle": self.failure_cycle or "",
            "sii_detection_cycle": self.sii_detection_cycle or "",
            "threshold_detection_cycle": self.threshold_detection_cycle or "",
            "zscore_detection_cycle": self.zscore_detection_cycle or "",
            "pca_detection_cycle": self.pca_detection_cycle or "",
            "sii_lead_time": self.sii_lead_time or "",
            "threshold_lead_time": self.threshold_lead_time or "",
            "zscore_lead_time": self.zscore_lead_time or "",
            "pca_lead_time": self.pca_lead_time or "",
        }


class ThresholdDetector:
    """Simple threshold-based detection on instability score."""

    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
        self.detection_cycle: Optional[int] = None

    def update(self, instability_score: float, cycle: int) -> bool:
        """Check if instability exceeds threshold."""
        if self.detection_cycle is None and instability_score >= self.threshold:
            self.detection_cycle = cycle
            return True
        return False


class ZScoreDetector:
    """Z-score based anomaly detection."""

    def __init__(
        self,
        baseline_window: int = 50,
        zscore_threshold: float = 2.5,
        recent_window: int = 12,
    ):
        self.baseline_window = baseline_window
        self.zscore_threshold = zscore_threshold
        self.recent_window = recent_window

        # Use baseline_window for accumulating baseline samples
        self.sensor_history: deque[np.ndarray] = deque(maxlen=baseline_window)
        self.baseline_mean: Optional[np.ndarray] = None
        self.baseline_std: Optional[np.ndarray] = None
        self.frame_count = 0
        self.detection_cycle: Optional[int] = None

    def update(self, x_t: np.ndarray, cycle: int) -> bool:
        """Check if sample is anomalous via z-score."""
        x_t = np.asarray(x_t, dtype=float)
        self.frame_count += 1

        # Warmup: accumulate baseline
        if self.frame_count <= self.baseline_window:
            self.sensor_history.append(x_t)
            if self.frame_count == self.baseline_window:
                data = np.array(list(self.sensor_history), dtype=float)
                self.baseline_mean = np.mean(data, axis=0)
                self.baseline_std = np.std(data, axis=0) + 1e-9
            return False

        # After baseline ready: check z-scores
        if self.baseline_mean is None or self.baseline_std is None:
            return False

        self.sensor_history.append(x_t)

        # Compute z-scores
        z_scores = np.abs((x_t - self.baseline_mean) / self.baseline_std)
        max_zscore = float(np.max(z_scores))

        # Detect if any dimension exceeds threshold
        if self.detection_cycle is None and max_zscore >= self.zscore_threshold:
            self.detection_cycle = cycle
            return True

        return False


class PCADetector:
    """PCA-based reconstruction error anomaly detection."""

    def __init__(
        self,
        baseline_window: int = 50,
        n_components: int = 3,
        error_threshold: float = 0.5,
        recent_window: int = 12,
    ):
        self.baseline_window = baseline_window
        self.n_components = n_components
        self.error_threshold = error_threshold
        self.recent_window = recent_window

        # Use baseline_window for accumulating baseline samples
        self.sensor_history: deque[np.ndarray] = deque(maxlen=baseline_window)
        self.pca_components: Optional[np.ndarray] = None
        self.pca_mean: Optional[np.ndarray] = None
        self.frame_count = 0
        self.detection_cycle: Optional[int] = None

    def update(self, x_t: np.ndarray, cycle: int) -> bool:
        """Check if reconstruction error indicates anomaly."""
        x_t = np.asarray(x_t, dtype=float)
        self.frame_count += 1

        # Warmup: accumulate baseline
        if self.frame_count <= self.baseline_window:
            self.sensor_history.append(x_t)
            if self.frame_count == self.baseline_window:
                self._fit_pca()
            return False

        # After baseline ready: check reconstruction error
        if self.pca_components is None or self.pca_mean is None:
            return False

        self.sensor_history.append(x_t)

        # Compute reconstruction error
        error = self._reconstruction_error(x_t)

        if self.detection_cycle is None and error >= self.error_threshold:
            self.detection_cycle = cycle
            return True

        return False

    def _fit_pca(self) -> None:
        """Fit PCA model on baseline data."""
        data = np.array(list(self.sensor_history), dtype=float)
        self.pca_mean = np.mean(data, axis=0)
        centered = data - self.pca_mean

        # Compute SVD
        try:
            U, S, Vt = np.linalg.svd(centered.T, full_matrices=False)
            n_comp = min(self.n_components, U.shape[1])
            self.pca_components = U[:, :n_comp]
        except (ValueError, np.linalg.LinAlgError):
            # Fallback: use identity
            self.pca_components = np.eye(data.shape[1], min(self.n_components, data.shape[1]))

    def _reconstruction_error(self, x_t: np.ndarray) -> float:
        """Compute PCA reconstruction error."""
        if self.pca_components is None or self.pca_mean is None:
            return 0.0

        centered = x_t - self.pca_mean
        projected = self.pca_components @ (self.pca_components.T @ centered)
        residual = centered - projected
        error = float(np.linalg.norm(residual))
        return error


class BaselineComparisonRunner:
    """Runs all detection methods on the same data and compares results."""

    def __init__(
        self,
        baseline_window: int = 50,
        recent_window: int = 12,
    ):
        self.baseline_window = baseline_window
        self.recent_window = recent_window

    def run(
        self,
        sensor_data: np.ndarray,
        timestamps: np.ndarray,
        unit_id: str,
        failure_cycle: Optional[int] = None,
    ) -> ComparisonResult:
        """
        Run all detection methods on sensor data.

        Args:
            sensor_data: Shape (N, d) where N = cycles, d = sensors
            timestamps: Shape (N,) timestamp for each cycle
            unit_id: Identifier for test case
            failure_cycle: True failure cycle (if known)

        Returns:
            ComparisonResult with detection timings and lead times
        """
        sii_engine = SIIEngine(
            baseline_window=self.baseline_window,
            recent_window=self.recent_window,
        )
        threshold_detector = ThresholdDetector(threshold=0.65)
        zscore_detector = ZScoreDetector(
            baseline_window=self.baseline_window,
            zscore_threshold=2.5,
            recent_window=self.recent_window,
        )
        pca_detector = PCADetector(
            baseline_window=self.baseline_window,
            n_components=min(3, sensor_data.shape[1]),
            error_threshold=0.5,
            recent_window=self.recent_window,
        )

        sii_detection_cycle: Optional[int] = None
        threshold_detection_cycle: Optional[int] = None
        zscore_detection_cycle: Optional[int] = None
        pca_detection_cycle: Optional[int] = None

        # Process each cycle
        for cycle in range(sensor_data.shape[0]):
            x_t = sensor_data[cycle, :]
            timestamp = float(timestamps[cycle])

            # Always update SII engine for fresh outputs
            sii_output = sii_engine.update(x_t, timestamp)

            # SIIEngine detection
            if sii_detection_cycle is None:
                if sii_output.instability_score >= 0.65:
                    sii_detection_cycle = cycle + 1

            # Threshold detection (use structural drift - independent signal)
            if threshold_detection_cycle is None:
                threshold_detector.update(sii_output.structural_drift, cycle + 1)
                if threshold_detector.detection_cycle is not None:
                    threshold_detection_cycle = threshold_detector.detection_cycle

            # Z-score detection
            if zscore_detection_cycle is None:
                zscore_detector.update(x_t, cycle + 1)
                if zscore_detector.detection_cycle is not None:
                    zscore_detection_cycle = zscore_detector.detection_cycle

            # PCA detection
            if pca_detection_cycle is None:
                pca_detector.update(x_t, cycle + 1)
                if pca_detector.detection_cycle is not None:
                    pca_detection_cycle = pca_detector.detection_cycle

        # Compute lead times (cycles before failure)
        sii_lead_time = (
            (failure_cycle - sii_detection_cycle) if sii_detection_cycle and failure_cycle else None
        )
        threshold_lead_time = (
            (failure_cycle - threshold_detection_cycle) if threshold_detection_cycle and failure_cycle else None
        )
        zscore_lead_time = (
            (failure_cycle - zscore_detection_cycle) if zscore_detection_cycle and failure_cycle else None
        )
        pca_lead_time = (
            (failure_cycle - pca_detection_cycle) if pca_detection_cycle and failure_cycle else None
        )

        return ComparisonResult(
            unit_id=unit_id,
            failure_cycle=failure_cycle,
            sii_detection_cycle=sii_detection_cycle,
            threshold_detection_cycle=threshold_detection_cycle,
            zscore_detection_cycle=zscore_detection_cycle,
            pca_detection_cycle=pca_detection_cycle,
            sii_lead_time=sii_lead_time,
            threshold_lead_time=threshold_lead_time,
            zscore_lead_time=zscore_lead_time,
            pca_lead_time=pca_lead_time,
        )

    def export_csv(self, results: list[ComparisonResult], output_path: str | Path) -> None:
        """Export comparison results to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "unit_id",
            "failure_cycle",
            "sii_detection_cycle",
            "threshold_detection_cycle",
            "zscore_detection_cycle",
            "pca_detection_cycle",
            "sii_lead_time",
            "threshold_lead_time",
            "zscore_lead_time",
            "pca_lead_time",
        ]

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_csv_row())


__all__ = [
    "BaselineComparisonRunner",
    "ComparisonResult",
    "ThresholdDetector",
    "ZScoreDetector",
    "PCADetector",
]
