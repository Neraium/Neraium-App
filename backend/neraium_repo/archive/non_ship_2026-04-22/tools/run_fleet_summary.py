from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from neraium_core.alignment import StructuralEngine
from neraium_core.structural_upgrade import fleet_comparison_summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    args = p.parse_args()

    df = pd.read_csv(args.input)
    feature_cols = [c for c in df.columns if c not in {"entity_id", "time", "scenario"}]

    entity_results: dict[str, list[dict]] = {}
    for entity, sub in df.groupby("entity_id"):
        engine = StructuralEngine(baseline_window=24, recent_window=12)
        rows = sub.sort_values("time").to_dict(orient="records")
        outputs = []
        for row in rows:
            outputs.append(
                engine.process_frame(
                    {
                        "timestamp": float(row["time"]),
                        "site_id": "fleet",
                        "asset_id": str(entity),
                        "sensor_values": {c: float(row[c]) for c in feature_cols},
                    }
                )
            )
        entity_results[str(entity)] = outputs

    print(json.dumps({"fleet_comparison": fleet_comparison_summary(entity_results)}, indent=2))


if __name__ == "__main__":
    main()
