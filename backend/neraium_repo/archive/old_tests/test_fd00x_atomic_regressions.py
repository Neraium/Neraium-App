import numpy as np
from unittest.mock import patch

from neraium_core.intelligence_stack.atomic_baseline import AtomicBaselineLearner
from neraium_core.intelligence_stack.atomic_calibrated import AtomicMonitorCalibrated
from neraium_core.intelligence_stack.config import DetectorConfig
from neraium_core.intelligence_stack.detector import StructuralDriftDetector


def test_score_unit_uses_provided_reference_stats_without_refit() -> None:
    rng = np.random.default_rng(0)
    healthy = rng.normal(size=(60, 3))
    detector = StructuralDriftDetector(DetectorConfig(calibration_enabled=False))
    ref = detector.fit_reference(healthy)

    shifted_prefix = np.full((ref.n_samples, 3), 25.0)
    tail = rng.normal(loc=0.5, scale=1.2, size=(20, 3))
    data = np.vstack([shifted_prefix, tail])

    out = detector.score_unit(data, ref)

    assert out.reference_stats is ref
    assert not np.allclose(ref.mean, data[: ref.n_samples].mean(axis=0))


def test_event_stats_use_two_sided_event_predicate() -> None:
    learner = AtomicBaselineLearner(latent_states=2, dmd_rank=1, sde_dt=1.0, event_level_std=1.0)
    pattern = np.array([-2.0, 0.0, 2.0, 0.0, -2.0, 0.0, 2.0, 0.0], dtype=float)
    data = np.stack([pattern, pattern], axis=1)

    mean = data.mean(axis=0)
    std = data.std(axis=0)
    rates, _ = learner._event_stats(data, mean, std)

    two_sided = np.abs(data[:, 0] - mean[0]) > (learner.event_level_std * std[0])
    expected_rate = np.where(np.diff(two_sided.astype(int)) != 0)[0].size / data.shape[0]

    assert np.isclose(rates[0], expected_rate)


def test_calibrate_resets_runtime_state_after_collecting_scores() -> None:
    rng = np.random.default_rng(1)
    healthy = rng.normal(size=(80, 3))
    monitor = AtomicMonitorCalibrated(sensors=["s0", "s1", "s2"], config={})

    monitor.calibrate(healthy_data=healthy, validation_data=None)

    assert monitor.counter == 0
    assert monitor.prev_x is None
    assert monitor.buffer.shape[0] == 0
    assert monitor.score_history == []
    assert monitor.component_history == []


def test_suppressed_red_does_not_repromote_internal_state_to_red() -> None:
    rng = np.random.default_rng(2)
    healthy = rng.normal(size=(50, 2))
    monitor = AtomicMonitorCalibrated(
        sensors=["s0", "s1"],
        config={
            "alert_thresholds": {"green_yellow": 0.0, "yellow_red": 0.0},
            "consensus_window": 1,
            "consensus_required": 1,
            "min_alert_duration": 1,
        },
    )
    monitor.learn_baseline(healthy)
    monitor.alert_machine.level = "YELLOW"

    x_t = np.array([0.0, 0.0])
    with patch.object(monitor, "_apply_conformal_calibration", return_value=False), \
         patch.object(monitor, "_apply_contextual_gating", return_value=True), \
         patch.object(monitor, "_apply_consensus_check", return_value=True), \
         patch.object(monitor, "_apply_bh_correction", return_value=True), \
         patch.object(monitor, "_apply_surge_protection", return_value=True):
        upd = monitor.update(x_t, context={})

    assert upd.raw_level == "RED"
    assert upd.alert_level == "YELLOW"
    assert monitor.alert_machine.level == "YELLOW"


def test_surge_protection_uses_prior_level_for_yellow_streak() -> None:
    monitor = AtomicMonitorCalibrated(
        sensors=["s0"],
        config={"min_alert_duration": 5},
    )
    monitor.fp_control["consecutive_yellow"] = 4

    allowed = monitor._apply_surge_protection(prior_level="YELLOW", proposed_level="RED")

    assert allowed
    assert monitor.fp_control["consecutive_yellow"] == 5
