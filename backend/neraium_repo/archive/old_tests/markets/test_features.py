from __future__ import annotations

import pandas as pd

from neraium_core.markets.state.state_vector import build_state_vector


def test_feature_generation_has_expected_columns() -> None:
    idx = pd.date_range("2026-01-01", periods=80, freq="B", tz="UTC")
    cols = ["SPY","QQQ","IWM","XLF","XLK","XLE","XLV","XLI","XLY","XLP","XLU","VIX","US2Y","US10Y","DXY","CRUDE","GOLD"]
    prices = pd.DataFrame({c: 100 + pd.Series(range(len(idx)), index=idx) for c in cols}, index=idx)
    state = build_state_vector(prices)
    assert "advancer_ratio" in state.columns
    assert "vix_change" in state.columns
    assert "SPY_rates_beta" in state.columns
