from neraium_core.fd004_real import (
    Fd004Row,
    fd004_row_to_sii_record,
    load_fd004_dataset,
    run_fd004_real_evaluation,
)


def _sample_row(unit: int, cycle: int, sensor_base: float = 1.0) -> str:
    operating = [0.1, 0.2, 0.3]
    sensors = [sensor_base + i * 0.01 for i in range(21)]
    values = [unit, cycle, *operating, *sensors]
    return " ".join(str(v) for v in values)


def test_load_fd004_dataset_parses_rows(tmp_path):
    source = tmp_path / "train_FD004.txt"
    source.write_text(f"{_sample_row(1, 1)}\n{_sample_row(1, 2)}\n", encoding="utf-8")

    rows = load_fd004_dataset(source)

    assert len(rows) == 2
    assert rows[0].unit == 1
    assert rows[0].time == 1
    assert len(rows[0].sensors) == 21


def test_fd004_row_to_sii_record_pads_to_24_sensors():
    row = Fd004Row(
        unit=7,
        time=3,
        operating_settings=(0.0, 0.1, 0.2),
        sensors=tuple(float(i) for i in range(1, 22)),
    )

    record = fd004_row_to_sii_record(row)

    assert record["asset_id"] == "unit_007"
    assert len(record["sensor_values"]) == 24
    assert record["sensor_values"]["s21"] == 21.0
    assert record["sensor_values"]["s22"] == 0.0
    assert record["sensor_values"]["s24"] == 0.0


def test_run_fd004_real_evaluation_generates_outputs(tmp_path):
    train = tmp_path / "train_FD004.txt"
    test = tmp_path / "test_FD004.txt"
    rul = tmp_path / "RUL_FD004.txt"

    train.write_text(
        "\n".join([_sample_row(1, 1), _sample_row(1, 2), _sample_row(2, 1)]),
        encoding="utf-8",
    )
    test.write_text(_sample_row(1, 1), encoding="utf-8")
    rul.write_text("123\n", encoding="utf-8")

    report = run_fd004_real_evaluation(
        train_path=str(train),
        test_path=str(test),
        rul_path=str(rul),
        output_dir=str(tmp_path),
    )

    assert report["overall_summary"]["units_total"] == 2
    assert report["overall_summary"]["rows_processed"] == 3
    assert report["rul_by_unit"]["unit_001"] == 123
    assert report["overall_summary"]["average_early_warning_window"] is None
    assert report["unit_summaries"][0]["first_MEDIUM_step"] is None
    assert report["unit_summaries"][0]["first_HIGH_step"] is None
    assert report["unit_summaries"][0]["instability_vs_rul_correlation"] is None
    assert report["timeseries"][0]["phase"] == "stable"
    assert report["timeseries"][0]["trend"] == "stable"
    assert "estimated_rul" in report["timeseries"][0]
    assert (tmp_path / "fd004_real_report.json").exists()
    assert (tmp_path / "fd004_real_timeseries.csv").exists()
    assert (tmp_path / "plots").exists()
    assert (tmp_path / "hero_unit_timeseries.csv").exists()
    assert report["proof_summary"] == "reports/fd004_proof_summary.md"
    assert report["hero_unit"]["asset_id"].startswith("unit_")
    assert report["unit_summaries"][0]["signal_emitted"] is False
    assert report["unit_summaries"][0]["signal_strength"] in {"low", "medium", "high"}
    assert report["unit_summaries"][0]["confidence"] in {"low", "medium", "high"}
    assert isinstance(report["unit_summaries"][0]["reason"], list)
    assert isinstance(report["unit_summaries"][0]["operator_message"], str)



def test_run_fd004_real_evaluation_hero_csv_schema(tmp_path):
    train = tmp_path / "train_FD004.txt"
    test = tmp_path / "test_FD004.txt"
    rul = tmp_path / "RUL_FD004.txt"

    train.write_text(
        "\n".join([_sample_row(1, 1), _sample_row(1, 2), _sample_row(1, 3)]),
        encoding="utf-8",
    )
    test.write_text(_sample_row(1, 1), encoding="utf-8")
    rul.write_text("5\n", encoding="utf-8")

    run_fd004_real_evaluation(
        train_path=str(train),
        test_path=str(test),
        rul_path=str(rul),
        output_dir=str(tmp_path),
    )

    hero_csv = (tmp_path / "hero_unit_timeseries.csv").read_text(encoding="utf-8").splitlines()[0]
    assert hero_csv == "timestamp,drift,instability,phase,risk_level,estimated_rul"
