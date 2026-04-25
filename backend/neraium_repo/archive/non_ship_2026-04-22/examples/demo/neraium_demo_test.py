# neraium_demo_test.py
# Single-file demo test harness for the bundled SII core.
# Run with: python neraium_demo_test.py
# Requires: neraium_intelligence_core.py in the same directory (or on PYTHONPATH).

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict
from typing import Callable

# Ensure script directory is on path so neraium_intelligence_core can be imported
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

try:
    import numpy as np
    import requests
except Exception:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "requests"])
    import numpy as np
    import requests

from neraium_intelligence_core import StructuralEngine

# ---------------------------------------------------------------------------
# Config and API
# ---------------------------------------------------------------------------

# GAL-2 API: set GAL2_API_KEY in environment (never commit the key).
API_KEY = os.getenv("GAL2_API_KEY")
GAL2_TIME_URL = os.getenv("GAL2_TIME_URL", "https://api-v2.gal-2.com/time")

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

TIME_STEPS = 120
NODES = ["A", "B", "C", "D"]


def get_gal2_time() -> float:
    if not API_KEY:
        return time.time()
    try:
        r = requests.get(
            GAL2_TIME_URL,
            headers={"x-api-key": API_KEY},
            timeout=3,
        )
        r.raise_for_status()
        data = r.json()
        return float(data.get("gal2_time", time.time()))
    except Exception:
        return time.time()


# ---------------------------------------------------------------------------
# Scenario helpers (for richer analysis; core provides normalize_window, etc.)
# ---------------------------------------------------------------------------


