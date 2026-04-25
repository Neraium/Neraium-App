from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neraium_core.adapters.raw_telemetry_adapter import convert_raw_telemetry_to_structural_rows, write_structural_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw telemetry windows into Neraium structural CSV.")
    parser.add_argument("--input", required=True, help="Input file/folder (.json/.csv/.npy/.npz).")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    args = parser.parse_args()

    rows = convert_raw_telemetry_to_structural_rows(args.input)
    write_structural_csv(rows, args.output)
    print(f"converted_windows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
