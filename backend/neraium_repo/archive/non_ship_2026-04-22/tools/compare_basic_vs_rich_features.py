from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import csv

import numpy as np

from neraium_core.adapters.raw_telemetry_adapter import load_raw_telemetry_windows
from neraium_core.features.window_feature_extractor import extract_window_features


def _basic(window: np.ndarray) -> dict[str, float]:
    x = np.asarray(window, dtype=float)
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
        "energy": float(np.mean(np.square(x))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare basic aggregate vs rich feature extraction.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    windows = load_raw_telemetry_windows(args.input)
    rows = []
    for w in windows:
        basic = _basic(w.values)
        rich = extract_window_features(w.values, channel_names=w.channel_names).flattened
        rows.append(
            {
                "unit": w.unit,
                "cycle": w.cycle,
                "basic_feature_count": len(basic),
                "rich_feature_count": len(rich),
                "basic_energy": basic["energy"],
                "rich_energy_proxy": float(np.mean([v for k, v in rich.items() if "rolling_energy" in k][:1] or [0.0])),
                "rich_spectral_entropy": float(np.mean([v for k, v in rich.items() if "spectral_entropy" in k][:1] or [0.0])),
            }
        )

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["unit", "cycle"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"windows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
