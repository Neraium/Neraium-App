"""Dataset loading helpers for engine replay modes.

This module is packaged with ``neraium_core`` so replay does not depend on
repository-local ``scripts`` modules that are unavailable in installed builds.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _load_fd_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = ["unit", "cycle"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"FD dataset missing columns: {missing}")

    df["asset_id"] = df["unit"].astype(str)
    df["site_id"] = "default-site"

    if "timestamp" not in df.columns:
        df["timestamp"] = df["cycle"].astype(str)

    if "structural_drift_score" not in df.columns:
        df["structural_drift_score"] = 0.0

    if "failure_cycle" not in df.columns and "true_rul" in df.columns:
        df["failure_cycle"] = df.groupby("unit")["cycle"].transform("max") + df["true_rul"]

    if "lead_time" not in df.columns:
        if "lead_time_hours" in df.columns:
            df["lead_time"] = df["lead_time_hours"]
        elif "alert_lead" in df.columns:
            df["lead_time"] = df["alert_lead"]
        else:
            df["lead_time"] = None

    return df


def _load_ims_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "cycle" not in df.columns:
        if "t" in df.columns:
            df["cycle"] = df["t"]
        else:
            df["cycle"] = range(len(df))

    if "unit" not in df.columns:
        if "file_name" in df.columns:
            df["unit"] = df["file_name"]
        else:
            df["unit"] = 1

    df["asset_id"] = df["unit"].astype(str)
    df["site_id"] = "default-site"

    if "timestamp" not in df.columns:
        df["timestamp"] = df["cycle"].astype(str)

    if "drift_smooth" in df.columns:
        df["structural_drift_score"] = df["drift_smooth"]
    elif "drift" in df.columns:
        df["structural_drift_score"] = df["drift"]
    elif "structural_drift_score" not in df.columns:
        df["structural_drift_score"] = 0.0

    return df


def _load_generic_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "unit" not in df.columns:
        if "id" in df.columns:
            df["unit"] = df["id"]
        else:
            df["unit"] = 1

    if "cycle" not in df.columns:
        if "time" in df.columns:
            df["cycle"] = df["time"]
        else:
            df["cycle"] = range(len(df))

    df["asset_id"] = df["unit"].astype(str)
    df["site_id"] = "default-site"

    if "timestamp" not in df.columns:
        df["timestamp"] = df["cycle"].astype(str)

    if "structural_drift_score" not in df.columns:
        drift_cols = [c for c in df.columns if "drift" in c.lower() and "score" in c.lower()]
        if drift_cols:
            df["structural_drift_score"] = df[drift_cols[0]]
        else:
            df["structural_drift_score"] = 0.0

    return df


def load_dataset(path: Path, dataset_type: str) -> pd.DataFrame | None:
    if not path.exists():
        return None

    try:
        normalized = dataset_type.lower()
        if normalized in {"fd001", "fd004"}:
            return _load_fd_dataset(path)
        if normalized == "ims":
            return _load_ims_dataset(path)
        return _load_generic_dataset(path)
    except Exception:
        return None
