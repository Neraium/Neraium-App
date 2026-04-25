from __future__ import annotations

import numpy as np
import pandas as pd

from neraium_core.markets.structure.drift_metrics import compute_drift_components, compute_structural_drift_score


def test_drift_scoring_increases_with_perturbation() -> None:
    idx = pd.date_range("2026-01-01", periods=120, freq="B", tz="UTC")
    base = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, size=(120, 4)), index=idx, columns=list("ABCD"))
    baseline, recent = base.iloc[:80], base.iloc[80:]
    calm = compute_structural_drift_score(compute_drift_components(baseline, recent))
    recent2 = recent.copy()
    recent2["A"] *= 4.0
    shock = compute_structural_drift_score(compute_drift_components(baseline, recent2))
    assert shock > calm
