from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from diagnostics.context_leakage import run_context_leakage_check


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check for static-context leakage in temporal separability.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--entity-col", default=None)
    p.add_argument("--time-col", default=None)
    p.add_argument("--mode", default="combined")
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    report = run_context_leakage_check(
        args.input,
        entity_col=args.entity_col,
        time_col=args.time_col,
        mode=args.mode,
    )
    text = json.dumps(report, indent=2)
    print(text)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Saved report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