def safe_corrcoef(x: np.ndarray) -> np.ndarray:
    if x.ndim != 2 or x.shape[0] < 2:
        cols = x.shape[1] if x.ndim == 2 else 1
        return np.eye(max(1, cols))
    c = np.corrcoef(x, rowvar=False)
    c = np.nan_to_num(c, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(c, 1.0)
    return c


def structural_drift_local(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        n = min(a.shape[0], b.shape[0])
        a = a[:n, :n]
        b = b[:n, :n]
    return float(np.linalg.norm(a - b, ord="fro"))


def normalize_window_local(window: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    means = np.nanmean(window, axis=0)
    means = np.nan_to_num(means, nan=0.0)
    std = np.nanstd(window, axis=0)
    std = np.nan_to_num(std, nan=0.0)
    safe_std = np.where(std <= 1e-12, 1.0, std)
    z = (window - means) / safe_std
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    return z, means, std


def early_warning_metrics(window: np.ndarray) -> dict[str, float]:
    variance = float(np.nanmean(np.nanvar(window, axis=0)))
    lag_vals: list[float] = []
    for i in range(window.shape[1]):
        x = window[:, i]
        x = x[~np.isnan(x)]
        if len(x) < 3:
            continue
        x0, x1 = x[:-1], x[1:]
        if np.std(x0) < 1e-12 or np.std(x1) < 1e-12:
            continue
        lag_vals.append(float(np.corrcoef(x0, x1)[0, 1]))
    lag1 = float(np.mean(lag_vals)) if lag_vals else 0.0
    return {"variance": variance, "lag1_autocorrelation": lag1}


def spectral_radius(corr: np.ndarray) -> float:
    vals = np.linalg.eigvals(corr)
    return float(np.max(np.abs(vals))) if len(vals) else 0.0


def lagged_correlation_matrix(obs: np.ndarray, lag: int = 1) -> np.ndarray:
    if obs.shape[0] <= lag:
        return np.zeros((obs.shape[1], obs.shape[1]))
    x = obs[:-lag]
    y = obs[lag:]
    n = x.shape[1]
    out = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            xi = x[:, i]
            yj = y[:, j]
            mask = ~np.isnan(xi) & ~np.isnan(yj)
            xi = xi[mask]
            yj = yj[mask]
            if len(xi) < 3 or np.std(xi) < 1e-12 or np.std(yj) < 1e-12:
                out[i, j] = 0.0
            else:
                out[i, j] = float(np.corrcoef(xi, yj)[0, 1])
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def directional_divergence(obs: np.ndarray) -> float:
    lagged = lagged_correlation_matrix(obs, lag=1)
    asym = np.abs(lagged - lagged.T)
    return float(np.mean(asym)) if asym.size else 0.0


def interaction_entropy(corr: np.ndarray) -> float:
    probs = np.abs(corr.flatten())
    total = np.sum(probs)
    if total <= 1e-12:
        return 0.0
    probs = probs / total
    probs = probs[probs > 1e-12]
    return float(-np.sum(probs * np.log(probs)))


# ---------------------------------------------------------------------------
# Demo scenario signal generators
# ---------------------------------------------------------------------------


def scenario_nominal(t: int) -> dict[str, float]:
    s = math.sin(t / 5.0)
    c = math.cos(t / 7.0)
    return {
        "temp": 50 + 2 * s + 0.5 * c,
        "pressure": 80 + 1.5 * s,
        "vibration": 10 + 0.8 * s + 0.2 * c,
        "flow": 100 + 1.8 * s - 0.3 * c,
        "current": 30 + 0.6 * s + 0.1 * c,
        "acoustic": 12 + 0.4 * s + 0.3 * c,
    }


def scenario_regime_shift(t: int) -> dict[str, float]:
    vals = scenario_nominal(t)
    if t >= 60:
        vals["temp"] += 15
        vals["pressure"] += 10
        vals["flow"] += 18
        vals["current"] += 7
    return vals


def scenario_coupling_instability(t: int) -> dict[str, float]:
    vals = scenario_nominal(t)
    if t >= 60:
        vals["pressure"] += random.uniform(-8, 8)
        vals["flow"] += random.uniform(-10, 10)
        vals["acoustic"] += random.uniform(-4, 4)
    return vals


def scenario_structural_instability(t: int) -> dict[str, float]:
    vals = scenario_nominal(t)
    if t >= 60:
        vals = {
            "temp": random.uniform(35, 85),
            "pressure": random.uniform(55, 110),
            "vibration": random.uniform(2, 22),
            "flow": random.uniform(70, 140),
            "current": random.uniform(15, 45),
            "acoustic": random.uniform(5, 25),
        }
    return vals


def run_structural_scenario(
    name: str,
    fn: Callable[[int], dict[str, float]],
) -> list[dict]:
    engine = StructuralEngine(baseline_window=24, recent_window=12)
    rows: list[dict] = []
    for t in range(TIME_STEPS):
        frame = {
            "timestamp": get_gal2_time(),
            "site_id": "demo_site",
            "asset_id": name,
            "sensor_values": fn(t),
        }
        result = engine.process_frame(frame)
        result["t"] = t
        rows.append(result)
    return rows


def summarize_scenario(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("latest_instability") is not None]
    interpreted = Counter(r.get("interpreted_state") for r in scored if r.get("interpreted_state"))
    states = Counter(r.get("state") for r in scored if r.get("state"))
    scores = [float(r["latest_instability"]) for r in scored if r.get("latest_instability") is not None]
    return {
        "state_counts": dict(states),
        "interpreted_counts": dict(interpreted),
        "mean_score": float(np.mean(scores)) if scores else None,
        "max_score": float(np.max(scores)) if scores else None,
        "final_state": scored[-1].get("state") if scored else None,
        "final_interpreted_state": scored[-1].get("interpreted_state") if scored else None,
    }


# ---------------------------------------------------------------------------
# Part 3: Multi-node scenario
# ---------------------------------------------------------------------------


def base_signals(t: int, bias: float = 0.0) -> dict[str, float]:
    s = math.sin(t / 5.0)
    c = math.cos(t / 7.0)
    return {
        "temp": 50 + bias + 2.0 * s + 0.5 * c,
        "pressure": 80 + 0.5 * bias + 1.5 * s,
        "vibration": 10 + 0.8 * s + 0.2 * c,
        "flow": 100 + 1.8 * s - 0.3 * c,
        "current": 30 + 0.6 * s + 0.1 * c,
        "acoustic": 12 + 0.4 * s + 0.3 * c,
    }


def node_behavior(node: str, t: int) -> dict[str, float | None]:
    bias = {"A": 0.0, "B": 1.5, "C": -1.0, "D": 0.8}[node]
    vals: dict[str, float | None] = dict(base_signals(t, bias))

    if node == "B" and t >= 60:
        vals["temp"] = (vals["temp"] or 0) + 8.0
        vals["current"] = (vals["current"] or 0) + 5.0
        vals["vibration"] = (vals["vibration"] or 0) + 2.5
        vals["flow"] = (vals["flow"] or 0) - 4.0

    if node == "C" and t >= 60:
        vals["pressure"] = (vals["pressure"] or 0) + random.uniform(-8, 8)
        vals["flow"] = (vals["flow"] or 0) + random.uniform(-10, 10)
        vals["acoustic"] = (vals["acoustic"] or 0) + random.uniform(-4, 4)

    if node == "D" and 60 <= t <= 80:
        for k in list(vals.keys()):
            if random.random() < 0.4:
                vals[k] = None
            elif vals[k] is not None:
                vals[k] = vals[k] + random.uniform(-6, 6)

    for k, v in list(vals.items()):
        if v is not None:
            vals[k] = v + random.uniform(-0.25, 0.25)

    return vals


def build_multinode_frames() -> list[dict]:
    frames: list[dict] = []
    for t in range(TIME_STEPS):
        for node in NODES:
            frames.append({
                "logical_t": t,
                "node": node,
                "sensor_values": node_behavior(node, t),
            })
    return frames


def apply_coherent_time(frames: list[dict]) -> list[dict]:
    out: list[dict] = []
    last_ts = 0.0
    for f in frames:
        ts = get_gal2_time()
        ts = float(ts) if ts is not None else time.time()
        if ts <= last_ts:
            ts = last_ts + 1e-6
        last_ts = ts
        out.append({
            "timestamp": ts,
            "site_id": "siteA",
            "asset_id": f["node"],
            "sensor_values": f["sensor_values"],
            "logical_t": f["logical_t"],
        })
    return out


def apply_disturbed_time(frames: list[dict]) -> list[dict]:
    out: list[dict] = []
    for f in frames:
        if random.random() < 0.05:
            continue
        item: dict = {
            "timestamp": time.time() + random.uniform(-3, 3),
            "site_id": "siteA",
            "asset_id": f["node"],
            "sensor_values": f["sensor_values"],
            "logical_t": f["logical_t"],
        }
        out.append(item)
        if random.random() < 0.06:
            dup = dict(item)
            dup["timestamp"] = item["timestamp"] + random.uniform(-2, 2)
            out.append(dup)

    i = 0
    while i < len(out) - 3:
        if random.random() < 0.18:
            j = min(len(out) - 1, i + random.randint(1, 3))
            out[i], out[j] = out[j], out[i]
        i += 1
    return out


def summarize_node_rows(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("latest_instability") is not None]
    states = Counter(r.get("state") for r in scored if r.get("state"))
    interpreted = Counter(r.get("interpreted_state") for r in scored if r.get("interpreted_state"))
    scores = [float(r["latest_instability"]) for r in scored if r.get("latest_instability") is not None]
    return {
        "state_counts": dict(states),
        "interpreted_counts": dict(interpreted),
        "mean_score": float(np.mean(scores)) if scores else None,
        "max_score": float(np.max(scores)) if scores else None,
        "final_state": scored[-1].get("state") if scored else None,
        "final_interpreted_state": scored[-1].get("interpreted_state") if scored else None,
    }


def run_multinode_condition(frames: list[dict]) -> dict:
    engines = {node: StructuralEngine(baseline_window=24, recent_window=12) for node in NODES}
    rows_by_node: dict[str, list[dict]] = defaultdict(list)
    for frame in frames:
        node = frame["asset_id"]
        result = engines[node].process_frame(frame)
        result["logical_t"] = frame["logical_t"]
        result["timestamp_in"] = frame["timestamp"]
        rows_by_node[node].append(result)
    return {
        "summary_by_node": {node: summarize_node_rows(rows) for node, rows in rows_by_node.items()},
        "rows_by_node": dict(rows_by_node),
    }


# ---------------------------------------------------------------------------
# Main: run all three parts and write JSON outputs
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Part 1: Temporal robustness (synthetic time records)
    def simulate_temporal_adversity() -> list[dict]:
        node_state: dict[str, float] = {n: 0.0 for n in NODES}
        results: list[dict] = []
        for t in range(TIME_STEPS):
            for node in NODES:
                gal_t = get_gal2_time()
                jitter = random.uniform(-0.02, 0.02)
                inversion_push = -0.05 if random.random() < 0.08 else 0.0
                irregular_delay = random.uniform(0.0, 0.1) if random.random() < 0.15 else 0.0
                duplicate = random.random() < 0.05
                proposed = node_state[node] + 0.01 + jitter + inversion_push + irregular_delay
                bounded_monotonic = max(node_state[node] + 1e-6, proposed)
                node_state[node] = bounded_monotonic
                results.append({
                    "logical_step": t,
                    "node": node,
                    "gal2_time": gal_t,
                    "bounded_monotonic_time": bounded_monotonic,
                    "jitter": jitter,
                    "inversion_attempt": inversion_push,
                    "irregular_delay": irregular_delay,
                    "duplicate_flag": duplicate,
                })
        return results

    def summarize_part1(rows: list[dict]) -> dict:
        by_node: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_node[r["node"]].append(r["bounded_monotonic_time"])
        summary: dict = {}
        for node, seq in by_node.items():
            diffs = np.diff(seq) if len(seq) > 1 else np.array([])
            summary[node] = {
                "monotonic": bool(np.all(diffs >= 0)) if len(diffs) else True,
                "min_step": float(np.min(diffs)) if len(diffs) else None,
                "max_step": float(np.max(diffs)) if len(diffs) else None,
                "final_time": float(seq[-1]) if seq else None,
            }
        return summary

    part1_rows = simulate_temporal_adversity()
    part1 = {"summary": summarize_part1(part1_rows), "rows": part1_rows}
    with open("part1_temporal_robustness.json", "w") as f:
        json.dump(part1, f, indent=2)

    # Part 2: Structural separation
    part2 = {
        "regime_shift": {"rows": run_structural_scenario("regime_shift", scenario_regime_shift)},
        "coupling_instability": {"rows": run_structural_scenario("coupling_instability", scenario_coupling_instability)},
        "structural_instability": {"rows": run_structural_scenario("structural_instability", scenario_structural_instability)},
    }
    for key in list(part2.keys()):
        part2[key]["summary"] = summarize_scenario(part2[key]["rows"])
    with open("part2_structural_separation.json", "w") as f:
        json.dump(part2, f, indent=2)

    # Part 3: Multi-node persistence
    base_frames = build_multinode_frames()
    part3 = {
        "coherent_time": run_multinode_condition(apply_coherent_time(base_frames)),
        "disturbed_time": run_multinode_condition(apply_disturbed_time(base_frames)),
    }
    with open("part3_multinode_persistence.json", "w") as f:
        json.dump(part3, f, indent=2)

    print("Done - JSON outputs written:")
    print("  - part1_temporal_robustness.json")
    print("  - part2_structural_separation.json")
    print("  - part3_multinode_persistence.json")
