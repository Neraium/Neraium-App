from __future__ import annotations

import argparse
import contextlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from neraium_core.alignment import StructuralEngine


@dataclass
class ScenarioSummary:
    scenario: str
    alignment_effect_score: float
    structural_decision_change_rate: float
    timing_sensitive_transition_rate: float
    branch_flip_rate: float
    horizon_shift_rate: float
    counterfactual_divergence_rate: float


def _parse_timestamp_series(raw: pd.Series) -> pd.Series:
    as_dt = pd.to_datetime(raw, utc=True, errors="coerce")
    if as_dt.notna().any():
        base = as_dt.dropna().iloc[0]
        secs = (as_dt - base).dt.total_seconds()
        return secs.ffill().bfill().fillna(0.0)
    nums = pd.to_numeric(raw, errors="coerce")
    return nums.ffill().bfill().fillna(0.0)


def _load_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".txt":
        raw = pd.read_csv(path, sep=r"\s+", header=None)
        if raw.shape[1] >= 26:
            cols = ["unit", "cycle"] + [f"op{i}" for i in range(1, 4)] + [f"s{i}" for i in range(1, 22)]
            raw = raw.iloc[:, : len(cols)]
            raw.columns = cols
            df = raw
        else:
            df = pd.read_csv(path)
    else:
        df = pd.read_csv(path)
    cols = set(df.columns)
    if {"timestamp", "site_id", "asset_id"}.issubset(cols):
        sensor_cols = [c for c in df.columns if c not in {"timestamp", "site_id", "asset_id"}]
        out = df.copy()
    else:
        ts_col = "timestamp" if "timestamp" in cols else ("cycle" if "cycle" in cols else None)
        if ts_col is None:
            raise ValueError("Input must contain either timestamp column or cycle column")
        asset_col = "asset_id" if "asset_id" in cols else ("unit" if "unit" in cols else None)
        if asset_col is None:
            out_asset = "asset_0"
            asset = pd.Series([out_asset] * len(df))
        else:
            asset = df[asset_col].astype(str)
        ignore = {ts_col, asset_col} if asset_col else {ts_col}
        sensor_cols = [c for c in df.columns if c not in ignore]
        out = pd.DataFrame(
            {
                "timestamp": df[ts_col],
                "site_id": "dataset",
                "asset_id": asset,
                **{c: df[c] for c in sensor_cols},
            }
        )

    out["timestamp"] = _parse_timestamp_series(out["timestamp"])
    out = out.sort_values(["asset_id", "timestamp"]).reset_index(drop=True)
    return out


def _perturb_timestamps(ts: np.ndarray, mode: str, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.array(ts, dtype=float, copy=True)
    if out.size < 6:
        return out
    if mode == "jittered":
        out += rng.normal(0.0, max(1e-6, np.std(np.diff(out)) * 0.4), size=out.size)
    elif mode == "compressed":
        out = out[0] + (out - out[0]) * 0.45
    elif mode == "stretched":
        out = out[0] + (out - out[0]) * 1.8
    elif mode == "local_misordering":
        idx = int(out.size * 0.45)
        if idx + 2 < out.size:
            out[idx], out[idx + 1] = out[idx + 1], out[idx]
    elif mode == "bursty_sampling":
        for i in range(1, out.size):
            factor = 0.25 if (i % 5 in (0, 1)) else 2.4
            out[i] = out[i - 1] + max(1e-6, (out[i] - out[i - 1]) * factor)
    elif mode == "missing_interval_gaps":
        out[int(out.size * 0.65) :] += (out[-1] - out[0]) * 0.3
    return out


def _align_monotonic(ts: np.ndarray) -> np.ndarray:
    out = np.array(ts, dtype=float, copy=True)
    if out.size <= 1:
        return out
    for i in range(1, out.size):
        if out[i] <= out[i - 1]:
            out[i] = out[i - 1] + 1e-3
    return out


def _run_engine(df: pd.DataFrame) -> pd.DataFrame:
    engine = StructuralEngine()
    rows = []
    sensor_cols = [c for c in df.columns if c not in {"timestamp", "site_id", "asset_id"}]
    with contextlib.redirect_stdout(io.StringIO()):
        for rec in df.to_dict(orient="records"):
            frame = {
                "timestamp": float(rec["timestamp"]),
                "site_id": str(rec["site_id"]),
                "asset_id": str(rec["asset_id"]),
                "sensor_values": {k: float(rec[k]) for k in sensor_cols},
            }
            result = engine.process_frame(frame)
            exp = result.get("experimental_analytics", {})
            rows.append(
                {
                    "transition_state": result.get("transition_state"),
                    "branching": (exp.get("branching_analysis") or {}).get("dominant_branch"),
                    "horizon": (exp.get("horizon_analysis") or {}).get("risk_horizon"),
                    "lock_in": (exp.get("constraint_analysis") or {}).get("commitment_to_failure"),
                    "counterfactual_path": ((exp.get("counterfactual_simulation") or {}).get("baseline_future") or {}).get("projected_path"),
                }
            )
    return pd.DataFrame(rows)


def _change_rate(a: Iterable[object], b: Iterable[object]) -> float:
    aa = list(a)
    bb = list(b)
    n = min(len(aa), len(bb))
    if n == 0:
        return 0.0
    changes = sum(1 for i in range(n) if aa[i] != bb[i])
    return float(changes / n)


def _summarize(naive: pd.DataFrame, aligned: pd.DataFrame, scenario: str) -> ScenarioSummary:
    transition = _change_rate(naive["transition_state"], aligned["transition_state"])
    branch = _change_rate(naive["branching"], aligned["branching"])
    horizon = _change_rate(naive["horizon"], aligned["horizon"])
    counterfactual = _change_rate(naive["counterfactual_path"], aligned["counterfactual_path"])
    lockin = _change_rate(naive["lock_in"], aligned["lock_in"])
    structural = float(np.mean([transition, branch, horizon, counterfactual, lockin]))
    effect = float(np.mean([structural, branch, horizon, counterfactual]))
    return ScenarioSummary(
        scenario=scenario,
        alignment_effect_score=round(effect, 4),
        structural_decision_change_rate=round(structural, 4),
        timing_sensitive_transition_rate=round(transition, 4),
        branch_flip_rate=round(branch, 4),
        horizon_shift_rate=round(horizon, 4),
        counterfactual_divergence_rate=round(counterfactual, 4),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate structural impact of temporal alignment under stressed timing scenarios.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("temporal_alignment_impact.csv"))
    parser.add_argument("--max-rows", type=int, default=0, help="Optional row cap for quick evaluation.")
    args = parser.parse_args()

    df = _load_dataset(args.input)
    if args.max_rows and args.max_rows > 0:
        df = df.head(int(args.max_rows)).copy()
    scenarios = ["baseline", "jittered", "compressed", "stretched", "local_misordering", "bursty_sampling", "missing_interval_gaps"]
    summaries: list[ScenarioSummary] = []

    for mode in scenarios:
        run_df = df.copy()
        ts = run_df["timestamp"].to_numpy(dtype=float)
        if mode != "baseline":
            run_df["timestamp"] = _perturb_timestamps(ts, mode)
        naive = _run_engine(run_df)
        run_df["timestamp"] = _align_monotonic(run_df["timestamp"].to_numpy(dtype=float))
        aligned = _run_engine(run_df)
        summaries.append(_summarize(naive, aligned, mode))

    summary_df = pd.DataFrame([s.__dict__ for s in summaries])
    summary_df.to_csv(args.output, index=False)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
