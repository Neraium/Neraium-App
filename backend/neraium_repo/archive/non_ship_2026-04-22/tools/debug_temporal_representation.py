from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from diagnostics.representation_debug import build_debug_table


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dump temporal representation internals for selected entities.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--entities", nargs="+", required=True)
    p.add_argument("--entity-col", default=None)
    p.add_argument("--time-col", default=None)
    p.add_argument("--features", nargs="*", default=None)
    p.add_argument("--output", type=Path, default=Path("temporal_representation_debug.csv"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    table = build_debug_table(
        args.input,
        entities=args.entities,
        entity_col=args.entity_col,
        time_col=args.time_col,
        features=args.features,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(f"Wrote debug output: {args.output.resolve()} ({len(table)} rows)")


if __name__ == "__main__":
    main()
