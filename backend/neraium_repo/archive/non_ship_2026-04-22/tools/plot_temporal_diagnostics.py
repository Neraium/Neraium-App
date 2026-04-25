from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.representation_compare import build_temporal_representation, load_dataset


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot temporal diagnostic charts.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True, help="CSV produced by compare_representations.py")
    p.add_argument("--entity-col", default=None)
    p.add_argument("--time-col", default=None)
    p.add_argument("--mode", default="combined")
    p.add_argument("--output", type=Path, default=Path("temporal_diagnostics.png"))
    return p.parse_args()


def _risk_to_score(v: str | float | None) -> float:
    m = {"IMMINENT": 1.0, "SHORT_TERM": 0.7, "MID_TERM": 0.45, "LONG_TERM": 0.2}
    if v is None:
        return 0.0
    return float(m.get(str(v).upper(), 0.0))


def main() -> None:
    args = parse_args()
    raw_df, spec = load_dataset(args.input, entity_col=args.entity_col, time_col=args.time_col)
    rep = build_temporal_representation(raw_df, spec, mode=args.mode)
    results = pd.read_csv(args.results)

    feature_cols = [c for c in rep.columns if c not in {spec.entity_col, spec.time_col}]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))

    # 1) trajectory embeddings over time (first 2 PCA-like axes via SVD)
    X = rep[feature_cols].fillna(0.0).values
    X = X - X.mean(axis=0, keepdims=True)
    u, s, _ = np.linalg.svd(X, full_matrices=False)
    emb1 = u[:, 0] * s[0] if s.size else np.zeros(len(rep))
    emb2 = u[:, 1] * s[1] if s.size > 1 else np.zeros(len(rep))
    axes[0, 0].scatter(emb1, emb2, c=rep[spec.time_col], s=8, cmap="viridis")
    axes[0, 0].set_title("Trajectory embeddings (time-colored)")

    # 2) early vs late separability
    early = rep.groupby(spec.entity_col).head(max(2, int(rep.groupby(spec.entity_col).size().median() * 0.2)))
    late = rep.groupby(spec.entity_col).tail(max(2, int(rep.groupby(spec.entity_col).size().median() * 0.2)))
    e_cent = early.groupby(spec.entity_col)[feature_cols].mean()
    l_cent = late.groupby(spec.entity_col)[feature_cols].mean()
    axes[0, 1].hist(np.linalg.norm(e_cent - e_cent.mean(axis=0), axis=1), bins=10, alpha=0.6, label="early")
    axes[0, 1].hist(np.linalg.norm(l_cent - l_cent.mean(axis=0), axis=1), bins=10, alpha=0.6, label="late")
    axes[0, 1].set_title("Early vs late separability")
    axes[0, 1].legend()

    # 3) per-entity drift curves
    for entity, g in results.groupby("entity"):
        axes[0, 2].plot(g["time"], g["structural_drift_score"], alpha=0.35)
    axes[0, 2].set_title("Per-entity drift curves")

    # 4) lock-in score over time
    lock = pd.to_numeric(results["lock_in_score"], errors="coerce")
    tmp = results.assign(lock=lock).dropna(subset=["lock"])
    if not tmp.empty:
        mean_lock = tmp.groupby("time")["lock"].mean()
        axes[1, 0].plot(mean_lock.index, mean_lock.values)
    axes[1, 0].set_title("Lock-in score over time")

    # 5) horizon state transitions
    hz = results.assign(h_score=results["risk_horizon"].map(_risk_to_score))
    hz_mean = hz.groupby("time")["h_score"].mean()
    axes[1, 1].plot(hz_mean.index, hz_mean.values)
    axes[1, 1].set_title("Horizon state transitions")

    # 6) early transition pressure profile
    pressure = results.groupby("time")["transition_pressure"].mean()
    axes[1, 2].plot(pressure.index, pressure.values)
    axes[1, 2].set_title("Transition pressure over time")

    for ax in axes.flatten():
        ax.grid(alpha=0.2)

    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=140)
    print(f"Saved plot: {args.output.resolve()}")


if __name__ == "__main__":
    main()
