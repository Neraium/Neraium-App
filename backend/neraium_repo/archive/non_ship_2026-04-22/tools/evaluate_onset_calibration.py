from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _quantiles(series: pd.Series) -> dict[str, float]:
    clean = series.dropna().astype(float)
    if clean.empty:
        return {}
    return {str(k): float(v) for k, v in clean.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict().items()}


def evaluate(path: Path) -> dict[str, object]:
    df = pd.read_csv(path)
    required = {
        "unit",
        "cycle",
        "state",
        "transition_pressure",
        "constraint_analysis_lock_in_score",
        "horizon_analysis_risk_horizon",
        "trajectory_analysis_dominant_path",
        "branching_analysis_commitment",
        "counterfactual_baseline_projected_path",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    first_alert = (
        df[df["state"] == "ALERT"]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "first_alert_cycle"})
    )
    fa = first_alert["first_alert_cycle"].astype(float) if not first_alert.empty else pd.Series(dtype=float)

    lock = df["constraint_analysis_lock_in_score"].fillna(0.0).astype(float)
    pressure = df["transition_pressure"].fillna(0.0).astype(float)
    horizon = df["horizon_analysis_risk_horizon"].fillna("UNKNOWN").astype(str)
    branch_true = df.get("branching_analysis_is_branching", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    branch_count = df.get("branching_analysis_branch_count_estimate", pd.Series(1.0, index=df.index)).fillna(1.0).astype(float)

    advanced_population = float(
        (
            df["trajectory_analysis_dominant_path"].notna()
            & df["branching_analysis_commitment"].notna()
            & df["counterfactual_baseline_projected_path"].notna()
            & df["horizon_analysis_risk_horizon"].notna()
            & df["constraint_analysis_lock_in_score"].notna()
        ).mean()
    )

    mode_cycle = None
    mode_share = 0.0
    if not fa.empty:
        counts = fa.value_counts(normalize=True)
        mode_cycle = int(counts.index[0])
        mode_share = float(counts.iloc[0])

    return {
        "rows": int(len(df)),
        "units": int(df["unit"].nunique()),
        "advanced_analytics_population_rate": advanced_population,
        "first_alert_cycle_distribution": {str(int(k)): int(v) for k, v in fa.value_counts().sort_index().to_dict().items()},
        "first_alert_cycle_mean": float(np.mean(fa)) if not fa.empty else 0.0,
        "first_alert_cycle_std": float(np.std(fa)) if not fa.empty else 0.0,
        "first_alert_cycle_unique_count": int(fa.nunique()) if not fa.empty else 0,
        "first_alert_mode_cycle": mode_cycle,
        "first_alert_mode_share": mode_share,
        "most_common_first_alert_fraction": mode_share,
        "onset_dispersion_score": float((fa.std() / (fa.mean() + 1e-6)) if not fa.empty else 0.0),
        "first_alert_examples": first_alert.sort_values(["first_alert_cycle", "unit"]).head(5).to_dict(orient="records"),
        "lock_in_saturation_rate": float((lock >= 0.9).mean()),
        "lock_in_percentiles": _quantiles(lock),
        "horizon_distribution": {k: float(v) for k, v in horizon.value_counts(normalize=True).to_dict().items()},
        "imminent_horizon_rate": float((horizon == "IMMINENT").mean()),
        "branching_true_rate": float(branch_true.mean()),
        "branch_count_estimate_distribution": _quantiles(branch_count),
        "transition_pressure_saturation_rate": float((pressure >= 1.0).mean()),
        "transition_pressure_percentiles": _quantiles(pressure),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate onset synchronization and saturation artifacts from replay CSV.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()

    metrics = evaluate(args.input)
    payload = json.dumps(metrics, indent=2)
    print(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
