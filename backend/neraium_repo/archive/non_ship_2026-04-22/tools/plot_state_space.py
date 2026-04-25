from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _pca(points: np.ndarray) -> np.ndarray:
    if points.size == 0:
        return np.zeros((0, 2), dtype=float)
    centered = points - np.mean(points, axis=0, keepdims=True)
    cov = np.cov(centered.T) if centered.shape[0] > 1 else np.eye(centered.shape[1], dtype=float)
    eigvals, eigvecs = np.linalg.eigh(np.atleast_2d(cov))
    order = np.argsort(eigvals)[::-1]
    basis = eigvecs[:, order[: min(2, eigvecs.shape[1])]]
    reduced = centered @ basis
    if reduced.shape[1] < 2:
        reduced = np.pad(reduced, ((0, 0), (0, 2 - reduced.shape[1])), mode="constant")
    return reduced


def _load_vectors(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        cols = [
            "geometry_path_length",
            "geometry_local_velocity_norm",
            "geometry_local_acceleration_norm",
            "geometry_curvature",
            "state_space_statistics_covariance_trace",
            "state_space_statistics_state_contraction_score",
            "state_space_statistics_state_expansion_score",
            "state_graph_branching_factor",
            "state_graph_graph_divergence_score",
        ]
        present = [c for c in cols if c in df.columns]
        if not present:
            return np.zeros((0, 2), dtype=float)
        mat = df[present].fillna(0.0).to_numpy(dtype=float)
        return _pca(mat)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    vectors: list[np.ndarray] = []
    for r in rows:
        geom = (r.get("geometry") or (r.get("experimental_analytics", {}).get("geometry", {})))
        stats = (r.get("state_space_statistics") or (r.get("experimental_analytics", {}).get("state_space_statistics", {})))
        graph = (r.get("state_graph") or (r.get("experimental_analytics", {}).get("state_graph", {})))
        vectors.append(
            np.array(
                [
                    float(geom.get("path_length", 0.0)),
                    float(geom.get("local_velocity_norm", 0.0)),
                    float(geom.get("local_acceleration_norm", 0.0)),
                    float(geom.get("curvature", 0.0)),
                    float(stats.get("covariance_trace", 0.0)),
                    float(stats.get("state_contraction_score", 0.0)),
                    float(stats.get("state_expansion_score", 0.0)),
                    float(graph.get("branching_factor", 0.0)),
                    float(graph.get("graph_divergence_score", 0.0)),
                ],
                dtype=float,
            )
        )
    return _pca(np.vstack(vectors)) if vectors else np.zeros((0, 2), dtype=float)


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot state-space trajectory (deterministic PCA projection).")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    points = _load_vectors(Path(args.input))
    if points.shape[0] == 0:
        raise SystemExit("No state-space vectors found in payload.")

    t = np.arange(points.shape[0])
    plt.figure(figsize=(8, 4))
    sc = plt.scatter(points[:, 0], points[:, 1], c=t, cmap="viridis", s=28)
    plt.plot(points[:, 0], points[:, 1], alpha=0.45)
    branch_idx = np.where(np.linalg.norm(points - np.mean(points, axis=0, keepdims=True), axis=1) > np.percentile(np.linalg.norm(points - np.mean(points, axis=0, keepdims=True), axis=1), 75))[0]
    if branch_idx.size:
        plt.scatter(points[branch_idx, 0], points[branch_idx, 1], marker="x", s=50, label="branching region")
        plt.legend(loc="best")
    plt.colorbar(sc, label="time index")
    plt.title("State-space trajectory")
    plt.xlabel("projection-1")
    plt.ylabel("projection-2")
    plt.tight_layout()
    plt.savefig(args.output, dpi=140)


if __name__ == "__main__":
    main()
