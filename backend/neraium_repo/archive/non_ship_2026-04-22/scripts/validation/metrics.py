"""Metric computation for validation datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class DatasetMetrics:
    """Computed metrics for a dataset."""

    dataset_name: str
    unit_count: int
    mean_lead_time: float
    median_lead_time: float
    p50_gt_50_cycles: float  # % of units with >50 cycles
    p50_gt_100_cycles: float  # % of units with >100 cycles
    best_case_unit: str | int
    best_case_lead_time: float
    worst_case_unit: str | int
    worst_case_lead_time: float
    median_case_unit: str | int
    median_case_lead_time: float
    total_records: int

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV export."""
        return {
            "dataset": self.dataset_name,
            "unit_count": self.unit_count,
            "mean_lead_time": round(self.mean_lead_time, 2),
            "median_lead_time": round(self.median_lead_time, 2),
            "pct_units_gt_50_cycles": round(self.p50_gt_50_cycles, 1),
            "pct_units_gt_100_cycles": round(self.p50_gt_100_cycles, 1),
            "best_case_unit": self.best_case_unit,
            "best_case_lead_time": round(self.best_case_lead_time, 2),
            "worst_case_unit": self.worst_case_unit,
            "worst_case_lead_time": round(self.worst_case_lead_time, 2),
            "median_case_unit": self.median_case_unit,
            "median_case_lead_time": round(self.median_case_lead_time, 2),
            "total_records": self.total_records,
        }


def compute_lead_time(row_data: pd.DataFrame, drift_threshold: float) -> Optional[float]:
    """
    Compute lead time from structural_drift_score.

    Lead time = cycles from first structural divergence to failure (or end-of-run if failure is not explicitly labeled).
    Structural divergence is defined as the point where the structural_drift_score first exceeds the threshold.
    """
    if not len(row_data):
        return None

    # Get structural_drift_score column
    if "structural_drift_score" not in row_data.columns:
        return None

    # Get the cycle column
    cycle_col = "cycle" if "cycle" in row_data.columns else None
    if not cycle_col:
        return None

    # Find first cycle where drift exceeds threshold
    exceeded = row_data[row_data["structural_drift_score"] >= drift_threshold]
    if len(exceeded) == 0:
        # Never exceeded threshold; use full cycle count
        return float(len(row_data))

    first_exceeded_cycle = exceeded[cycle_col].iloc[0]
    last_cycle = row_data[cycle_col].iloc[-1]

    return float(last_cycle - first_exceeded_cycle + 1)


def compute_metrics(
    df: pd.DataFrame,
    dataset_name: str,
    drift_threshold: float = 0.5,
) -> DatasetMetrics:
    """
    Compute all metrics for a dataset.

    Args:
        df: DataFrame with columns: unit, cycle, structural_drift_score
        dataset_name: Name of dataset (e.g., 'FD004')
        drift_threshold: Threshold for structural_drift_score

    Returns:
        DatasetMetrics object
    """
    if df is None or len(df) == 0:
        raise ValueError("Empty dataset")

    # Group by unit
    units = df["unit"].unique()
    unit_count = len(units)

    lead_times = []
    unit_lead_time_map = {}

    for unit in units:
        unit_data = df[df["unit"] == unit].sort_values("cycle")
        lead_time = compute_lead_time(unit_data, drift_threshold)
        if lead_time is not None:
            lead_times.append(lead_time)
            unit_lead_time_map[unit] = lead_time

    if not lead_times:
        # No valid lead times; use cycle count per unit
        lead_times = []
        for unit in units:
            unit_data = df[df["unit"] == unit]
            lead_time = float(len(unit_data))
            lead_times.append(lead_time)
            unit_lead_time_map[unit] = lead_time

    lead_times_array = np.array(lead_times)

    # Compute percentiles
    p50_gt_50 = (lead_times_array > 50).sum() / len(lead_times) * 100 if lead_times else 0.0
    p50_gt_100 = (lead_times_array > 100).sum() / len(lead_times) * 100 if lead_times else 0.0

    # Find best, worst, median cases
    # Best case = maximum lead time (longest lead time = earliest structural detection)
    # Worst case = minimum lead time (shortest lead time = latest structural detection)
    best_idx = np.argmax(lead_times_array)
    worst_idx = np.argmin(lead_times_array)
    median_idx = np.argsort(lead_times_array)[len(lead_times_array) // 2]

    best_unit = units[best_idx]
    worst_unit = units[worst_idx]
    median_unit = units[median_idx]

    return DatasetMetrics(
        dataset_name=dataset_name,
        unit_count=unit_count,
        mean_lead_time=float(np.mean(lead_times_array)),
        median_lead_time=float(np.median(lead_times_array)),
        p50_gt_50_cycles=p50_gt_50,
        p50_gt_100_cycles=p50_gt_100,
        best_case_unit=best_unit,
        best_case_lead_time=float(lead_times_array[best_idx]),
        worst_case_unit=worst_unit,
        worst_case_lead_time=float(lead_times_array[worst_idx]),
        median_case_unit=median_unit,
        median_case_lead_time=float(lead_times_array[median_idx]),
        total_records=len(df),
    )


def create_lead_time_summary(
    df: pd.DataFrame,
    metrics: DatasetMetrics,
    drift_threshold: float = 0.5,
) -> pd.DataFrame:
    """
    Create a per-unit lead time summary.

    Args:
        df: Dataset DataFrame
        metrics: Computed metrics
        drift_threshold: Drift threshold

    Returns:
        DataFrame with columns: unit, lead_time, cycles, best, median, worst
    """
    units = df["unit"].unique()
    rows = []

    for unit in sorted(units):
        unit_data = df[df["unit"] == unit].sort_values("cycle")
        lead_time = compute_lead_time(unit_data, drift_threshold)
        if lead_time is None:
            lead_time = float(len(unit_data))

        # Handle both int and string unit identifiers
        is_best = unit == metrics.best_case_unit
        is_median = unit == metrics.median_case_unit
        is_worst = unit == metrics.worst_case_unit

        # Try to convert to int for CSV display, fallback to string
        try:
            unit_display = int(unit)
        except (ValueError, TypeError):
            unit_display = str(unit)

        rows.append({
            "unit": unit_display,
            "lead_time": round(lead_time, 2),
            "total_cycles": len(unit_data),
            "is_best_case": is_best,
            "is_median_case": is_median,
            "is_worst_case": is_worst,
        })

    return pd.DataFrame(rows)
