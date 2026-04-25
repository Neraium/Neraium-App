import numpy as np

from neraium_core.intelligence_stack.sii import SII
from neraium_core.early_warning import early_warning_metrics


def test_constant_window_lag1_acf_is_finite() -> None:
    observations = np.ones((8, 3), dtype=float)
    out = early_warning_metrics(observations)
    assert np.isfinite(out["lag1_autocorrelation"])
    assert out["lag1_autocorrelation"] == 0.0


def test_non_finite_input_does_not_map_to_critical() -> None:
    baseline = np.zeros((32, 3), dtype=float)
    model = SII(["s0", "s1", "s2"], baseline)
    out = model.assess({"s0": np.nan, "s1": np.inf, "s2": 0.0})
    assert out["state"] != "critical"
    assert out["quality_flag"] == "non_finite_input"


def test_to_state_nan_maps_to_insufficient_data() -> None:
    baseline = np.zeros((32, 3), dtype=float)
    model = SII(["s0", "s1", "s2"], baseline)
    assert model._to_state(float("nan")) == "insufficient_data"
