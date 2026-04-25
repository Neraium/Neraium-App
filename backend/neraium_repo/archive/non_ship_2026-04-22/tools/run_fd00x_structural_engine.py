from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from neraium_core.alignment import StructuralEngine

DATA_DIR = Path("/content/data")  # change to your folder
SUPPORTED_DATASETS = ("FD001", "FD002", "FD003", "FD004")
FD00X_COLUMNS = ["unit", "cycle"] + [f"os{i}" for i in range(1, 4)] + [f"s{i}" for i in range(1, 22)]
TETRA_VERTICES = {
    "STRUCTURAL": (1.0, 1.0, 1.0),
    "RELATIONAL": (1.0, -1.0, -1.0),
    "TRANSITION": (-1.0, 1.0, -1.0),
    "TEMPORAL": (-1.0, -1.0, 1.0),
}
TETRA_EDGES = [
    ("STRUCTURAL", "RELATIONAL"),
    ("STRUCTURAL", "TRANSITION"),
    ("STRUCTURAL", "TEMPORAL"),
    ("RELATIONAL", "TRANSITION"),
    ("RELATIONAL", "TEMPORAL"),
    ("TRANSITION", "TEMPORAL"),
]


def _plot_tetra_trajectory(trajectory: list[list[float]], dataset: str, unit: int) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping tetrahedral trajectory plot")
        return

    if not trajectory:
        print(f"no tetrahedral trajectory points found for unit {unit}")
        return

    xs = [p[0] for p in trajectory]
    ys = [p[1] for p in trajectory]
    zs = [p[2] for p in trajectory]

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")

    progression = [i / max(len(xs) - 1, 1) for i in range(len(xs))]
    colors = plt.cm.viridis(progression)

    for i in range(1, len(xs)):
        recency = (i - 1) / max(len(xs) - 2, 1)
        ax.plot(
            [xs[i - 1], xs[i]],
            [ys[i - 1], ys[i]],
            [zs[i - 1], zs[i]],
            color=colors[i],
            linewidth=1.0 + 2.0 * recency,
            alpha=0.25 + 0.7 * recency,
        )

    ax.scatter(xs, ys, zs, c=progression, cmap="viridis", s=12, label="trajectory")
    ax.scatter(xs[0], ys[0], zs[0], color="tab:green", s=70, marker="o", label="start")
    ax.scatter(xs[-1], ys[-1], zs[-1], color="tab:red", s=70, marker="^", label="end")

    vx = [coord[0] for coord in TETRA_VERTICES.values()]
    vy = [coord[1] for coord in TETRA_VERTICES.values()]
    vz = [coord[2] for coord in TETRA_VERTICES.values()]
    ax.scatter(vx, vy, vz, color="black", s=30, alpha=0.8, label="tetra vertices")

    for a, b in TETRA_EDGES:
        xa, ya, za = TETRA_VERTICES[a]
        xb, yb, zb = TETRA_VERTICES[b]
        ax.plot([xa, xb], [ya, yb], [za, zb], color="gray", alpha=0.25, linewidth=1.0)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"{dataset} tetrahedral trajectory (unit {unit})")
    ax.legend(loc="best")

    output_path = Path(f"{dataset}_tetra_unit_{unit}.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close(fig)
    print("saved", output_path)


def _plot_structural_metric(out_df: pd.DataFrame, dataset: str, unit: int) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping structural metric plot")
        return

    unit_df = out_df[out_df["unit"] == unit].sort_values("cycle").reset_index(drop=True)
    if unit_df.empty:
        print(f"no rows found for unit {unit}; skipping structural metric plot")
        return

    metric_column = (
        "structural_drift_score_smoothed"
        if "structural_drift_score_smoothed" in unit_df.columns
        else "structural_drift_score"
    )
    if metric_column not in unit_df.columns:
        print("no structural drift metric available in output; skipping plot")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(unit_df["cycle"], unit_df[metric_column], linewidth=1.8, color="tab:blue")
    ax.set_xlabel("Cycle")
    ax.set_ylabel(metric_column)
    ax.set_title(f"{dataset} structural metric over cycles (unit {unit})")
    ax.grid(alpha=0.25)

    output_path = Path(f"{dataset}_structural_metric_unit_{unit}.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close(fig)
    print("saved", output_path)


def _resolve_input_path(dataset: str, user_input: str | None) -> Path:
    if user_input:
        path = Path(user_input).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"input path does not exist: {path}")
        return path
    return DATA_DIR / f"test_{dataset}.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FD00x structural engine")
    parser.add_argument("--dataset", choices=SUPPORTED_DATASETS, default="FD004", help="CMAPSS dataset id")
    parser.add_argument("--input", default=None, help="Path to a test_FD00x.txt file (optional)")
    parser.add_argument("--plot-tetra", action="store_true", help="Plot tetrahedral trajectory for selected unit")
    parser.add_argument("--unit", type=int, default=1, help="Unit id to collect tetrahedral trajectory")
    args = parser.parse_args()

    dataset = str(args.dataset)
    file_path = _resolve_input_path(dataset, args.input)

    df = pd.read_csv(file_path, sep=r"\s+", header=None)
    expected_columns = len(FD00X_COLUMNS)
    actual_columns = df.shape[1]
    if actual_columns != expected_columns:
        extra_columns = df.iloc[:, expected_columns:] if actual_columns > expected_columns else None
        trailing_empty_columns = bool(
            extra_columns is not None and extra_columns.isna().all().all()
        )
        if actual_columns > expected_columns and trailing_empty_columns:
            df = df.iloc[:, :expected_columns].copy()
        else:
            raise ValueError(
                "Unexpected FD00x column count in input "
                f"{file_path}: expected {expected_columns}, found {actual_columns}. "
                "Refusing to remap columns to avoid silent feature shifts."
            )
    df.columns = FD00X_COLUMNS

    engine = StructuralEngine(
        baseline_window=50,
        recent_window=12,
    )
    results = []
    tetra_trajectory: list[list[float]] = []
    global_t = 0.0

    for _, row in df.iterrows():
        frame = {
            "timestamp": global_t,
            "site_id": "nasa_cmapss",
            "asset_id": f"engine_{int(row['unit'])}",
            "sensor_values": {
                f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)
            }
            | {
                f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)
            },
        }

        out = engine.process_frame(frame)
        out["unit"] = int(row["unit"])
        out["cycle"] = int(row["cycle"])
        results.append(out)

        if args.plot_tetra and int(row["unit"]) == args.unit:
            tetra_state = out.get("tetrahedral_state") if isinstance(out, dict) else None
            position = tetra_state.get("position") if isinstance(tetra_state, dict) else None
            if isinstance(position, (list, tuple)) and len(position) == 3:
                tetra_trajectory.append([float(position[0]), float(position[1]), float(position[2])])

        global_t += 1.0

    out_df = pd.DataFrame(results)
    out_df.to_csv(f"{dataset}_results.csv", index=False)
    unit_df = out_df[out_df["unit"] == args.unit].sort_values("cycle").reset_index(drop=True)
    unit_df.to_csv(f"{dataset}_unit_{args.unit}_results.csv", index=False)

    print("saved", f"{dataset}_results.csv")
    print("saved", f"{dataset}_unit_{args.unit}_results.csv")
    print(out_df.head())
    print(out_df.columns.tolist())
    _plot_structural_metric(out_df, dataset=dataset, unit=args.unit)

    if args.plot_tetra:
        _plot_tetra_trajectory(tetra_trajectory, dataset=dataset, unit=args.unit)


if __name__ == "__main__":
    main()
