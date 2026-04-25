from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

METRICS = (
    "structural_drift_score",
    "relational_instability_score",
    "transition_pressure",
)
TIMELINE_CANDIDATE_COLUMNS = ("time", "timestamp", "cycle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare FD001 and FD004 structural metrics on matched y-axis scales."
    )
    parser.add_argument("--fd001", type=Path, required=True, help="Path to FD001 results CSV")
    parser.add_argument("--fd004", type=Path, required=True, help="Path to FD004 results CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fd001_vs_fd004_metrics.png"),
        help="Output image path",
    )
    return parser.parse_args()


def _validate_columns(df: pd.DataFrame, label: str) -> None:
    missing = [metric for metric in METRICS if metric not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{label} is missing required columns: {joined}")


def _x_values(df: pd.DataFrame) -> tuple[pd.Series, str]:
    lower_col_map = {column.lower(): column for column in df.columns}
    for candidate in TIMELINE_CANDIDATE_COLUMNS:
        if candidate in lower_col_map:
            source_col = lower_col_map[candidate]
            numeric_series = pd.to_numeric(df[source_col], errors="coerce")
            if numeric_series.notna().any():
                return numeric_series.ffill().fillna(0), source_col

            datetime_series = pd.to_datetime(df[source_col], errors="coerce")
            if datetime_series.notna().any():
                return datetime_series.ffill().bfill(), source_col
    return pd.Series(range(len(df)), index=df.index), "index"


def _y_limits(values_left: pd.Series, values_right: pd.Series) -> tuple[float, float] | None:
    merged = pd.concat([values_left, values_right], ignore_index=True)
    merged = pd.to_numeric(merged, errors="coerce").dropna()
    if merged.empty:
        return None
    ymin = float(merged.min())
    ymax = float(merged.max())
    if ymin == ymax:
        pad = abs(ymin) * 0.05 or 0.05
        return ymin - pad, ymax + pad
    pad = (ymax - ymin) * 0.05
    return ymin - pad, ymax + pad


def main() -> None:
    args = parse_args()

    fd001_df = pd.read_csv(args.fd001)
    fd004_df = pd.read_csv(args.fd004)

    _validate_columns(fd001_df, "FD001 CSV")
    _validate_columns(fd004_df, "FD004 CSV")

    x_fd001, x_fd001_label = _x_values(fd001_df)
    x_fd004, x_fd004_label = _x_values(fd004_df)

    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(14, 10), sharex=False)

    for row_idx, metric in enumerate(METRICS):
        left_ax = axes[row_idx, 0]
        right_ax = axes[row_idx, 1]

        fd001_y = pd.to_numeric(fd001_df[metric], errors="coerce")
        fd004_y = pd.to_numeric(fd004_df[metric], errors="coerce")

        left_ax.plot(x_fd001, fd001_y, color="tab:blue", linewidth=1.6)
        right_ax.plot(x_fd004, fd004_y, color="tab:orange", linewidth=1.6)

        left_ax.set_title(f"FD001 {metric}")
        right_ax.set_title(f"FD004 {metric}")

        left_ax.set_ylabel(metric)
        left_ax.set_xlabel(x_fd001_label)
        right_ax.set_xlabel(x_fd004_label)

        limits = _y_limits(fd001_y, fd004_y)
        if limits is not None:
            left_ax.set_ylim(*limits)
            right_ax.set_ylim(*limits)

        left_ax.grid(alpha=0.25)
        right_ax.grid(alpha=0.25)

    fig.suptitle("FD001 vs FD004 Metric Comparison", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f"Saved comparison plot: {args.output.resolve()}")


if __name__ == "__main__":
    main()
