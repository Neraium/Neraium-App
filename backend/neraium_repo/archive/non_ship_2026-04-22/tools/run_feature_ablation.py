from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.representation_compare import (
    build_temporal_representation,
    load_dataset,
    run_engine_over_representation,
    summarize_run,
)


MODES = ["raw_only", "residual_only", "delta_only", "drift_only", "slope_only", "combined"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run feature-group ablation for temporal representation.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--entity-col", default=None)
    p.add_argument("--time-col", default=None)
    p.add_argument("--output", type=Path, default=Path("feature_ablation_results.csv"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df, spec = load_dataset(args.input, entity_col=args.entity_col, time_col=args.time_col)

    rows: list[dict[str, float | str | None]] = []
    for mode in MODES:
        rep = build_temporal_representation(df, spec, mode=mode)
        run = run_engine_over_representation(rep, spec)
        summary = summarize_run(rep, run, spec)
        rows.append({"mode": mode, **summary})

    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(f"\nAblation table written to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
