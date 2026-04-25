#!/usr/bin/env python3
"""Compare wall time with NERAIUM_INCREMENTAL=1 vs 0 (same StructuralEngine semantics)."""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from neraium_core.alignment import StructuralEngine


def _frames(n: int, sensors: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    names = [f"s{i}" for i in range(1, sensors + 1)]
    out = []
    for t in range(n):
        vals = {name: rng.gauss(0.0, 1.0) for name in names}
        out.append(
            {
                "timestamp": str(t),
                "site_id": "bench",
                "asset_id": "a1",
                "sensor_values": vals,
            }
        )
    return out


def run_bench(*, incremental: bool, frames: list[dict]) -> float:
    os.environ["NERAIUM_INCREMENTAL"] = "1" if incremental else "0"
    eng = StructuralEngine(baseline_window=50, recent_window=12)
    t0 = time.perf_counter()
    for f in frames:
        eng.process_frame(f)
    return time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--sensors", type=int, default=12)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument(
        "--light-analytics",
        action="store_true",
        help="Set NERAIUM_CAUSAL_INTELLIGENCE=0 to emphasize window/geometry vs causal cost.",
    )
    args = ap.parse_args()
    if args.light_analytics:
        os.environ["NERAIUM_CAUSAL_INTELLIGENCE"] = "0"
    frames = _frames(args.frames, args.sensors, args.seed)
    t_on = run_bench(incremental=True, frames=frames)
    t_off = run_bench(incremental=False, frames=frames)
    print(f"frames={args.frames} sensors={args.sensors}")
    print(f"NERAIUM_INCREMENTAL=1: {t_on:.4f}s ({args.frames / t_on:.1f} fps)")
    print(f"NERAIUM_INCREMENTAL=0: {t_off:.4f}s ({args.frames / t_off:.1f} fps)")
    if t_off > 0:
        print(f"speedup vs batch scan: {t_off / max(t_on, 1e-9):.2f}x")


if __name__ == "__main__":
    main()
