import pandas as pd
import pytest

pytest.importorskip("matplotlib")
import run_fd_test


def _sample_unit_df() -> pd.DataFrame:
    rows = []
    for cycle in range(1, 4):
        row = {"unit": 1, "cycle": cycle, "op1": 0.0, "op2": 0.0, "op3": 0.0}
        for i in range(1, 22):
            row[f"s{i}"] = float(cycle + i)
        rows.append(row)
    return pd.DataFrame(rows)


def test_replay_unit_without_gal2_populates_disabled_fields():
    out = run_fd_test.replay_unit(_sample_unit_df(), use_gal2=False)

    assert len(out) == 3
    assert out[0]["gal2_available"] is False
    assert out[0]["gal2_reason"] == "disabled"


def test_replay_unit_with_gal2_uses_payload(monkeypatch):
    class _StubClient:
        def __init__(self, cache_ms):
            self.cache_ms = cache_ms

        def get_time(self):
            return {
                "available": True,
                "reason": None,
                "gal2_time": "2026-03-25T12:00:00.000Z",
                "drift_ms": 4.0,
                "wobble_ms": 1.0,
                "live_ms": 12,
                "fractal_factor": 0.88,
            }

    monkeypatch.setattr(run_fd_test, "GAL2Client", _StubClient)

    out = run_fd_test.replay_unit(_sample_unit_df(), use_gal2=True, gal2_cache_ms=250)

    assert len(out) == 3
    assert out[0]["gal2_available"] is True
    assert out[0]["gal2_time"] == "2026-03-25T12:00:00.000Z"
    assert out[0]["gal2_drift_ms"] == 4.0
