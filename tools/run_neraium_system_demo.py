#!/usr/bin/env python3
"""Proof runner for the hazard-centered NeraiumEngine."""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.neraium_engine import NeraiumEngine  # noqa: E402


ASSET_ID = "CNC-MILL-01"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical hazard-centered Neraium engine demo.")
    parser.add_argument("--interval", type=float, default=0.0)
    parser.add_argument("--max-cycles", type=int, default=150)
    parser.add_argument("--show-every", type=int, default=5)
    return parser.parse_args()


def packet_stream(max_cycles: int) -> Iterator[Dict[str, object]]:
    for cycle in range(1, max_cycles + 1):
        phase = cycle / 9.0
        drift = min(max(0.0, cycle - 90) / 33.0, 1.0)
        yield {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_id": ASSET_ID,
            "cycle": cycle,
            "signals": {
                "spindle_vibration": round(0.50 + 0.010 * math.sin(phase) + 0.28 * drift, 6),
                "spindle_load": round(0.62 + 0.010 * math.cos(phase / 1.6) + 0.20 * drift, 6),
                "bearing_temperature": round(0.42 + 0.006 * math.sin(phase / 2.0) + 0.08 * drift, 6),
                "acoustic_kurtosis": round(3.02 + 0.030 * math.cos(phase / 2.4) + 0.92 * drift, 6),
                "motor_current": round(0.57 + 0.008 * math.sin(phase / 3.0) + 0.10 * drift, 6),
            },
        }


def print_frame(frame: Dict[str, object], previous_state: str) -> None:
    drivers = frame["drivers"]
    audit = frame["audit"]
    if frame["state"] != previous_state:
        print(f"[EVENT] {previous_state} -> {frame['state']} cycle={frame['cycle']}")
    print(
        f"[HAZARD] cycle={frame['cycle']} asset={frame['asset_id']} "
        f"score={frame['hazard_score']:.3f} rate={frame['hazard_rate']:.4f} "
        f"state={frame['state']} confidence={frame['confidence']:.2f}"
    )
    print(
        "[DRIVERS] "
        f"drift={drivers['structural_drift']:.3f} "
        f"trajectory={drivers['trajectory_strength']:.3f} "
        f"relational={drivers['relational_instability']:.3f}"
    )
    print(f"[TIME] time_to_threshold={frame['time_to_threshold']}")
    print(f"[AUDIT] future_data_used={str(audit['future_data_used']).lower()} window={audit['data_window_used']}")
    print()


def main() -> int:
    args = parse_args()
    engine = NeraiumEngine()
    previous_state = "STABLE"

    print("NeraiumEngine demo: structural departure -> trajectory confirmation -> hazard -> operator state.")
    print("Forward-only: each output is produced by one call to update(packet).")
    print()

    for packet in packet_stream(args.max_cycles):
        frame = engine.update(packet)
        cycle = int(frame["cycle"])
        should_show = frame["state"] != previous_state or cycle == 1 or cycle % max(args.show_every, 1) == 0
        if should_show:
            print_frame(frame, previous_state)
        previous_state = str(frame["state"])
        time.sleep(max(args.interval, 0.0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
