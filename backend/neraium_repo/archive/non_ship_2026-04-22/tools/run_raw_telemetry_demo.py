from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import csv

from neraium_core.adapters.raw_telemetry_adapter import load_raw_telemetry_windows, raw_slices_to_structural_frames
from neraium_core.alignment import StructuralEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neraium engine on raw telemetry windows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    windows = load_raw_telemetry_windows(args.input)
    frames = raw_slices_to_structural_frames(windows, site_id="raw-telemetry")
    engine = StructuralEngine(baseline_window=24, recent_window=8)
    results = []
    for frame in frames:
        meta = frame.get("raw_window_metadata", {})
        res = engine.process_frame(frame)
        results.append(
            {
                "unit": meta.get("unit", frame.get("asset_id")),
                "cycle": meta.get("cycle", 0),
                "state": res.get("state"),
                "latest_instability": res.get("latest_instability", 0.0),
                "transition_pressure": res.get("transition_pressure", 0.0),
                "horizon_category": (res.get("experimental_analytics", {}).get("horizon_analysis", {}) or {}).get("horizon_category"),
                "signal_degradation_state": (res.get("signal_degradation", {}) or {}).get("signal_degradation_state"),
            }
        )

    headers = list(results[0].keys()) if results else ["unit", "cycle", "state"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"processed_windows={len(results)} output={args.output}")


if __name__ == "__main__":
    main()
