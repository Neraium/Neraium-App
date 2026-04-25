#!/usr/bin/env python3
"""
Near-real-time demo: one observation at a time with incremental window buffers.

Examples::

  python tools/run_realtime_demo.py --mode synthetic --steps 200
  python tools/run_realtime_demo.py --mode incremental --steps 120
  NERAIUM_PROFILE_INCREMENTAL=1 python tools/run_realtime_demo.py --mode synthetic --steps 80
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from neraium_core.realtime import IncrementalUpdateEngine, process_one


def _synthetic_frames(steps: int, *, seed: int, sensors: int) -> list[dict]:
    rng = random.Random(seed)
    names = [f"s{i}" for i in range(1, sensors + 1)]
    out: list[dict] = []
    for t in range(steps):
        phase = 0.02 * t
        vals = {n: rng.gauss(0.0, 1.0) + 0.15 * (i % 3) * phase for i, n in enumerate(names)}
        out.append(
            {
                "timestamp": str(t),
                "site_id": "demo",
                "asset_id": "unit_1",
                "sensor_values": vals,
            }
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Neraium incremental realtime demo")
    p.add_argument("--mode", choices=("incremental", "synthetic", "batch"), default="incremental")
    p.add_argument("--steps", type=int, default=150)
    p.add_argument("--sensors", type=int, default=8)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--baseline-window", type=int, default=50)
    p.add_argument("--recent-window", type=int, default=12)
    args = p.parse_args()

    frames = _synthetic_frames(args.steps, seed=args.seed, sensors=args.sensors)

    eng = IncrementalUpdateEngine(
        "unit_1",
        baseline_window=args.baseline_window,
        recent_window=args.recent_window,
    )

    t0 = time.perf_counter()
    last: dict | None = None
    for fr in frames:
        last = process_one(eng, fr, attach_timing=os.environ.get("NERAIUM_PROFILE_INCREMENTAL") == "1")
    elapsed = time.perf_counter() - t0

    print(f"processed {len(frames)} frames in {elapsed:.4f}s ({len(frames) / max(elapsed, 1e-9):.1f} fps)")
    if last:
        print(
            "last: state=%s latest_instability=%s interpreted_state=%s"
            % (
                last.get("state"),
                last.get("latest_instability"),
                last.get("interpreted_state"),
            )
        )
        inc = last.get("_incremental_timing")
        if inc:
            print("timing:", inc)


if __name__ == "__main__":
    main()
