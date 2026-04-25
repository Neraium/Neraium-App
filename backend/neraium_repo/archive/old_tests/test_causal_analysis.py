from __future__ import annotations

import math
import tempfile

import pytest

from neraium_core.causal import (
    generate_hypotheses,
    generate_validation_plan,
    rank_actions,
    run_counterfactual_checks,
    score_hypotheses,
)


def _sample_inputs() -> tuple[dict, dict, dict, dict]:
    attribution = {
        "top_drivers": [{"feature": "sensor_a"}, {"feature": "sensor_c"}, {"feature": "sensor_f"}],
        "driver_scores": {"sensor_a": 0.88, "sensor_c": 0.62, "sensor_f": 0.41},
    }
    structural_signals = {
        "structural_drift_score": 1.28,
        "relational_instability_score": 1.02,
        "regime_distance": 0.74,
        "regime_drift": 0.68,
        "transition_pressure": 1.12,
        "localization_score": 0.73,
        "temporal_distortion_score": 0.26,
    }
    regime_memory = {"regime_name": "regime_1", "regime_distance": 0.74, "library_size": 3}
    risk_assessment = {"risk_level": "HIGH", "trend": "RISING", "latest_instability": 1.61}
    return attribution, structural_signals, regime_memory, risk_assessment


def _frame(t: int, sensors: dict[str, float]) -> dict:
    return {
        "timestamp": str(t),
        "site_id": "site_1",
        "asset_id": "asset_1",
        "sensor_values": sensors,
    }


def test_hypothesis_generation_structure_and_determinism() -> None:
    attribution, structural_signals, regime_memory, risk_assessment = _sample_inputs()

    out_a = generate_hypotheses(
        attribution=attribution,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )
    out_b = generate_hypotheses(
        attribution=attribution,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )

    assert out_a == out_b
    assert len(out_a) >= 3

    for hyp in out_a:
        assert isinstance(hyp.get("hypothesis_id"), str)
        assert isinstance(hyp.get("description"), str)
        assert hyp.get("type") in {"physical", "sensor", "systemic"}
        assert isinstance(hyp.get("confidence"), float)
        assert isinstance(hyp.get("supporting_evidence"), list)
        assert isinstance(hyp.get("conflicting_evidence"), list)
        assert isinstance(hyp.get("primary_drivers"), list)


def test_hypothesis_generation_works_without_driver_scores_key() -> None:
    _, structural_signals, regime_memory, risk_assessment = _sample_inputs()
    attribution = {"top_drivers": [{"feature": "sensor_x", "score": 0.9}, {"feature": "sensor_y", "score": 0.4}]}
    hypotheses = generate_hypotheses(
        attribution=attribution,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )
    assert len(hypotheses) >= 3


def test_hypothesis_generation_handles_non_mapping_attribution() -> None:
    _, structural_signals, regime_memory, risk_assessment = _sample_inputs()
    hypotheses = generate_hypotheses(
        attribution=None,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )
    assert len(hypotheses) >= 3


def test_hypothesis_scoring_and_ranking_behavior() -> None:
    attribution, structural_signals, regime_memory, risk_assessment = _sample_inputs()
    hypotheses = generate_hypotheses(
        attribution=attribution,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )

    scored = score_hypotheses(
        hypotheses=hypotheses,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
        structural_signals=structural_signals,
    )

    ranked = scored["ranked_hypotheses"]
    assert len(ranked) >= 3
    assert scored["top_hypothesis"] == ranked[0]
    assert ranked[0]["ranking_score"] >= ranked[-1]["ranking_score"]


def test_counterfactual_and_validation_plan_shape() -> None:
    attribution, structural_signals, regime_memory, risk_assessment = _sample_inputs()
    hypotheses = generate_hypotheses(
        attribution=attribution,
        structural_signals=structural_signals,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
    )
    scored = score_hypotheses(
        hypotheses=hypotheses,
        regime_memory=regime_memory,
        risk_assessment=risk_assessment,
        structural_signals=structural_signals,
    )

    cf = run_counterfactual_checks(
        top_hypothesis=scored["top_hypothesis"],
        attribution=attribution,
        structural_signals=structural_signals,
    )
    assert "counterfactual_checks" in cf
    assert len(cf["counterfactual_checks"]) == 3
    assert 0.0 <= cf["robustness"] <= 1.0

    plan = generate_validation_plan(
        ranked_hypotheses=scored["ranked_hypotheses"],
        attribution=attribution,
        risk_assessment=risk_assessment,
        counterfactual=cf,
    )
    assert len(plan) >= 1
    for action in plan:
        assert "action" in action
        assert "target" in action
        assert "expected_outcome_if_true" in action
        assert "expected_outcome_if_false" in action
        assert "priority" in action
        assert "confidence" in action

    ranked_actions = rank_actions(validation_plan=plan, risk_assessment=risk_assessment)
    assert ranked_actions["best_next_action"] == ranked_actions["recommended_sequence"][0]


def test_process_frame_includes_causal_analysis_and_aligns_with_risk() -> None:
    pytest.importorskip("matplotlib")
    from neraium_core.alignment import StructuralEngine

    with tempfile.TemporaryDirectory() as d:
        engine = StructuralEngine(baseline_window=24, recent_window=8, regime_store_path=f"{d}/r.json")

        latest = None
        for t in range(120):
            base = math.sin(0.08 * t)
            if t < 60:
                sensors = {
                    "sensor_a": base,
                    "sensor_b": 0.95 * base,
                    "sensor_c": 1.03 * base,
                }
            else:
                sensors = {
                    "sensor_a": base + 0.25 * math.sin(0.7 * t),
                    "sensor_b": 0.55 * base + 0.35 * math.sin(0.25 * t + 0.4),
                    "sensor_c": 1.2 * base + 0.28 * math.cos(0.31 * t),
                }
            latest = engine.process_frame(_frame(t, sensors))

        assert latest is not None
        assert "causal_attribution" not in latest
        assert "attribution" in latest
        assert "regime_memory" in latest
        assert "risk_assessment" in latest
        assert "operator_guidance" in latest
        assert "causal_analysis" in latest
        causal_analysis = latest["causal_analysis"]
        assert "hypotheses" in causal_analysis
        assert "counterfactual" in causal_analysis
        assert "validation_plan" in causal_analysis
        assert "recommended_sequence" in causal_analysis
        assert "status" in causal_analysis

        assert isinstance(causal_analysis["hypotheses"], list)
        assert isinstance(causal_analysis["validation_plan"], list)
        assert isinstance(causal_analysis["recommended_sequence"], list)

        if causal_analysis["hypotheses"]:
            assert causal_analysis["top_hypothesis"] == causal_analysis["hypotheses"][0]
        assert "risk_level" in latest
