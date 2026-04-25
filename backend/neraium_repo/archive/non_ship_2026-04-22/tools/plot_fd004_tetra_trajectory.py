from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neraium_core.alignment import StructuralEngine


FD004_COLUMNS = ["unit", "cycle", "os1", "os2", "os3"] + [f"s{i}" for i in range(1, 22)]
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


def _resolve_input_path(input_path: str | None) -> Path:
    if input_path:
        p = Path(input_path).expanduser()
        if p.exists():
            return p
        raise FileNotFoundError(f"Input path does not exist: {p}")

    candidates = [
        Path("test_FD004.txt"),
        Path("data/test_FD004.txt"),
        Path("/content/data/test_FD004.txt"),
        Path.home() / "Desktop" / "CMAPSSData" / "test_FD004.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    tried = "\n  - ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Could not find test_FD004.txt. Tried:\n  - {tried}")


def _load_fd004(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None)
    df = df.iloc[:, :26].copy()
    df.columns = FD004_COLUMNS
    return df


def _extract_unit_trajectory(df: pd.DataFrame, unit_id: int) -> list[list[float]]:
    unit_df = df[df["unit"] == unit_id].sort_values("cycle").reset_index(drop=True)
    if unit_df.empty:
        raise ValueError(f"Unit {unit_id} was not found in the input data")

    engine = StructuralEngine(baseline_window=50, recent_window=12)
    trajectory: list[list[float]] = []

    for _, row in unit_df.iterrows():
        sensor_values = {f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)}
        sensor_values.update({f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)})

        result = engine.process_frame(
            {
                "timestamp": float(row["cycle"]),
                "site_id": "nasa_cmapss",
                "asset_id": f"FD004_unit_{unit_id}",
                "sensor_values": sensor_values,
            }
        )

        if not (isinstance(result, dict) and bool(result.get("engine_ready", False))):
            # StructuralEngine emits a deterministic warmup tetrahedral position
            # ([0, 0, 0]) before baseline/recent windows are ready.
            # Skip those placeholders so the plotted path reflects only physical
            # post-warmup trajectory points.
            continue

        tetra_state = result.get("tetrahedral_state")
        position = tetra_state.get("position") if isinstance(tetra_state, dict) else None
        if isinstance(position, (list, tuple)) and len(position) == 3:
            trajectory.append([float(position[0]), float(position[1]), float(position[2])])

    return trajectory


def _plot_trajectory(trajectory: list[list[float]], unit_id: int, output_path: Path) -> None:
    if not trajectory:
        raise RuntimeError("No tetrahedral positions found for selected unit")

    xs = [p[0] for p in trajectory]
    ys = [p[1] for p in trajectory]
    zs = [p[2] for p in trajectory]

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot(xs, ys, zs, color="tab:blue", linewidth=2.0, label="trajectory")
    ax.scatter(xs[0], ys[0], zs[0], color="tab:green", s=70, marker="o", label="start")
    ax.scatter(xs[-1], ys[-1], zs[-1], color="tab:red", s=70, marker="^", label="end")

    vx = [coord[0] for coord in TETRA_VERTICES.values()]
    vy = [coord[1] for coord in TETRA_VERTICES.values()]
    vz = [coord[2] for coord in TETRA_VERTICES.values()]
    ax.scatter(vx, vy, vz, color="black", s=30, alpha=0.8, label="tetra vertices")

    for name, (x, y, z) in TETRA_VERTICES.items():
        ax.text(x, y, z, f" {name}", fontsize=8)

    for a, b in TETRA_EDGES:
        xa, ya, za = TETRA_VERTICES[a]
        xb, yb, zb = TETRA_VERTICES[b]
        ax.plot([xa, xb], [ya, yb], [za, zb], color="gray", alpha=0.25, linewidth=1.0)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"FD004 tetrahedral trajectory (unit {unit_id})")
    ax.legend(loc="best")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot FD004 tetrahedral trajectory for a selected unit.")
    parser.add_argument("--input", default=None, help="Path to test_FD004.txt (optional)")
    parser.add_argument("--unit", type=int, default=1, help="FD004 unit id")
    parser.add_argument("--output", default=None, help="Output PNG path")
    args = parser.parse_args()

    input_path = _resolve_input_path(args.input)
    output_path = Path(args.output) if args.output else Path(f"fd004_tetra_unit_{args.unit}.png")

    df = _load_fd004(input_path)
    trajectory = _extract_unit_trajectory(df, args.unit)
    _plot_trajectory(trajectory, args.unit, output_path)

    print(f"Loaded: {input_path}")
    print(f"Unit: {args.unit}")
    print(f"Trajectory points plotted: {len(trajectory)}")
    print(f"Saved plot: {output_path}")


if __name__ == "__main__":
    main()
