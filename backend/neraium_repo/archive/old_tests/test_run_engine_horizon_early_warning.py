from __future__ import annotations

from run_engine import StructuralEngine


def _seed_min_histories(engine: StructuralEngine) -> None:
    for v in (0.18, 0.22, 0.2, 0.24, 0.23, 0.21):
        engine._transition_pressure_history.append(v)
    for v in (0.04, 0.06, 0.05, 0.07, 0.06, 0.05):
        engine._shock_activity_history.append(v)
    for v in (0.5, 0.55, 0.6, 0.58, 0.62, 0.6):
        engine._structural_drift_history.append(v)
    for v in (0.01, 0.012, 0.011, 0.013, 0.012, 0.014):
        engine._velocity_history.append(v)


def test_horizon_escalates_to_mid_term_on_persistent_pre_instability() -> None:
    engine = StructuralEngine()
    _seed_min_histories(engine)

    engine._early_warning_state_history.extend(
        ["stable", "pre_instability", "stable", "pre_instability", "pre_instability", "stable"]
    )
    engine._metric_history["lock_in_score"].extend([0.08, 0.1, 0.11, 0.1, 0.12, 0.11])
    engine._metric_history["pre_instability_score"].extend([0.35, 0.38, 0.4, 0.42, 0.41, 0.43])

    analytics = engine._compute_advanced_analytics(
        early_warning={
            "early_warning_state": "pre_instability",
            "pre_instability_score": 0.43,
            "stability_erosion_score": 0.36,
            "coherence_breakdown_score": 0.31,
        }
    )

    horizon = analytics["horizon_analysis"]
    assert horizon["risk_horizon"] == "MID_TERM"
    assert horizon["rationale"]["horizon_before_adjustment"] == "LONGER_HORIZON"
    assert horizon["rationale"]["early_warning_persistence_count"] >= 3


def test_horizon_can_move_to_near_term_on_coupled_early_and_lockin_rise() -> None:
    engine = StructuralEngine()
    _seed_min_histories(engine)

    engine._early_warning_state_history.extend(
        ["stable", "pre_instability", "emerging_instability", "pre_instability", "emerging_instability", "pre_instability"]
    )
    engine._metric_history["lock_in_score"].extend([0.18, 0.2, 0.22, 0.25, 0.27, 0.3])
    engine._metric_history["pre_instability_score"].extend([0.35, 0.39, 0.43, 0.49, 0.56, 0.62])

    analytics = engine._compute_advanced_analytics(
        early_warning={
            "early_warning_state": "pre_instability",
            "pre_instability_score": 0.62,
            "stability_erosion_score": 0.52,
            "coherence_breakdown_score": 0.47,
        }
    )

    horizon = analytics["horizon_analysis"]
    assert horizon["risk_horizon"] == "NEAR_TERM"
    assert horizon["rationale"]["pre_instability_rising"] is True
    assert horizon["rationale"]["lock_in_rising"] is True
