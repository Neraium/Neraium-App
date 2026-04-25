from neraium_core.fd004_canonical_evaluation import run_fd004_canonical_evaluation


def test_run_fd004_canonical_evaluation_schema(tmp_path):
    report = run_fd004_canonical_evaluation(
        num_units=3,
        num_steps=80,
        seed=5,
        confidence_threshold=0.9,
        output_dir=str(tmp_path),
    )

    aggregate = report["aggregate"]
    assert 0.0 <= aggregate["structural_rank_compactness_mean"] <= 1.0
    assert 0.0 <= aggregate["decision_stability_mean"] <= 1.0
    assert 0.0 <= aggregate["early_signal_rate"] <= 1.0
    assert 0.0 <= aggregate["confidence_threshold_hit_rate"] <= 1.0
    assert aggregate["action_flip_count_total"] >= 0
    assert 0.0 <= aggregate["attribution_alignment_coupled_mean"] <= 1.0
    assert 0.0 <= aggregate["attribution_alignment_independent_mean"] <= 1.0

    assert (tmp_path / "fd004_canonical_metrics.json").exists()
    assert (tmp_path / "fd004_canonical_metrics.md").exists()


def test_canonical_report_marks_alignment_caveat():
    report = run_fd004_canonical_evaluation(num_units=2, num_steps=80, seed=5)
    caveat = report["metric_definitions"]["attribution_alignment_coupled_mean"]["caveat"].lower()
    assert "coupled" in caveat or "not an independence test" in caveat


def test_fd004_canonical_policy_regression_floor():
    report = run_fd004_canonical_evaluation(num_units=3, num_steps=80, seed=5)
    aggregate = report["aggregate"]
    # Regression guard: avoid pathological loss of detection coverage or unstable decisions.
    assert aggregate["early_signal_rate"] >= 0.5
    assert aggregate["decision_stability_mean"] >= 0.1
    assert aggregate["action_flip_count_total"] <= 240
