from pathlib import Path

from neraium_core.fd004_plotting import (
    generate_fd004_hero_plot,
    generate_fd004_subset_plots,
    select_hero_unit,
    select_representative_units,
)


def test_select_representative_units_uses_low_median_high_peak_instability():
    summaries = [
        {"asset_id": "unit_001", "peak_instability": 0.1},
        {"asset_id": "unit_002", "peak_instability": 0.5},
        {"asset_id": "unit_003", "peak_instability": 0.9},
        {"asset_id": "unit_004", "peak_instability": 0.6},
    ]

    selected = select_representative_units(summaries, max_units=3)

    assert selected == ["unit_001", "unit_004", "unit_003"]


def test_generate_fd004_subset_plots_writes_selected_units(monkeypatch, tmp_path):
    timeseries = [
        {"asset_id": "unit_001", "cycle": 1, "phase": "stable"},
        {"asset_id": "unit_002", "cycle": 1, "phase": "drift"},
        {"asset_id": "unit_003", "cycle": 1, "phase": "unstable"},
    ]
    unit_summaries = [
        {"asset_id": "unit_001", "peak_instability": 0.1},
        {"asset_id": "unit_002", "peak_instability": 0.5},
        {"asset_id": "unit_003", "peak_instability": 1.0},
    ]

    def fake_plot(rows, output_path, include_rul_curve=True):  # noqa: ANN001, FBT002
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"rows={len(rows)} rul={include_rul_curve}", encoding="utf-8")

    monkeypatch.setattr("neraium_core.fd004_plotting.plot_fd004_unit_timeseries", fake_plot)

    generated = generate_fd004_subset_plots(
        timeseries,
        unit_summaries,
        output_dir=tmp_path,
        max_units=3,
        include_rul_curve=True,
    )

    assert len(generated) == 3
    assert all(path.exists() for path in generated)
    assert generated[0] == tmp_path / "plots" / "unit_001_sii_plot.png"


def test_select_hero_unit_prefers_progression_and_smoother_instability():
    summaries = [
        {"asset_id": "unit_001", "first_MEDIUM_step": 2, "first_HIGH_step": 5, "peak_instability": 0.7},
        {"asset_id": "unit_002", "first_MEDIUM_step": 2, "first_HIGH_step": 5, "peak_instability": 0.9},
        {"asset_id": "unit_003", "first_MEDIUM_step": None, "first_HIGH_step": 4, "peak_instability": 1.0},
    ]
    timeseries = [
        {"asset_id": "unit_001", "cycle": 1, "phase": "stable", "composite_instability": 0.1},
        {"asset_id": "unit_001", "cycle": 2, "phase": "drift", "composite_instability": 0.2},
        {"asset_id": "unit_001", "cycle": 3, "phase": "drift", "composite_instability": 0.3},
        {"asset_id": "unit_001", "cycle": 4, "phase": "unstable", "composite_instability": 0.4},
        {"asset_id": "unit_002", "cycle": 1, "phase": "stable", "composite_instability": 0.1},
        {"asset_id": "unit_002", "cycle": 2, "phase": "drift", "composite_instability": 0.45},
        {"asset_id": "unit_002", "cycle": 3, "phase": "drift", "composite_instability": 0.2},
        {"asset_id": "unit_002", "cycle": 4, "phase": "unstable", "composite_instability": 0.9},
        {"asset_id": "unit_003", "cycle": 1, "phase": "stable", "composite_instability": 0.2},
        {"asset_id": "unit_003", "cycle": 2, "phase": "unstable", "composite_instability": 1.1},
    ]

    selected = select_hero_unit(summaries, timeseries)

    assert selected == "unit_001"


def test_generate_fd004_hero_plot_logs_and_skips_without_matplotlib(monkeypatch, capsys, tmp_path):
    timeseries = [
        {"asset_id": "unit_001", "cycle": 1, "phase": "stable", "composite_instability": 0.1},
        {"asset_id": "unit_001", "cycle": 2, "phase": "drift", "composite_instability": 0.2},
        {"asset_id": "unit_001", "cycle": 3, "phase": "unstable", "composite_instability": 0.4},
    ]
    summaries = [{"asset_id": "unit_001", "first_MEDIUM_step": 2, "first_HIGH_step": 3, "peak_instability": 0.4}]

    def fake_plot(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ImportError("No module named 'matplotlib'")

    monkeypatch.setattr("neraium_core.fd004_plotting.plot_fd004_unit_timeseries", fake_plot)

    hero, generated = generate_fd004_hero_plot(
        timeseries,
        summaries,
        output_path=tmp_path / "plots" / "hero_unit.png",
        include_rul_curve=True,
    )

    captured = capsys.readouterr().out
    assert hero == "unit_001"
    assert generated is False
    assert "Selected hero unit: unit_001" in captured
    assert "Skipping hero FD004 plot because matplotlib is unavailable" in captured
