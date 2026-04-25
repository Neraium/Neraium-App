from __future__ import annotations

import math
import os
import tempfile
import io
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from neraium_core.alignment import StructuralEngine


_COMMON_ENTITY_COLS = ["entity_id", "entity", "unit", "asset_id", "id"]
_COMMON_TIME_COLS = ["time", "timestep", "cycle", "timestamp", "step"]


@dataclass
class DatasetSpec:
    entity_col: str
    time_col: str
    feature_cols: list[str]


def infer_dataset_spec(df: pd.DataFrame, entity_col: str | None = None, time_col: str | None = None) -> DatasetSpec:
    if entity_col is None:
        for candidate in _COMMON_ENTITY_COLS:
            if candidate in df.columns:
                entity_col = candidate
                break
    if time_col is None:
        for candidate in _COMMON_TIME_COLS:
            if candidate in df.columns:
                time_col = candidate
                break

    if entity_col is None or entity_col not in df.columns:
        raise ValueError("Could not infer entity column. Pass --entity-col.")
    if time_col is None or time_col not in df.columns:
        raise ValueError("Could not infer time column. Pass --time-col.")

    numeric_cols = [c for c in df.columns if c not in {entity_col, time_col} and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise ValueError("No numeric feature columns found.")

    return DatasetSpec(entity_col=entity_col, time_col=time_col, feature_cols=numeric_cols)


def load_dataset(path: Path, entity_col: str | None = None, time_col: str | None = None) -> tuple[pd.DataFrame, DatasetSpec]:
    input_path = path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    if input_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(input_path)
    else:
        df = pd.read_csv(input_path)

    spec = infer_dataset_spec(df, entity_col=entity_col, time_col=time_col)
    out = df[[spec.entity_col, spec.time_col] + spec.feature_cols].copy()
    for col in spec.feature_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out[spec.feature_cols] = (
        out.groupby(spec.entity_col)[spec.feature_cols]
        .transform(lambda g: g.ffill().bfill())
        .fillna(0.0)
    )
    out = out.sort_values([spec.entity_col, spec.time_col]).reset_index(drop=True)
    return out, spec


def build_temporal_representation(df: pd.DataFrame, spec: DatasetSpec, mode: str) -> pd.DataFrame:
    base = df.copy()
    entity_col, time_col, features = spec.entity_col, spec.time_col, spec.feature_cols
    base[features] = base[features].astype(float)

    grouped = base.groupby(entity_col, sort=False)
    rolling_mean = grouped[features].rolling(window=6, min_periods=2).mean().reset_index(level=0, drop=True)
    delta = grouped[features].diff().fillna(0.0)
    residual = (base[features] - rolling_mean).fillna(0.0)

    long_mean = grouped[features].transform("mean")
    drift = (rolling_mean - long_mean).fillna(0.0)

    slope = grouped[features].diff(periods=3) / 3.0
    slope = slope.fillna(0.0)

    def _rename(block: pd.DataFrame, prefix: str) -> pd.DataFrame:
        out = block.copy()
        out.columns = [f"{prefix}_{c}" for c in block.columns]
        return out

    chunks: dict[str, pd.DataFrame] = {
        "raw": base[features],
        "raw_only": base[features],
        "residual_only": _rename(residual, "res"),
        "delta_only": _rename(delta, "delta"),
        "drift_only": _rename(drift, "drift"),
        "slope_only": _rename(slope, "slope"),
        "combined": pd.concat(
            [
                _rename(base[features], "raw"),
                _rename(residual, "res"),
                _rename(delta, "delta"),
                _rename(drift, "drift"),
                _rename(slope, "slope"),
            ],
            axis=1,
        ),
    }

    if mode not in chunks:
        raise ValueError(f"Unknown representation mode: {mode}")

    rep = pd.concat([base[[entity_col, time_col]], chunks[mode]], axis=1)
    return rep


def _safe_get(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def run_engine_over_representation(rep_df: pd.DataFrame, spec: DatasetSpec, *, transition_aware: bool = True) -> pd.DataFrame:
    entity_col, time_col = spec.entity_col, spec.time_col
    feature_cols = [c for c in rep_df.columns if c not in {entity_col, time_col}]

    rows: list[dict[str, Any]] = []

    for entity, entity_df in rep_df.groupby(entity_col, sort=False):
        old_env = os.environ.get("NERAIUM_TRANSITION_AWARE")
        with tempfile.TemporaryDirectory() as td:
            os.environ["NERAIUM_TRANSITION_AWARE"] = "1" if transition_aware else "0"
            try:
                engine = StructuralEngine(regime_store_path=str(Path(td) / "regime_eval.json"))
            finally:
                if old_env is None:
                    os.environ.pop("NERAIUM_TRANSITION_AWARE", None)
                else:
                    os.environ["NERAIUM_TRANSITION_AWARE"] = old_env

            ordered = entity_df.sort_values(time_col)
            with redirect_stdout(io.StringIO()):
                for _, rec in ordered.iterrows():
                    frame = {
                        "timestamp": str(rec[time_col]),
                        "site_id": "eval",
                        "asset_id": str(entity),
                        "sensor_values": {
                            col: float(rec[col]) if pd.notna(rec[col]) and np.isfinite(float(rec[col])) else 0.0
                            for col in feature_cols
                        },
                    }
                    try:
                        result = engine.process_frame(frame)
                    except Exception:
                        result = {
                            "state": "ERROR",
                            "transition_pressure": 0.0,
                            "structural_drift_score": 0.0,
                            "experimental_analytics": {},
                        }
                    exp = result.get("experimental_analytics", {}) if isinstance(result, dict) else {}
                    rows.append(
                        {
                            "entity": entity,
                            "time": rec[time_col],
                            "state": result.get("state"),
                            "transition_pressure": float(result.get("transition_pressure", 0.0) or 0.0),
                            "structural_drift_score": float(result.get("structural_drift_score", 0.0) or 0.0),
                            "branching": bool(_safe_get(exp, "branching_analysis", "is_branching") or False),
                            "lock_in_score": _safe_get(exp, "constraint_analysis", "lock_in_score"),
                            "risk_horizon": _safe_get(exp, "horizon_analysis", "risk_horizon"),
                            "trajectory_path": _safe_get(exp, "trajectory_analysis", "dominant_path"),
                            "analytics_available": bool(_safe_get(exp, "trajectory_analysis", "available") is not False),
                        }
                    )

    return pd.DataFrame(rows)


def _first_index(mask: pd.Series, times: pd.Series) -> float | None:
    idx = mask[mask].index
    if len(idx) == 0:
        return None
    return float(times.loc[idx[0]])


def compute_context_leakage_metrics(rep_df: pd.DataFrame, spec: DatasetSpec, early_fraction: float = 0.2) -> dict[str, float | bool]:
    entity_col, time_col = spec.entity_col, spec.time_col
    feature_cols = [c for c in rep_df.columns if c not in {entity_col, time_col}]

    early_rows = []
    for _, g in rep_df.groupby(entity_col):
        n = len(g)
        k = max(2, int(math.ceil(n * early_fraction)))
        early_rows.append(g.sort_values(time_col).head(k))
    early_df = pd.concat(early_rows, ignore_index=True)

    early_means = early_df.groupby(entity_col)[feature_cols].mean()
    global_center = early_df[feature_cols].mean()
    between = float(np.mean(np.linalg.norm(early_means - global_center, axis=1)))

    within_changes = []
    for _, g in rep_df.groupby(entity_col):
        ordered = g.sort_values(time_col)[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        diffs = ordered.diff().dropna()
        if not diffs.empty:
            within_changes.append(float(np.mean(np.linalg.norm(diffs.values, axis=1))))
    within = float(np.mean(within_changes)) if within_changes else 0.0

    static_var = float(early_df.groupby(entity_col)[feature_cols].mean().var(axis=0).mean())
    dynamic_var = float(rep_df.groupby(entity_col)[feature_cols].diff().fillna(0.0).var(axis=0).mean())

    early_separation = between / (within + 1e-8)
    dominance = between / (between + within + 1e-8)

    return {
        "early_separation_score": float(early_separation),
        "between_entity_offset_score": float(between),
        "within_entity_drift_score": float(within),
        "context_dominance_score": float(dominance),
        "static_dynamic_variance_ratio": float(static_var / (dynamic_var + 1e-8)),
        "warning": bool(dominance > 0.65 and early_separation > 1.2),
    }


def summarize_run(rep_df: pd.DataFrame, run_df: pd.DataFrame, spec: DatasetSpec) -> dict[str, float | None]:
    leakage = compute_context_leakage_metrics(rep_df, spec)

    dynamic_vals: list[float] = []
    for _, g in rep_df.groupby(spec.entity_col):
        dynamic_vals.append(float(g.drop(columns=[spec.entity_col, spec.time_col]).diff().abs().mean().mean()))
    dynamic_signal = float(np.mean(dynamic_vals)) if dynamic_vals else 0.0

    per_entity = []
    advanced_count = 0
    horizons = {"IMMINENT", "SHORT_TERM"}
    for entity, g in run_df.groupby("entity"):
        ordered = g.sort_values("time")
        first_branch = _first_index(ordered["branching"].astype(bool), ordered["time"])
        lock_vals = pd.to_numeric(ordered["lock_in_score"], errors="coerce")
        first_lock = _first_index((lock_vals >= 0.6).fillna(False), ordered["time"])
        first_horizon = _first_index(ordered["risk_horizon"].isin(horizons), ordered["time"])
        path = ordered["trajectory_path"].dropna().tail(1)
        if ordered["trajectory_path"].notna().any():
            advanced_count += 1
        per_entity.append(
            {
                "entity": entity,
                "first_branch": first_branch,
                "first_lock": first_lock,
                "first_horizon_collapse": first_horizon,
                "last_path": path.iloc[0] if not path.empty else None,
            }
        )

    entity_df = pd.DataFrame(per_entity)
    path_counts = entity_df["last_path"].value_counts(dropna=True)
    if len(path_counts) > 0:
        p = path_counts / path_counts.sum()
        diversity = float(-(p * np.log(p + 1e-8)).sum())
    else:
        diversity = 0.0

    n_entities = max(1, run_df["entity"].nunique())
    return {
        "early_separation_score": float(leakage["early_separation_score"]),
        "context_dominance_score": float(leakage["context_dominance_score"]),
        "dynamic_signal_strength": dynamic_signal,
        "first_branching_point": float(entity_df["first_branch"].dropna().mean()) if entity_df["first_branch"].notna().any() else None,
        "first_lock_in_rise": float(entity_df["first_lock"].dropna().mean()) if entity_df["first_lock"].notna().any() else None,
        "first_horizon_collapse": float(entity_df["first_horizon_collapse"].dropna().mean()) if entity_df["first_horizon_collapse"].notna().any() else None,
        "fraction_entities_non_null_advanced_analytics": float(advanced_count / n_entities),
        "simple_trajectory_diversity_score": diversity,
    }


def compare_summaries(old: dict[str, float | None], new: dict[str, float | None]) -> pd.DataFrame:
    higher_better = {
        "early_separation_score": False,
        "context_dominance_score": False,
        "dynamic_signal_strength": True,
        "first_branching_point": False,
        "first_lock_in_rise": False,
        "first_horizon_collapse": False,
        "fraction_entities_non_null_advanced_analytics": True,
        "simple_trajectory_diversity_score": True,
    }

    rows = []
    for metric in higher_better:
        a = old.get(metric)
        b = new.get(metric)
        if a is None or b is None:
            delta = None
            verdict = "insufficient_data"
        else:
            delta = float(b - a)
            good = delta > 0 if higher_better[metric] else delta < 0
            if abs(delta) < 1e-9:
                verdict = "no_change"
            else:
                verdict = "better" if good else "worse"
        rows.append({"metric": metric, "old": a, "new": b, "delta": delta, "verdict": verdict})
    return pd.DataFrame(rows)
