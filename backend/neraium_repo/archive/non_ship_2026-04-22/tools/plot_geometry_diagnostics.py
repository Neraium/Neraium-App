from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot trajectory geometry diagnostics.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    path = Path(args.input)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        curvature = df.get("geometry_curvature", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        consistency = df.get("geometry_directional_consistency", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        smoothness = df.get("geometry_path_smoothness", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        lock_in = df.get("constraint_analysis_lock_in_score", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else [payload]
        curvature, consistency, smoothness, lock_in = [], [], [], []
        for r in rows:
            g = (r.get("geometry") or (r.get("experimental_analytics", {}).get("geometry", {})))
            c = (r.get("experimental_analytics", {}).get("constraint_analysis", {}))
            curvature.append(float(g.get("curvature", 0.0)))
            consistency.append(float(g.get("directional_consistency", 0.0)))
            smoothness.append(float(g.get("path_smoothness", 0.0)))
            lock_in.append(float(c.get("lock_in_score", 0.0) or 0.0))

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(curvature, label="curvature")
    axes[0].plot(consistency, label="directional_consistency")
    axes[0].plot(smoothness, label="path_smoothness")
    axes[0].legend()
    axes[0].set_title("Trajectory geometry diagnostics")
    axes[1].plot(lock_in, label="lock_in_score")
    axes[1].plot([c * (1.0 - d) for c, d in zip(curvature, consistency)], label="curvature_divergence_overlay")
    axes[1].legend()
    axes[1].set_xlabel("time index")
    plt.tight_layout()
    plt.savefig(args.output, dpi=140)


if __name__ == "__main__":
    main()
