from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.representation_compare import (
    build_temporal_representation,
    compare_summaries,
    load_dataset,
    run_engine_over_representation,
    summarize_run,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare two temporal representations side by side.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--config-a", default="raw")
    p.add_argument("--config-b", default="combined")
    p.add_argument("--entity-col", default=None)
    p.add_argument("--time-col", default=None)
    p.add_argument("--details-output", type=Path, default=Path("representation_compare_details.csv"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df, spec = load_dataset(args.input, entity_col=args.entity_col, time_col=args.time_col)

    rep_a = build_temporal_representation(df, spec, mode=args.config_a)
    run_a = run_engine_over_representation(rep_a, spec)
    summary_a = summarize_run(rep_a, run_a, spec)

    rep_b = build_temporal_representation(df, spec, mode=args.config_b)
    run_b = run_engine_over_representation(rep_b, spec)
    summary_b = summarize_run(rep_b, run_b, spec)

    table = compare_summaries(summary_a, summary_b)
    print("\nRepresentation comparison")
    print(table.to_string(index=False))

    details = pd.concat(
        [
            run_a.assign(config=args.config_a),
            run_b.assign(config=args.config_b),
        ],
        ignore_index=True,
    )
    args.details_output.parent.mkdir(parents=True, exist_ok=True)
    details.to_csv(args.details_output, index=False)
    print(f"\nDetailed run output written to: {args.details_output.resolve()}")


if __name__ == "__main__":
    main()
