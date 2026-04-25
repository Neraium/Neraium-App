"""Relational instability and graph metrics.

Responsibilities:
- Relational stability (correlation frame-to-frame)
- Relational drift (relationship changes)
- Adjacency matrix and graph metrics
- Signal structural importance (per-node criticality)
- Subsystem spectral measures

Note: Delegates to existing geometry and graph modules.
This layer will grow as graph-based detection is enhanced.
"""

from typing import Dict, Any
import numpy as np

from neraium_core.geometry import (
    signal_structural_importance,
)
from neraium_core.graph import graph_metrics, thresholded_adjacency
from neraium_core.subsystems import subsystem_spectral_measures


def compute_relational_stability(
    corr_recent: np.ndarray, prev_corr_matrix: np.ndarray | None
) -> float:
    """Compute correlation matrix stability (how much changed frame-to-frame).

    Args:
        corr_recent: Current correlation matrix
        prev_corr_matrix: Previous frame's correlation matrix

    Returns:
        Stability score in [0, 1] where 1 = unchanged
    """
    if prev_corr_matrix is None or prev_corr_matrix.shape != corr_recent.shape:
        return 1.0

    relational_stability = 1.0 - float(np.mean(np.abs(corr_recent - prev_corr_matrix)))
    return max(0.0, min(1.0, relational_stability))


def compute_relational_metrics(
    corr_baseline: np.ndarray,
    corr_recent: np.ndarray,
    z_recent_valid: np.ndarray,
) -> Dict[str, Any]:
    """Compute all relational instability metrics.

    Args:
        corr_baseline: Baseline correlation matrix
        corr_recent: Recent correlation matrix
        z_recent_valid: Normalized recent data (valid sensors only)

    Returns:
        Dictionary with relational metrics
    """
    # Relational drift: how much relationships changed
    rel_delta = corr_recent - corr_baseline
    relational_raw = float(np.mean(np.abs(rel_delta))) if rel_delta.size else 0.0

    # Graph structure
    adjacency = thresholded_adjacency(corr_recent, threshold=0.6)
    graph = graph_metrics(adjacency, corr=corr_recent)

    # Signal importance
    signal_importance = signal_structural_importance(corr_recent)

    # Subsystem measures
    subsystem = subsystem_spectral_measures(corr_recent)

    return {
        "relational_drift": float(relational_raw),
        "adjacency": np.asarray(adjacency, dtype=float),
        "graph": graph,
        "signal_importance": signal_importance,
        "subsystem": subsystem,
    }
