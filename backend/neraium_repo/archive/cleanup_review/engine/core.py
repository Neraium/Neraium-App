"""Core runtime layer: frame ingestion, normalization, data quality.

Responsibilities:
- Frame vector extraction and sensor ordering
- Value normalization and NaN handling
- Data quality assessment and gate checking
- Temporal representation building
"""

from typing import Dict, List, Tuple, Optional
import numpy as np

from neraium_core.geometry import normalize_window
from neraium_core.data_quality import (
    compute_data_quality,
    data_quality_summary,
    impute_missing_simple,
    should_use_degraded_analytics,
)


def vector_from_sensor_values(
    sensor_values: Dict[str, object], order: List[str]
) -> np.ndarray:
    """Build a fixed-order vector from sensor dict; missing keys become NaN.

    Args:
        sensor_values: Dict mapping sensor name to value
        order: Ordered list of sensor names

    Returns:
        1D numpy array of values (missing = NaN)
    """
    values: list[float] = []
    for name in order:
        v = sensor_values.get(name)
        try:
            values.append(float(v) if v is not None else np.nan)
        except (TypeError, ValueError):
            values.append(np.nan)
    return np.asarray(values, dtype=float)


def normalize_windows(
    baseline_window: np.ndarray, recent_window: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Normalize baseline and recent windows to zero-mean, unit-variance.

    Args:
        baseline_window: 2D array (rows=samples, cols=features)
        recent_window: 2D array (rows=samples, cols=features)

    Returns:
        (z_baseline, baseline_mean, baseline_std,
         z_recent, recent_mean, recent_std)
    """
    z_baseline, baseline_mean, baseline_std = normalize_window(baseline_window)
    z_recent, recent_mean, recent_std = normalize_window(recent_window)
    return z_baseline, baseline_mean, baseline_std, z_recent, recent_mean, recent_std


def assess_data_quality(
    baseline_window: np.ndarray,
    recent_window: np.ndarray,
    sensor_names: List[str],
    timestamps_baseline: Optional[List[float]] = None,
    timestamps_recent: Optional[List[float]] = None,
) -> Tuple[object, dict, bool, np.ndarray, np.ndarray]:
    """Assess data quality and decide if degraded analytics needed.

    Args:
        baseline_window: 2D baseline array
        recent_window: 2D recent array
        sensor_names: List of sensor names
        timestamps_baseline: Baseline timestamps
        timestamps_recent: Recent timestamps

    Returns:
        (dq_report, dq_summary_dict, use_degraded, baseline_window_out, recent_window_out)
    """
    dq_report = compute_data_quality(
        baseline_window,
        recent_window,
        sensor_names=sensor_names,
        timestamps_baseline=timestamps_baseline,
        timestamps_recent=timestamps_recent,
    )

    dq_summary = data_quality_summary(dq_report)
    use_degraded = (not dq_report.gate_passed) and should_use_degraded_analytics(
        dq_report
    )

    # Optional imputation for degraded mode
    if not dq_report.gate_passed and use_degraded:
        baseline_window = impute_missing_simple(baseline_window, method="column_mean")
        recent_window = impute_missing_simple(recent_window, method="column_mean")

    return dq_report, dq_summary, use_degraded, baseline_window, recent_window


def get_valid_signal_mask(
    z_baseline: np.ndarray, z_recent: np.ndarray
) -> np.ndarray:
    """Identify sensors with sufficient variability to use for relational metrics.

    A sensor is "valid" if it has variance > 1e-12 in either baseline or recent.

    Args:
        z_baseline: Normalized baseline window
        z_recent: Normalized recent window

    Returns:
        Boolean mask for valid sensors
    """
    baseline_std = np.nanstd(z_baseline, axis=0)
    recent_std = np.nanstd(z_recent, axis=0)
    valid_mask = (np.nan_to_num(recent_std) > 1e-12) | (np.nan_to_num(baseline_std) > 1e-12)
    return valid_mask
