from backend.services.intervention_boundary_estimator import InterventionBoundaryEstimator


def update(estimator, cycle, drift, stability, covariance, state="STABLE", recovery=0.72, degradation=0.20, lock_in=0.08):
    return estimator.update(
        cycle=cycle,
        structural_drift_score=drift,
        relational_stability_score=stability,
        covariance_shift=covariance,
        drift_velocity=0.0,
        drift_acceleration=0.0,
        trajectory_classification="STABLE" if state == "STABLE" else "DEGRADATION",
        recovery_probability=recovery,
        degradation_probability=degradation,
        lock_in_probability=lock_in,
        current_state=state,
        baseline_ready=True,
    )


def test_stable_sequence_stays_clear_without_time_estimate():
    estimator = InterventionBoundaryEstimator()
    frame = None
    for cycle in range(1, 25):
        frame = update(estimator, cycle, 0.03, 0.96, 0.04)

    assert frame["intervention_boundary_state"] == "CLEAR"
    assert frame["time_to_intervention_boundary_cycles"] is None
    assert frame["confidence"] == "LOW"


def test_noisy_sequence_does_not_become_actionable():
    estimator = InterventionBoundaryEstimator()
    frame = None
    for cycle in range(1, 30):
        drift = 0.18 if cycle % 3 == 0 else 0.07
        covariance = 0.22 if cycle % 4 == 0 else 0.08
        frame = update(estimator, cycle, drift, 0.86, covariance)

    assert frame["intervention_boundary_state"] in {"CLEAR", "APPROACHING"}
    assert frame["intervention_boundary_state"] != "ACTIONABLE"


def test_gradual_degradation_approaches_boundary_with_estimate():
    estimator = InterventionBoundaryEstimator()
    frame = None
    for cycle in range(1, 45):
        drift = min(0.52, 0.08 + cycle * 0.012)
        stability = max(0.45, 0.95 - cycle * 0.01)
        covariance = min(0.55, 0.05 + cycle * 0.012)
        frame = update(
            estimator,
            cycle,
            drift,
            stability,
            covariance,
            state="CONFIRMING",
            recovery=0.22,
            degradation=0.62,
            lock_in=0.16,
        )

    assert frame["intervention_boundary_state"] in {"APPROACHING", "ACTIONABLE"}
    assert frame["confidence"] in {"MEDIUM", "HIGH"}
    assert "PERSISTENT_DRIFT" in frame["reason_codes"]


def test_rapid_degradation_becomes_actionable_or_critical():
    estimator = InterventionBoundaryEstimator()
    frame = None
    for cycle in range(1, 30):
        drift = min(0.95, 0.15 + cycle * 0.04)
        stability = max(0.12, 0.92 - cycle * 0.04)
        covariance = min(1.0, 0.12 + cycle * 0.04)
        frame = update(
            estimator,
            cycle,
            drift,
            stability,
            covariance,
            state="ACTIONABLE",
            recovery=0.12,
            degradation=0.65,
            lock_in=0.42,
        )

    assert frame["intervention_boundary_state"] in {"ACTIONABLE", "CRITICAL"}
    assert frame["confidence"] in {"MEDIUM", "HIGH"}
    assert frame["time_to_intervention_boundary_cycles"] == 0
