from backend.services.failure_time_distribution import FailureTimeDistributionModel


def test_stable_distribution_is_low_and_monotonic():
    model = FailureTimeDistributionModel()
    frame = model.predict(
        drift_score=0.02,
        drift_velocity=0.0,
        acceleration=0.0,
        time_in_watch=0,
        time_in_alert=0,
        trajectory="STABLE",
        recovery_probability=0.72,
        degradation_probability=0.20,
        lock_in_probability=0.08,
        baseline_ready=True,
    )
    horizons = frame["horizons"]
    assert horizons["within_50_cycles"] <= horizons["within_100_cycles"] <= horizons["within_200_cycles"]
    assert horizons["within_200_cycles"] < 0.20
    assert frame["is_rul"] is False
    assert frame["is_point_prediction"] is False


def test_riskier_distribution_increases_monotonically():
    model = FailureTimeDistributionModel()
    stable = model.predict(
        drift_score=0.05,
        drift_velocity=0.0,
        acceleration=0.0,
        time_in_watch=0,
        time_in_alert=0,
        trajectory="STABLE",
        recovery_probability=0.72,
        degradation_probability=0.20,
        lock_in_probability=0.08,
        baseline_ready=True,
    )
    risky = model.predict(
        drift_score=0.85,
        drift_velocity=0.04,
        acceleration=0.02,
        time_in_watch=20,
        time_in_alert=8,
        trajectory="LOCK_IN",
        recovery_probability=0.10,
        degradation_probability=0.35,
        lock_in_probability=0.55,
        baseline_ready=True,
    )
    assert risky["horizons"]["within_50_cycles"] > stable["horizons"]["within_50_cycles"]
    assert risky["horizons"]["within_200_cycles"] > risky["horizons"]["within_100_cycles"]
