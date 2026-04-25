from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from neraium_core.alignment import StructuralEngine


MODES = ["raw_only", "dynamic_only", "directional_only", "temporal_only", "combined"]


def _run(df: pd.DataFrame, mode: str) -> dict:
    feature_cols = [c for c in df.columns if c not in {"entity_id", "time", "scenario"}]
    engine = StructuralEngine(representation_mode=mode, baseline_window=24, recent_window=12)
    out = {}
    for row in df.to_dict(orient="records"):
        out = engine.process_frame(
            {
                "timestamp": float(row["time"]),
                "site_id": "feature-mode",
                "asset_id": str(row["entity_id"]),
                "sensor_values": {c: float(row[c]) for c in feature_cols},
            }
        )
    return {
        "state": out.get("state"),
        "drift": out.get("latest_drift"),
        "prototype": (out.get("path_prototypes", {}) or {}).get("dominant_prototype"),
        "stability": (out.get("stability", {}) or {}).get("overall_structural_stability"),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    args = p.parse_args()
    df = pd.read_csv(args.input)
    print(json.dumps({m: _run(df, m) for m in MODES}, indent=2))


if __name__ == "__main__":
    main()
