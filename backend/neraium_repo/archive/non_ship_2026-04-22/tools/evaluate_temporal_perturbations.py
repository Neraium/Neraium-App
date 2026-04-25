from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from neraium_core.alignment import StructuralEngine
from neraium_core.robustness.temporal_perturbation import perturb_timestamps, temporal_shift_metrics


MODES = [
    "timestamp_jitter",
    "timestamp_compression",
    "timestamp_expansion",
    "bursty_intervals",
    "gap_insertion",
    "local_reordering",
    "sampling_irregularity",
]


def _run(rows: list[dict[str, Any]], ts_override: list[float] | None = None) -> dict[str, Any]:
    feature_cols = [c for c in rows[0].keys() if c not in {"entity_id", "time", "scenario"}]
    engine = StructuralEngine(baseline_window=24, recent_window=12)
    out = {}
    for i, row in enumerate(rows):
        ts = float(ts_override[i]) if ts_override is not None else float(row["time"])
        frame = {
            "timestamp": ts,
            "site_id": "eval-site",
            "asset_id": str(row["entity_id"]),
            "sensor_values": {c: float(row[c]) for c in feature_cols},
        }
        out = engine.process_frame(frame)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()

    df = pd.read_csv(args.input)
    rows = df.to_dict(orient="records")
    base = _run(rows)
    base_ts = [float(r["time"]) for r in rows]

    report = {}
    for mode in MODES:
        pert_ts = perturb_timestamps(base_ts, mode=mode)
        perturbed = _run(rows, ts_override=pert_ts.tolist())
        report[mode] = temporal_shift_metrics(base, perturbed)

    text = json.dumps({"base_state": base.get("state"), "perturbations": report}, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
