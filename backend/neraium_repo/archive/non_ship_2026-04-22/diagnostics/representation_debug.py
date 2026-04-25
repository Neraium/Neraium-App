from __future__ import annotations

from pathlib import Path

import pandas as pd

from evaluation.representation_compare import load_dataset


def build_debug_table(
    input_path: Path,
    entities: list[str],
    *,
    entity_col: str | None = None,
    time_col: str | None = None,
    features: list[str] | None = None,
) -> pd.DataFrame:
    df, spec = load_dataset(input_path, entity_col=entity_col, time_col=time_col)
    entity_values = set(str(e) for e in entities)
    selected = df[df[spec.entity_col].astype(str).isin(entity_values)].copy()

    if selected.empty:
        raise ValueError("No rows matched selected entities.")

    chosen_features = [c for c in spec.feature_cols if features is None or c in features]
    if not chosen_features:
        raise ValueError("No matching numeric features for debug output.")

    g = selected.groupby(spec.entity_col, sort=False)
    rolling = g[chosen_features].rolling(window=6, min_periods=2).mean().reset_index(level=0, drop=True)
    residual = (selected[chosen_features] - rolling).fillna(0.0)
    delta = g[chosen_features].diff().fillna(0.0)
    slope = (g[chosen_features].diff(periods=3) / 3.0).fillna(0.0)
    ref_profile = g[chosen_features].transform("mean")

    output = selected[[spec.entity_col, spec.time_col]].copy()
    for col in chosen_features:
        output[f"raw_{col}"] = selected[col]
        output[f"reference_{col}"] = ref_profile[col]
        output[f"rolling_mean_{col}"] = rolling[col]
        output[f"residual_{col}"] = residual[col]
        output[f"delta_{col}"] = delta[col]
        output[f"slope_{col}"] = slope[col]

    return output.sort_values([spec.entity_col, spec.time_col]).reset_index(drop=True)
