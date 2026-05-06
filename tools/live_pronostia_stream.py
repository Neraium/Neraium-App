#!/usr/bin/env python3
"""Live-like PRONOSTIA/FEMTO telemetry packet generator.

The generator emits one telemetry packet at a time. It uses cached PRONOSTIA
windows when available and applies a gradual live drift after cycle 90 so the
ingestion endpoint receives a plausible streaming transition.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator

import numpy as np


ASSET_ID = "FEMTO-BEARING-01"
RAW_SIGNAL_CACHE = Path.home() / ".rul-datasets/FEMTOBearingDataSet/run_1_1_features.npy"


def _finite_values(window: object) -> np.ndarray:
    values = np.asarray(window, dtype=float).reshape(-1)
    return values[np.isfinite(values)]


def _features_from_values(values: np.ndarray) -> Dict[str, float]:
    if values.size == 0:
        return {
            "rms": 0.0,
            "peak": 0.0,
            "kurtosis": 0.0,
            "skewness": 0.0,
            "crest_factor": 0.0,
        }

    mean = float(np.mean(values))
    std = float(np.std(values))
    rms = float(np.sqrt(np.mean(values ** 2)))
    peak = float(np.max(np.abs(values)))
    centered = values - mean
    if std > 1e-12:
        normalized = centered / std
        skewness = float(np.mean(normalized ** 3))
        kurtosis = float(np.mean(normalized ** 4))
    else:
        skewness = 0.0
        kurtosis = 0.0
    crest = float(peak / rms) if rms > 1e-12 else 0.0
    return {
        "rms": rms,
        "peak": peak,
        "kurtosis": kurtosis,
        "skewness": skewness,
        "crest_factor": crest,
    }


def _fallback_features(cycle: int) -> Dict[str, float]:
    phase = cycle / 8.0
    return {
        "rms": 0.52 + 0.01 * math.sin(phase),
        "peak": 1.42 + 0.03 * math.cos(phase / 2.0),
        "kurtosis": 3.05 + 0.05 * math.sin(phase / 3.0),
        "skewness": 0.03 * math.cos(phase / 4.0),
        "crest_factor": 2.70 + 0.04 * math.sin(phase / 5.0),
    }


def _stable_feature_series(seed_rows: list[Dict[str, float]], max_cycles: int) -> list[Dict[str, float]]:
    keys = ("rms", "peak", "kurtosis", "skewness", "crest_factor")
    medians = {
        key: float(np.median([row[key] for row in seed_rows]))
        for key in keys
    }
    scales = {
        key: max(float(np.std([row[key] for row in seed_rows])), abs(medians[key]) * 0.01, 1e-6)
        for key in keys
    }
    rows: list[Dict[str, float]] = []
    for cycle in range(1, max_cycles + 1):
        phase = cycle / 7.0
        rows.append({
            "rms": medians["rms"] + 0.02 * scales["rms"] * math.sin(phase),
            "peak": medians["peak"] + 0.02 * scales["peak"] * math.cos(phase / 1.7),
            "kurtosis": medians["kurtosis"] + 0.02 * scales["kurtosis"] * math.sin(phase / 2.1),
            "skewness": medians["skewness"] + 0.02 * scales["skewness"] * math.cos(phase / 2.9),
            "crest_factor": medians["crest_factor"] + 0.02 * scales["crest_factor"] * math.sin(phase / 3.3),
        })
    return rows


def _load_pronostia_features(max_cycles: int) -> list[Dict[str, float]]:
    if not RAW_SIGNAL_CACHE.exists():
        return [_fallback_features(cycle) for cycle in range(1, max_cycles + 1)]

    run = np.load(RAW_SIGNAL_CACHE, mmap_mode="r")
    seed_rows = min(80, int(run.shape[0]))
    source = [
        _features_from_values(_finite_values(run[index]))
        for index in range(seed_rows)
    ]
    return _stable_feature_series(source, max_cycles)


def _inject_live_drift(features: Dict[str, float], cycle: int) -> Dict[str, float]:
    drift = max(0.0, cycle - 90) / 33.0
    drift = min(drift, 1.0)
    if drift <= 0:
        return {key: round(float(value), 6) for key, value in features.items()}

    # Keep feature ranges plausible while changing their relationship over time.
    adjusted = dict(features)
    adjusted["rms"] = adjusted["rms"] * (1.0 + 0.22 * drift)
    adjusted["peak"] = adjusted["peak"] * (1.0 + 0.30 * drift)
    adjusted["kurtosis"] = adjusted["kurtosis"] + 0.85 * drift
    adjusted["skewness"] = adjusted["skewness"] + 0.35 * drift
    adjusted["crest_factor"] = adjusted["crest_factor"] * (1.0 + 0.14 * drift)
    return {key: round(float(value), 6) for key, value in adjusted.items()}


def generate_packets(max_cycles: int = 150) -> Iterator[Dict[str, object]]:
    feature_rows = _load_pronostia_features(max_cycles)
    for cycle in range(1, max_cycles + 1):
        source = feature_rows[min(cycle - 1, len(feature_rows) - 1)]
        yield {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_id": ASSET_ID,
            "cycle": cycle,
            "signals": _inject_live_drift(source, cycle),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit live-like PRONOSTIA telemetry packets as JSON lines.")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=150)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for packet in generate_packets(args.max_cycles):
        print(json.dumps(packet), flush=True)
        time.sleep(max(args.interval, 0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
