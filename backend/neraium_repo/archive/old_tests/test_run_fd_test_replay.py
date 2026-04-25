from pathlib import Path

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


def test_replay_unit_uses_cycle_timestamp_and_flattens_diag():
    diag, slim = run_fd_test.replay_unit(_sample_unit_df())

    assert len(diag) == 3
    assert len(slim) == 3
    assert "gal2_time" not in diag[0]
    assert "transition_pressure" in slim[0]
    assert "transition_pressure" in diag[0]


def test_resolve_output_paths_default_names():
    from argparse import Namespace

    args = Namespace(output_mode="both", slim_output=None, diagnostics_output=None)
    r = run_fd_test.resolve_output_paths(args, Path("/tmp/x/out.csv"))
    assert r.slim == Path("/tmp/x/out_slim.csv")
    assert r.diagnostics == Path("/tmp/x/out_diagnostics.csv")


def test_flatten_slim_has_product_columns():
    row = run_fd_test.flatten_slim_result(
        1,
        2,
        {
            "state": "S",
            "structural_drift_score": 0.1,
            "latest_instability": 0.2,
            "transition_pressure": 0.3,
            "predicted_impact": "x",
            "structural_driver": "y",
            "experimental_analytics": {"horizon_analysis": {"risk_horizon": 5}},
            "early_warning": {"early_warning_state": "nominal", "pre_instability_score": 0.4},
        },
    )
    assert row["unit"] == 1
    assert row["cycle"] == 2
    assert row["horizon_analysis_risk_horizon"] == 5
    assert row["predicted_impact"] == "x"
    assert row["structural_driver"] == "y"
