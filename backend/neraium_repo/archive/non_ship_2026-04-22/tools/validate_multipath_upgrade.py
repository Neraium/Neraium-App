from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from neraium_core.branching import derive_branching_analysis
from neraium_core.experimental_analytics.directional_evolution import derive_directional_evolution_features
from neraium_core.experimental_analytics.path_prototypes import derive_path_prototypes
from neraium_core.experimental_analytics.trajectory_analysis import classify_trajectory_path
from neraium_core.experimental_analytics.trajectory_shape_features import derive_trajectory_shape_features


def _normalized_entropy(probs: list[float]) -> float:
    probs = [p for p in probs if p > 0.0]
    if len(probs) <= 1:
        return 0.0
    import math

    ent = -sum(p * math.log(p) for p in probs)
    return float(ent / math.log(len(probs)))


def _old_metrics(path_scores: dict[str, float]) -> dict[str, float]:
    vals = [float(path_scores[k]) for k in ("stabilizing", "metastable", "diverging")]
    # Legacy branch output committed to top-1 path identity in projection outputs.
    probs = [1.0, 0.0, 0.0] if vals else [1.0]
    return {
        "path_diversity": round(float(1.0 - max(probs)), 4),
        "dominant_path_concentration": round(float(max(probs)), 4),
        "branch_entropy": round(float(_normalized_entropy(probs)), 4),
    }


def _build_analysis(window: np.ndarray, drift_history: list[float], pressure_history: list[float]) -> tuple[dict[str, object], dict[str, object]]:
    directional = derive_directional_evolution_features(recent_window=window)
    shape = derive_trajectory_shape_features(recent_window=window)
    prototypes = derive_path_prototypes(directional_evolution=directional, trajectory_shape=shape)
    trajectory = classify_trajectory_path(
        drift_history=drift_history,
        transition_pressure_history=pressure_history,
        subsystem_instability_history=[x * 1.05 for x in drift_history],
        regime_novelty_history=np.linspace(0.08, 0.45, len(drift_history)).tolist(),
        shock_activity_history=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        reversibility_classification="METASTABLE",
        reversibility_score=0.52,
        directional_evolution=directional,
        trajectory_shape=shape,
        path_prototypes=prototypes,
    )
    branching = derive_branching_analysis(trajectory) or {}
    return trajectory, branching


def _real_dataset_window() -> np.ndarray:
    data = np.loadtxt(Path("train_FD004.txt"), dtype=float)
    # column0=id, column1=cycle, use remaining as multivariate observables
    rows = data[data[:, 0] == 1.0]
    return rows[-14:, 2:]


def main() -> None:
    real_window = _real_dataset_window()
    real_traj, real_branch = _build_analysis(
        real_window,
        drift_history=[0.22, 0.31, 0.44, 0.53, 0.61, 0.73],
        pressure_history=[0.35, 0.46, 0.58, 0.71, 0.86, 0.97],
    )

    t = np.linspace(0.0, 1.0, 14)
    synthetic_window = np.stack(
        [
            t * 1.2,
            np.sin(5.5 * t) * 0.35 + t * 0.15,
            np.where(t > 0.6, 1.4 * t, 0.3 * t),
            1.1 - t,
        ],
        axis=1,
    )
    synth_traj, synth_branch = _build_analysis(
        synthetic_window,
        drift_history=[0.25, 0.32, 0.41, 0.48, 0.59, 0.64],
        pressure_history=[0.41, 0.48, 0.57, 0.65, 0.74, 0.79],
    )

    report = {}
    for name, traj, branch in [("real_dataset", real_traj, real_branch), ("synthetic_benchmark", synth_traj, synth_branch)]:
        old = _old_metrics(traj["path_scores"])
        new_diag = branch.get("diagnostics", {}) if isinstance(branch, dict) else {}
        new = {
            "path_diversity": new_diag.get("path_diversity_score"),
            "dominant_path_concentration": new_diag.get("dominant_path_concentration_ratio"),
            "branch_entropy": branch.get("branch_entropy"),
        }
        report[name] = {
            "before": old,
            "after": new,
            "branch_count_estimate": branch.get("branch_count_estimate"),
            "candidate_paths": branch.get("candidate_paths"),
            "dominant_branch": branch.get("dominant_branch"),
            "alternative_branch": branch.get("alternative_branch"),
        }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
