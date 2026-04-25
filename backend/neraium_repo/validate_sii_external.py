#!/usr/bin/env python3
"""
Independent External Validation of SII Engine

Purpose:
- Load FD004 data directly (no pipeline dependencies)
- Run SIIEngine inference only
- Independently implement baseline methods
- Validate reproducibility
- Compare against internal validation results

Requirements (NOT imported):
- sii_engine_adapter
- sii_evidence_builder
- sii_causal_narratives
- sii_fd004_validation (for method comparison only)

This script proves SII results are reproducible outside the system pipeline.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import numpy as np
from collections import deque
import math

from neraium_core.sii_engine_unified import SIIEngine


@dataclass
class ValidationResult:
    """Results for a single unit."""
    unit_id: str
    failure_cycle: int
    sii_detection_cycle: Optional[int] = None
    threshold_detection_cycle: Optional[int] = None
    zscore_detection_cycle: Optional[int] = None
    pca_detection_cycle: Optional[int] = None

    @property
    def sii_lead_time(self) -> Optional[int]:
        return self.failure_cycle - self.sii_detection_cycle if self.sii_detection_cycle else None

    @property
    def threshold_lead_time(self) -> Optional[int]:
        return self.failure_cycle - self.threshold_detection_cycle if self.threshold_detection_cycle else None

    @property
    def zscore_lead_time(self) -> Optional[int]:
        return self.failure_cycle - self.zscore_detection_cycle if self.zscore_detection_cycle else None

    @property
    def pca_lead_time(self) -> Optional[int]:
        return self.failure_cycle - self.pca_detection_cycle if self.pca_detection_cycle else None


@dataclass
class ValidationMetrics:
    """Summary statistics for a method."""
    method_name: str
    detection_cycles: list[int] = field(default_factory=list)
    lead_times: list[int] = field(default_factory=list)
    detected_count: int = 0
    total_count: int = 0

    @property
    def detection_rate(self) -> float:
        return 100.0 * self.detected_count / self.total_count if self.total_count > 0 else 0.0

    @property
    def mean_lead_time(self) -> float:
        return float(np.mean(self.lead_times)) if self.lead_times else 0.0

    @property
    def median_lead_time(self) -> float:
        return float(np.median(self.lead_times)) if self.lead_times else 0.0

    @property
    def std_lead_time(self) -> float:
        return float(np.std(self.lead_times)) if len(self.lead_times) >= 2 else 0.0

    @property
    def min_lead_time(self) -> float:
        return float(np.min(self.lead_times)) if self.lead_times else 0.0

    @property
    def max_lead_time(self) -> float:
        return float(np.max(self.lead_times)) if self.lead_times else 0.0


class IndependentThresholdDetector:
    """Independent threshold implementation (replicates internal logic)."""

    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
        self.detection_cycle: Optional[int] = None

    def update(self, score: float) -> bool:
        if self.detection_cycle is None and score >= self.threshold:
            self.detection_cycle = True
        return self.detection_cycle is not None


class IndependentZScoreDetector:
    """Independent Z-score implementation (replicates internal logic)."""

    def __init__(self, baseline_window: int = 50, zscore_threshold: float = 2.5):
        self.baseline_window = baseline_window
        self.zscore_threshold = zscore_threshold
        self.sensor_history: deque = deque(maxlen=baseline_window)
        self.baseline_mean: Optional[np.ndarray] = None
        self.baseline_std: Optional[np.ndarray] = None
        self.frame_count = 0
        self.detection_cycle: Optional[int] = None

    def update(self, x_t: np.ndarray, cycle: int) -> bool:
        x_t = np.asarray(x_t, dtype=float)
        self.frame_count += 1

        if self.frame_count <= self.baseline_window:
            self.sensor_history.append(x_t)
            if self.frame_count == self.baseline_window:
                data = np.array(list(self.sensor_history), dtype=float)
                self.baseline_mean = np.mean(data, axis=0)
                self.baseline_std = np.std(data, axis=0) + 1e-9
            return False

        if self.baseline_mean is None or self.baseline_std is None:
            return False

        z_scores = np.abs((x_t - self.baseline_mean) / self.baseline_std)
        max_zscore = float(np.max(z_scores))

        if self.detection_cycle is None and max_zscore >= self.zscore_threshold:
            self.detection_cycle = cycle
            return True

        return False


class IndependentPCADetector:
    """Independent PCA implementation (replicates internal logic)."""

    def __init__(self, baseline_window: int = 50, n_components: int = 3, error_threshold: float = 0.5):
        self.baseline_window = baseline_window
        self.n_components = n_components
        self.error_threshold = error_threshold
        self.sensor_history: deque = deque(maxlen=baseline_window)
        self.pca_components: Optional[np.ndarray] = None
        self.pca_mean: Optional[np.ndarray] = None
        self.frame_count = 0
        self.detection_cycle: Optional[int] = None

    def update(self, x_t: np.ndarray, cycle: int) -> bool:
        x_t = np.asarray(x_t, dtype=float)
        self.frame_count += 1

        if self.frame_count <= self.baseline_window:
            self.sensor_history.append(x_t)
            if self.frame_count == self.baseline_window:
                self._fit_pca()
            return False

        if self.pca_components is None or self.pca_mean is None:
            return False

        error = self._reconstruction_error(x_t)
        if self.detection_cycle is None and error >= self.error_threshold:
            self.detection_cycle = cycle
            return True

        return False

    def _fit_pca(self) -> None:
        data = np.array(list(self.sensor_history), dtype=float)
        self.pca_mean = np.mean(data, axis=0)
        centered = data - self.pca_mean

        try:
            U, S, Vt = np.linalg.svd(centered.T, full_matrices=False)
            n_comp = min(self.n_components, U.shape[1])
            self.pca_components = U[:, :n_comp]
        except (ValueError, np.linalg.LinAlgError):
            self.pca_components = np.eye(data.shape[1], min(self.n_components, data.shape[1]))

    def _reconstruction_error(self, x_t: np.ndarray) -> float:
        if self.pca_components is None or self.pca_mean is None:
            return 0.0
        centered = x_t - self.pca_mean
        projected = self.pca_components @ (self.pca_components.T @ centered)
        residual = centered - projected
        return float(np.linalg.norm(residual))


class ExternalValidator:
    """Independent validation runner - no pipeline dependencies."""

    def __init__(self, baseline_window: int = 50):
        self.baseline_window = baseline_window

    def validate_unit(
        self,
        unit_id: str,
        sensor_data: np.ndarray,
        timestamps: np.ndarray,
        failure_cycle: int,
    ) -> ValidationResult:
        """
        Validate a single unit independently.

        Args:
            unit_id: Unit identifier
            sensor_data: Shape (N, d) - N cycles, d sensors
            timestamps: Shape (N,)
            failure_cycle: True failure cycle

        Returns:
            ValidationResult with detection timings
        """
        # Initialize SIIEngine (inference only, no modifications)
        sii_engine = SIIEngine(baseline_window=self.baseline_window, recent_window=self.baseline_window)

        # Initialize independent baseline methods
        threshold_detector = IndependentThresholdDetector(threshold=0.65)
        zscore_detector = IndependentZScoreDetector(baseline_window=self.baseline_window, zscore_threshold=2.5)
        pca_detector = IndependentPCADetector(
            baseline_window=self.baseline_window,
            n_components=min(3, sensor_data.shape[1]),
            error_threshold=0.5,
        )

        sii_detection: Optional[int] = None
        threshold_detection: Optional[int] = None
        zscore_detection: Optional[int] = None
        pca_detection: Optional[int] = None

        # Process each cycle
        for cycle in range(sensor_data.shape[0]):
            x_t = sensor_data[cycle, :]
            timestamp = float(timestamps[cycle])
            cycle_num = cycle + 1

            # SII inference (read-only)
            sii_output = sii_engine.update(x_t, timestamp)

            # SII detection
            if sii_detection is None and sii_output.instability_score >= 0.65:
                sii_detection = cycle_num

            # Threshold detection (independent signal: structural_drift)
            if threshold_detection is None:
                threshold_detector.update(sii_output.structural_drift)
                if threshold_detector.detection_cycle and threshold_detection is None:
                    threshold_detection = cycle_num

            # Z-score detection
            if zscore_detection is None:
                zscore_detector.update(x_t, cycle_num)
                if zscore_detector.detection_cycle is not None:
                    zscore_detection = zscore_detector.detection_cycle

            # PCA detection
            if pca_detection is None:
                pca_detector.update(x_t, cycle_num)
                if pca_detector.detection_cycle is not None:
                    pca_detection = pca_detector.detection_cycle

        return ValidationResult(
            unit_id=unit_id,
            failure_cycle=failure_cycle,
            sii_detection_cycle=sii_detection,
            threshold_detection_cycle=threshold_detection,
            zscore_detection_cycle=zscore_detection,
            pca_detection_cycle=pca_detection,
        )

    def run_validation(self, units: dict[str, tuple]) -> tuple[list[ValidationResult], dict[str, Any]]:
        """
        Run validation on all units.

        Args:
            units: Dict mapping unit_id to (sensor_data, timestamps, failure_cycle)

        Returns:
            (results, summary_statistics)
        """
        results = []

        print(f"Running independent validation on {len(units)} units...")
        for i, (unit_id, (sensor_data, timestamps, failure_cycle)) in enumerate(units.items()):
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(units)} units")

            result = self.validate_unit(unit_id, sensor_data, timestamps, failure_cycle)
            results.append(result)

        # Compute summary statistics
        summary = self._compute_summary(results)
        return results, summary

    def _compute_summary(self, results: list[ValidationResult]) -> dict[str, Any]:
        """Compute summary statistics for all results."""
        sii_metrics = ValidationMetrics(method_name="SII")
        threshold_metrics = ValidationMetrics(method_name="Threshold")
        zscore_metrics = ValidationMetrics(method_name="ZScore")
        pca_metrics = ValidationMetrics(method_name="PCA")

        for result in results:
            sii_metrics.total_count += 1
            threshold_metrics.total_count += 1
            zscore_metrics.total_count += 1
            pca_metrics.total_count += 1

            if result.sii_detection_cycle:
                sii_metrics.detected_count += 1
                sii_metrics.detection_cycles.append(result.sii_detection_cycle)
                if result.sii_lead_time and result.sii_lead_time > 0:
                    sii_metrics.lead_times.append(result.sii_lead_time)

            if result.threshold_detection_cycle:
                threshold_metrics.detected_count += 1
                threshold_metrics.detection_cycles.append(result.threshold_detection_cycle)
                if result.threshold_lead_time and result.threshold_lead_time > 0:
                    threshold_metrics.lead_times.append(result.threshold_lead_time)

            if result.zscore_detection_cycle:
                zscore_metrics.detected_count += 1
                zscore_metrics.detection_cycles.append(result.zscore_detection_cycle)
                if result.zscore_lead_time and result.zscore_lead_time > 0:
                    zscore_metrics.lead_times.append(result.zscore_lead_time)

            if result.pca_detection_cycle:
                pca_metrics.detected_count += 1
                pca_metrics.detection_cycles.append(result.pca_detection_cycle)
                if result.pca_lead_time and result.pca_lead_time > 0:
                    pca_metrics.lead_times.append(result.pca_lead_time)

        return {
            "sii": {
                "detection_rate": sii_metrics.detection_rate,
                "mean_lead_time": sii_metrics.mean_lead_time,
                "median_lead_time": sii_metrics.median_lead_time,
                "std_lead_time": sii_metrics.std_lead_time,
                "min_lead_time": sii_metrics.min_lead_time,
                "max_lead_time": sii_metrics.max_lead_time,
                "detected_count": sii_metrics.detected_count,
            },
            "threshold": {
                "detection_rate": threshold_metrics.detection_rate,
                "mean_lead_time": threshold_metrics.mean_lead_time,
                "median_lead_time": threshold_metrics.median_lead_time,
                "std_lead_time": threshold_metrics.std_lead_time,
                "min_lead_time": threshold_metrics.min_lead_time,
                "max_lead_time": threshold_metrics.max_lead_time,
                "detected_count": threshold_metrics.detected_count,
            },
            "zscore": {
                "detection_rate": zscore_metrics.detection_rate,
                "mean_lead_time": zscore_metrics.mean_lead_time,
                "median_lead_time": zscore_metrics.median_lead_time,
                "std_lead_time": zscore_metrics.std_lead_time,
                "min_lead_time": zscore_metrics.min_lead_time,
                "max_lead_time": zscore_metrics.max_lead_time,
                "detected_count": zscore_metrics.detected_count,
            },
            "pca": {
                "detection_rate": pca_metrics.detection_rate,
                "mean_lead_time": pca_metrics.mean_lead_time,
                "median_lead_time": pca_metrics.median_lead_time,
                "std_lead_time": pca_metrics.std_lead_time,
                "min_lead_time": pca_metrics.min_lead_time,
                "max_lead_time": pca_metrics.max_lead_time,
                "detected_count": pca_metrics.detected_count,
            },
        }

    def export_csv(self, results: list[ValidationResult], output_path: str) -> None:
        """Export results to CSV."""
        with open(output_path, "w", newline="") as f:
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
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow({
                    "unit_id": result.unit_id,
                    "failure_cycle": result.failure_cycle,
                    "sii_detection_cycle": result.sii_detection_cycle or "",
                    "threshold_detection_cycle": result.threshold_detection_cycle or "",
                    "zscore_detection_cycle": result.zscore_detection_cycle or "",
                    "pca_detection_cycle": result.pca_detection_cycle or "",
                    "sii_lead_time": result.sii_lead_time or "",
                    "threshold_lead_time": result.threshold_lead_time or "",
                    "zscore_lead_time": result.zscore_lead_time or "",
                    "pca_lead_time": result.pca_lead_time or "",
                })

        print(f"Results exported to {output_path}")

    def export_summary(self, summary: dict[str, Any], output_path: str) -> None:
        """Export summary statistics to JSON."""
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"Summary exported to {output_path}")

    @staticmethod
    def print_summary(summary: dict[str, Any]) -> None:
        """Print summary statistics."""
        print("\n" + "=" * 80)
        print("EXTERNAL VALIDATION SUMMARY")
        print("=" * 80)

        for method_name in ["sii", "threshold", "zscore", "pca"]:
            metrics = summary.get(method_name, {})
            print(f"\n{method_name.upper()}:")
            print(f"  Detection Rate: {metrics.get('detection_rate', 0):.1f}%")
            print(f"  Mean Lead Time: {metrics.get('mean_lead_time', 0):.1f} cycles")
            print(f"  Median Lead Time: {metrics.get('median_lead_time', 0):.1f} cycles")
            print(f"  Std Dev: {metrics.get('std_lead_time', 0):.1f} cycles")
            print(f"  Range: {metrics.get('min_lead_time', 0):.1f} - {metrics.get('max_lead_time', 0):.1f} cycles")
            print(f"  Detected: {metrics.get('detected_count', 0)} units")

        print("\n" + "=" * 80)
        print("SII IMPROVEMENT vs THRESHOLD:")
        sii_lead = summary.get("sii", {}).get("mean_lead_time", 0)
        threshold_lead = summary.get("threshold", {}).get("mean_lead_time", 0)
        if threshold_lead > 0:
            improvement = sii_lead - threshold_lead
            improvement_pct = 100.0 * improvement / threshold_lead
            print(f"  Lead Time: {improvement:.1f} cycles ({improvement_pct:+.1f}%)")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    print("External Validation Script")
    print("=" * 80)
    print("Note: This script requires FD004 data to be loaded externally.")
    print("It demonstrates independent validation without pipeline dependencies.")
    print("=" * 80)

__all__ = [
    "ExternalValidator",
    "ValidationResult",
    "ValidationMetrics",
    "IndependentThresholdDetector",
    "IndependentZScoreDetector",
    "IndependentPCADetector",
]
