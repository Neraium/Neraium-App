from neraium_core.system_intelligence.falsification import StructuralFalsificationEngine


def _law(law_id: str, effect: float, confidence: float = 0.75):
    return {
        "law_id": law_id,
        "estimated_effect": effect,
        "confidence": confidence,
        "classification": "candidate_structural_law",
    }


def _update(engine: StructuralFalsificationEngine, *, domain: str, escalation: float, laws: list[dict]):
    return engine.update(
        domain=domain,
        transition={"regime": "stressed", "transition_path": "escalating" if escalation >= 0.6 else "stable", "escalation_probability": escalation},
        trajectory={"current_trajectory_archetype": "arch-A", "current_trajectory_path_family": "drift"},
        laws={"law_candidates": laws},
        intervention={
            "recommendation": {
                "ranked_interventions": [
                    {
                        "name": "cooling_adjust",
                        "evidence_sources": {"historical_evidence": {"uncertainty": 0.2}},
                    }
                ]
            }
        },
        universal={
            "experimental_universal_structural_intelligence": {
                "safety_boundary": {"warnings": []},
                "intervention_transfer": {
                    "transferable_interventions": [{"intervention": "cooling_adjust"}],
                    "failed_transfers": [],
                    "domain_specific_interventions": [],
                },
            }
        },
    )


def test_false_pattern_detected_and_penalized():
    engine = StructuralFalsificationEngine()
    law = _law("law::false", effect=0.9)
    for _ in range(4):
        out = _update(engine, domain="energy", escalation=0.2, laws=[law])
    eval_row = out["falsification_analysis"]["law_evaluations"][0]
    assert eval_row["contradiction_count"] >= 4
    assert eval_row["epistemic_status"] in {"fragile_pattern", "falsified_pattern"}
    assert eval_row["robustness_score"] < 0.6


def test_true_pattern_survives_with_higher_robustness_than_false_pattern():
    engine = StructuralFalsificationEngine()
    true_law = _law("law::true", effect=0.7)
    false_law = _law("law::false", effect=0.7)
    for _ in range(5):
        _update(engine, domain="water", escalation=0.8, laws=[true_law])
    out_false = None
    for _ in range(5):
        out_false = _update(engine, domain="water", escalation=0.2, laws=[false_law])
    out_true = _update(engine, domain="water", escalation=0.9, laws=[true_law])
    true_score = out_true["falsification_analysis"]["law_evaluations"][0]["robustness_score"]
    false_score = out_false["falsification_analysis"]["law_evaluations"][0]["robustness_score"]
    assert true_score > false_score


def test_law_splitting_reduces_contradiction_rate_and_transfer_failures_flagged():
    engine = StructuralFalsificationEngine()
    law = _law("law::split", effect=0.8)
    for _ in range(5):
        _update(engine, domain="manufacturing", escalation=0.85, laws=[law])
    out = None
    for _ in range(5):
        out = engine.update(
            domain="finance",
            transition={"regime": "volatile", "transition_path": "stable", "escalation_probability": 0.1},
            trajectory={"current_trajectory_archetype": "arch-A", "current_trajectory_path_family": "drift"},
            laws={"law_candidates": [law]},
            intervention={"recommendation": {"ranked_interventions": []}},
            universal={
                "experimental_universal_structural_intelligence": {
                    "safety_boundary": {"warnings": ["domain mismatch risk"]},
                    "intervention_transfer": {
                        "transferable_interventions": [],
                        "failed_transfers": [{"intervention": "cooling_adjust"}],
                        "domain_specific_interventions": [{"intervention": "valve_tune"}],
                    },
                }
            },
        )
    row = out["falsification_analysis"]["law_evaluations"][0]
    assert row["law_refinement"]["narrower_applicability_scope"] is True
    assert row["law_refinement"]["reduced_contradiction_rate"] > 0
    assert row["transfer_failure"]["transfer_failure_rate"] > 0


def test_adversarial_examples_expose_weakness_and_robustness_decreases_with_contradictions():
    engine = StructuralFalsificationEngine()
    law = _law("law::adv", effect=0.6)
    out1 = None
    for _ in range(5):
        out1 = _update(engine, domain="energy", escalation=0.8, laws=[law])
    r1 = out1["falsification_analysis"]["law_evaluations"][0]["robustness_score"]
    for _ in range(6):
        out2 = _update(engine, domain="energy", escalation=0.1, laws=[law])
    r2 = out2["falsification_analysis"]["law_evaluations"][0]["robustness_score"]
    adv = out2["falsification_analysis"]["counterexamples"]["adversarial_test_results"]
    assert adv["cases_tested"] > 0
    assert adv["false_positive_rate"] >= 0
    assert r2 < r1
