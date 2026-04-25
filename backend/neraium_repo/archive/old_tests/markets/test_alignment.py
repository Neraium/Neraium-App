from __future__ import annotations

import pandas as pd

from neraium_core.markets.data.alignment import align_to_shared_clock


def test_alignment_removes_duplicates_and_fills() -> None:
    idx = pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-02"], utc=True)
    df = pd.DataFrame({"SPY": [1.0, 2.0, None]}, index=idx)
    out = align_to_shared_clock(df)
    assert len(out) == 2
    assert out.isna().sum().sum() == 0
