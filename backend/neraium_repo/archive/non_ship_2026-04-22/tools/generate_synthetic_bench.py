from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from synthetic.temporal_bench import generate_temporal_bench


def main() -> None:
    p = argparse.ArgumentParser(description="Generate domain-general synthetic temporal robustness benchmark.")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    df = generate_temporal_bench(seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {args.output} rows={len(df)} scenarios={df['scenario'].nunique()}")


if __name__ == "__main__":
    main()
