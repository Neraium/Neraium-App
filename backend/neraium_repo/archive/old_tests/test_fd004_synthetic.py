from neraium_core.fd004_synthetic import (
    Fd004RiskEscalator,
    generate_fd004_synthetic_dataset,
    run_fd004_evaluation,
)


def test_generate_fd004_dataset_shape():
    frames, configs = generate_fd004_synthetic_dataset(
        num_units=3,
        num_steps=30,
        num_sensors=20,
        num_regimes=3,
        seed=11,
    )

    assert len(frames) == 90
    assert len(configs) == 3
    sample = frames[0]
    assert {"timestamp", "site_id", "asset_id", "sensor_values"}.issubset(sample.keys())
    assert len(sample["sensor_values"]) == 20


def test_run_fd004_evaluation_report(tmp_path):
    report = run_fd004_evaluation(num_units=4, num_steps=40, seed=3, output_dir=str(tmp_path))

    assert report["overall_summary"]["units_total"] == 4
    assert len(report["unit_summaries"]) == 4
    assert (tmp_path / "fd004_synthetic_report.json").exists()
    assert (tmp_path / "fd004_synthetic_timeseries.csv").exists()


def test_fd004_risk_escalator_progresses_medium_before_high():
    escalator = Fd004RiskEscalator()
    risks = [
        escalator.update(raw_instability=value, regime_index=0)[0]
        for value in [0.14, 0.19, 0.22, 0.29, 0.34, 0.38, 0.42, 0.46, 0.52, 0.56]
    ]

    assert "MEDIUM" in risks
    assert "HIGH" in risks
    assert risks.index("MEDIUM") < risks.index("HIGH")


def test_fd004_risk_escalator_regime_change_grace_blocks_direct_high():
    escalator = Fd004RiskEscalator()

    pre_risks = [escalator.update(raw_instability=value, regime_index=0)[0] for value in [0.12, 0.15]]
    post_change_risks = [
        escalator.update(raw_instability=value, regime_index=1)[0]
        for value in [0.44, 0.46, 0.48, 0.5, 0.52, 0.54]
    ]

    assert pre_risks[-1] == "LOW"
    assert post_change_risks[0] != "HIGH"
    assert post_change_risks[1] != "HIGH"
    assert post_change_risks[-1] == "HIGH"
