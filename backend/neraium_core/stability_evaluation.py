"""
Nominal-window stability metrics (operational_stability_index and components).

Used by comparative benchmarks and offline evaluation - not required for single-frame inference.
Depends on pandas when computing from timeseries DataFrames.
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def compute_operational_stability_index(sub: Any) -> dict[str, float]:
    """
    Composite stability over nominal operation windows (baseline + recovery).
    Components are empirical rates / inverse dispersion from the run itself (no per-variant constants).
    """
    if pd is None or sub is None or getattr(sub, "empty", True) or len(sub) < 4:
        return {
            "operational_stability_index": 0.0,
            "strict_nominal_rate": 0.0,
            "nominal_stable_rate": 0.0,
            "nominal_structure_rate": 0.0,
            "nominal_false_positive_burden": 0.0,
            "nominal_state_switch_rate": 0.0,
            "nominal_instability_cv_inverse": 0.0,
            "nominal_temporal_coherence_consistency": 0.0,
            "nominal_confidence_consistency": 0.0,
            "mean_regime_distance_nominal": 0.0,
            "mean_nominal_consistency_nominal": 0.0,
        }

    st = sub["state"].values
    intr = sub["interpreted_state"].values
    pure = (st == "STABLE") & (intr == "NOMINAL_STRUCTURE")
    strict_nominal_rate = float(np.mean(pure.astype(float)))
    nominal_stable_rate = float(np.mean((st == "STABLE").astype(float)))
    nominal_structure_rate = float(np.mean((intr == "NOMINAL_STRUCTURE").astype(float)))
    nominal_false_positive_burden = float(np.mean(np.isin(st, ["WATCH", "ALERT"]).astype(float)))

    if len(st) > 1:
        switches = np.mean(st[1:] != st[:-1])
        nominal_state_switch_rate = float(switches)
    else:
        nominal_state_switch_rate = 0.0

    inst = sub["latest_instability"].to_numpy(dtype=float)
    m = float(np.mean(np.abs(inst)) + 1e-9)
    cv = float(np.std(inst) / m)
    nominal_instability_cv_inverse = float(1.0 / (1.0 + cv))

    tc = sub["temporal_coherence_score"].to_numpy(dtype=float)
    tc_m = float(np.mean(tc) + 1e-9)
    nominal_temporal_coherence_consistency = float(1.0 - min(1.0, float(np.std(tc) / tc_m)))

    cs = sub["confidence_score"].to_numpy(dtype=float)
    c_m = float(np.mean(cs) + 1e-9)
    nominal_confidence_consistency = float(1.0 - min(1.0, float(np.std(cs) / c_m)))

    rd = sub["regime_distance"].to_numpy(dtype=float)
    mean_regime_distance_nominal = float(np.mean(rd))

    mean_nominal_consistency_nominal = (
        float(sub["nominal_consistency_score"].mean()) if "nominal_consistency_score" in sub.columns else 0.0
    )

    terms = np.array(
        [
            strict_nominal_rate,
            1.0 - nominal_false_positive_burden,
            1.0 - nominal_state_switch_rate,
            nominal_instability_cv_inverse,
            nominal_temporal_coherence_consistency,
            nominal_confidence_consistency,
            mean_nominal_consistency_nominal,
        ],
        dtype=float,
    )
    operational_stability_index = float(np.clip(np.mean(terms), 0.0, 1.0))

    return {
        "operational_stability_index": operational_stability_index,
        "strict_nominal_rate": strict_nominal_rate,
        "nominal_stable_rate": nominal_stable_rate,
        "nominal_structure_rate": nominal_structure_rate,
        "nominal_false_positive_burden": nominal_false_positive_burden,
        "nominal_state_switch_rate": nominal_state_switch_rate,
        "nominal_instability_cv_inverse": nominal_instability_cv_inverse,
        "nominal_temporal_coherence_consistency": nominal_temporal_coherence_consistency,
        "nominal_confidence_consistency": nominal_confidence_consistency,
        "mean_regime_distance_nominal": mean_regime_distance_nominal,
        "mean_nominal_consistency_nominal": mean_nominal_consistency_nominal,
    }
