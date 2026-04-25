from __future__ import annotations

import numpy as np
import pandas as pd

from neraium_core.markets.signals.signal_generator import generate_signal_for_asset


def test_signal_serialization() -> None:
    idx = pd.date_range("2026-01-01", periods=100, freq="B", tz="UTC")
    rng = np.random.default_rng(7)
    state = pd.DataFrame(rng.normal(0, 0.01, size=(100, 6)), index=idx, columns=["ret_SPY", "vol_SPY", "advancer_ratio", "vix_change", "x1", "x2"])
    signal = generate_signal_for_asset("SPY", "daily", state, 1.0)
    if signal:
        payload = signal.model_dump(mode="json")
        assert payload["asset"] == "SPY"
        assert "scores" in payload
