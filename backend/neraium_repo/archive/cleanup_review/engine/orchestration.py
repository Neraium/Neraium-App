"""Orchestration: coordinates core detections and auxiliary analytics.

Responsibilities:
- Call core detection components in sequence
- Optional auxiliary analytics (gated by feature flags)
- Assemble results into final output
- Handle fast mode policy vs degraded mode

This layer implements the "glue logic" that used to be inline in
alignment.py StructuralEngine.process_frame(). By delegating to
specialized modules, we reduce complexity and improve testability.
"""

from typing import Dict, Any, Optional, List
import numpy as np

from . import (
    core,
    windows,
    drift,
    relational,
    temporal,
    transitions,
)
from neraium_core.geometry import correlation_matrix, structural_drift
from neraium_core.early_warning import early_warning_metrics


class CoreDetectionOrchestrator:
    """Orchestrates core structural detection path (frames → detections)."""

    def __init__(
        self,
        baseline_window: int = 50,
        recent_window: int = 12,
        window_stride: int = 1,
    ):
        self.window_extractor = windows.WindowExtractor(
            baseline_window, recent_window, window_stride
        )
        self.drift_machine = drift.DriftStateMachine()
        self.transition_computer = transitions.TransitionMetricsComputer()

    def process_windows(
        self,
        baseline_window: np.ndarray,
        recent_window: np.ndarray,
        baseline_ts: Optional[List[float]],
        recent_ts: Optional[List[float]],
        sensor_names: List[str],
    ) -> Dict[str, Any]:
        """Process baseline and recent windows through full detection pipeline.

        Args:
            baseline_window: 2D baseline matrix
            recent_window: 2D recent matrix
            baseline_ts: Baseline timestamps
            recent_ts: Recent timestamps
            sensor_names: Sensor names

        Returns:
            Dictionary with:
            - z_baseline, z_recent: Normalized windows
            - data_quality: Quality report and summary
            - drift_state: Alert state and score
            - relational_metrics: Graph/stability metrics
            - temporal_metrics: Timing and rate features
        """
        # Step 1: Data quality assessment
        (
            dq_report,
            dq_summary,
            use_degraded,
            baseline_window,
            recent_window,
        ) = core.assess_data_quality(
            baseline_window,
            recent_window,
            sensor_names,
            baseline_ts,
            recent_ts,
        )

        # Step 2: Normalization
        z_baseline, bl_mean, bl_std, z_recent, rc_mean, rc_std = core.normalize_windows(
            baseline_window, recent_window
        )

        # Step 3: Valid signal detection
        valid_mask = core.get_valid_signal_mask(z_baseline, z_recent)
        valid_count = int(np.sum(valid_mask))

        # Step 4: Drift detection (requires correlation matrices)
        corr_baseline = None
        corr_recent = None
        drift_score = 0.0
        alert_state = "STABLE"

        if valid_count >= 2:
            z_base_valid = z_baseline[:, valid_mask]
            z_recent_valid = z_recent[:, valid_mask]

            # Correlation matrices
            corr_baseline = correlation_matrix(z_base_valid)
            corr_recent = correlation_matrix(z_recent_valid)

            # Structural drift
            drift_score = structural_drift(corr_recent, corr_baseline, norm="fro")
            self.drift_machine.calibrate_thresholds()
            alert_state, smoothed_drift = self.drift_machine.update(drift_score)

            # Relational metrics
            rel_metrics = relational.compute_relational_metrics(
                corr_baseline, corr_recent, z_recent_valid
            )

            # Temporal metrics
            temp_metrics = temporal.compute_temporal_metrics(z_recent_valid, recent_ts)
        else:
            rel_metrics = {"relational_drift": 0.0, "adjacency": None}
            temp_metrics = {"temporal_features": {}, "temporal_quality": {}}

        # Step 5: Early warning (signal-level anomalies)
        warning = early_warning_metrics(np.nan_to_num(recent_window, nan=0.0))

        return {
            "z_baseline": z_baseline,
            "z_recent": z_recent,
            "baseline_mean": bl_mean,
            "baseline_std": bl_std,
            "recent_mean": rc_mean,
            "recent_std": rc_std,
            "valid_mask": valid_mask,
            "valid_count": valid_count,
            "data_quality_report": dq_report,
            "data_quality_summary": dq_summary,
            "use_degraded": use_degraded,
            "drift_score": drift_score,
            "alert_state": alert_state,
            "corr_baseline": corr_baseline,
            "corr_recent": corr_recent,
            "relational_metrics": rel_metrics,
            "temporal_metrics": temp_metrics,
            "early_warning": warning,
        }
