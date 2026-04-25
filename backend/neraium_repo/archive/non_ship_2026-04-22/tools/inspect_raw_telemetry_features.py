from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json

from neraium_core.adapters.raw_telemetry_adapter import convert_raw_telemetry_to_structural_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect extracted rich telemetry features.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    rows = convert_raw_telemetry_to_structural_rows(args.input)
    print(f"rows={len(rows)}")
    for row in rows[: max(1, args.limit)]:
        keys = [k for k in row.keys() if k.startswith("sensor__")][:12]
        view = {"unit": row.get("unit"), "cycle": row.get("cycle"), **{k: row[k] for k in keys}}
        print(json.dumps(view, indent=2))


if __name__ == "__main__":
    main()
