from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Print signal degradation trend from demo output CSV.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    with open(args.input, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"rows={len(rows)}")
    for row in rows[:20]:
        print(
            f"unit={row.get('unit')} cycle={row.get('cycle')} "
            f"state={row.get('state')} transition_pressure={row.get('transition_pressure')} "
            f"signal_degradation_state={row.get('signal_degradation_state')}"
        )


if __name__ == "__main__":
    main()
