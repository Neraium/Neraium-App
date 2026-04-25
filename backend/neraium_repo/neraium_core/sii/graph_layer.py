from __future__ import annotations

import numpy as np

from .errors import SIIValidationError
from .types import GraphSnapshot, GraphState


def _validate_square(name: str, m: np.ndarray) -> np.ndarray:
    arr = np.asarray(m, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise SIIValidationError(f"{name} must be a square matrix")
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def _threshold_from_distribution(abs_vals: np.ndarray, fallback: float) -> float:
    if abs_vals.size == 0:
        return float(fallback)
    q75 = float(np.percentile(abs_vals, 75.0))
    q60 = float(np.percentile(abs_vals, 60.0))
    lo = 0.05
    hi = 0.95
    thr = max(lo, min(hi, q75))
    if thr <= 0.05:
        thr = max(lo, min(hi, q60))
    return float(thr)


def build_adaptive_adjacency(corr: np.ndarray, fallback_threshold: float) -> np.ndarray:
    corr = _validate_square("correlation_matrix", corr)
    n = corr.shape[0]
    if n == 0:
        return corr.copy()
    idx = np.triu_indices(n, k=1)
    abs_vals = np.abs(corr[idx])
    thr = _threshold_from_distribution(abs_vals, fallback_threshold)
    adj = (np.abs(corr) >= thr).astype(float)
    np.fill_diagonal(adj, 0.0)
    return adj


def _avg_shortest_path_length(adj: np.ndarray) -> float:
    n = int(adj.shape[0])
    if n <= 1:
        return 0.0
    dist = np.full((n, n), np.inf, dtype=float)
    np.fill_diagonal(dist, 0.0)
    edge_idx = np.where(adj > 0.0)
    dist[edge_idx] = 1.0
    for k in range(n):
        dist = np.minimum(dist, dist[:, [k]] + dist[[k], :])
    finite = dist[np.isfinite(dist) & (dist > 0.0)]
    if finite.size == 0:
        return 0.0
    return float(np.mean(finite))


def build_graph_snapshot(state: GraphState, *, threshold: float) -> GraphSnapshot:
    corr = _validate_square("correlation_matrix", state.adjacency)
    adj = build_adaptive_adjacency(corr, fallback_threshold=threshold)

    n = int(adj.shape[0])
    edge_count = int(np.sum(adj))
    density = float(edge_count / max(1.0, float(n * (n - 1))))
    mean_abs_weight = float(np.mean(np.abs(corr[np.triu_indices(n, k=1)]))) if n > 1 else 0.0
    spectral_radius = float(np.max(np.abs(np.linalg.eigvalsh(corr)))) if n > 0 else 0.0

    deg = np.sum(adj, axis=1) if n > 0 else np.array([], dtype=float)
    degree_centrality = {
        state.feature_names[i]: float(deg[i] / max(1.0, float(n - 1)))
        for i in range(min(n, len(state.feature_names)))
    }

    lap = np.diag(np.sum(adj, axis=1)) - adj if n > 0 else np.zeros((0, 0), dtype=float)
    lap_trace = float(np.trace(lap)) if n > 0 else 0.0

    return GraphSnapshot(
        adjacency=adj,
        node_count=n,
        edge_count=edge_count,
        density=density,
        mean_abs_weight=mean_abs_weight,
        spectral_radius=spectral_radius,
        laplacian_trace=lap_trace,
        degree_centrality=degree_centrality,
    )


def graph_departure_score(current: GraphSnapshot, baseline: GraphSnapshot | None) -> float:
    if baseline is None or baseline.adjacency.shape != current.adjacency.shape:
        return 0.0

    l1_deformation = float(np.mean(np.abs(current.adjacency - baseline.adjacency)))
    density_shift = abs(float(current.density) - float(baseline.density))
    spectral_shift = abs(float(current.spectral_radius) - float(baseline.spectral_radius))
    curr_path = _avg_shortest_path_length(current.adjacency)
    base_path = _avg_shortest_path_length(baseline.adjacency)
    path_shift = abs(curr_path - base_path)
    return float(0.40 * l1_deformation + 0.22 * density_shift + 0.18 * spectral_shift + 0.20 * path_shift)


def graph_state(
    current_corr: np.ndarray,
    baseline_adj: np.ndarray | None,
    threshold: float,
    feature_names: list[str] | None = None,
) -> GraphState:
    corr = _validate_square("correlation_matrix", current_corr)
    adj = build_adaptive_adjacency(corr, fallback_threshold=threshold)
    n = int(adj.shape[0])
    edges = float(np.sum(adj))
    density = float(edges / max(1.0, float(n * (n - 1))))
    avg_degree = float(edges / max(1.0, float(n)))
    if baseline_adj is None or baseline_adj.shape != adj.shape:
        deformation = 0.0
    else:
        deformation = float(np.mean(np.abs(adj - baseline_adj)))
    if feature_names is None:
        names = [f"s{i}" for i in range(n)]
    else:
        names = list(feature_names[:n]) + [f"s{i}" for i in range(len(feature_names), n)]
    return GraphState(
        adjacency=adj,
        feature_names=names,
        density=density,
        avg_degree=avg_degree,
        l1_deformation=deformation,
    )
