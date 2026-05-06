from copy import deepcopy

from backend.services.neraium_engine_impl import NeraiumEngine
from backend.services.operator_explanation_context import attach_validation_context


def _packet(asset_id: str, cycle: int, scale: float) -> dict:
    return {
        "asset_id": asset_id,
        "cycle": cycle,
        "signals": {
            "sensor_x": 1.0 * scale,
            "sensor_y": 0.5 * scale,
            "sensor_z": 0.25,
        },
    }


def _mapped_packet(asset_id: str, cycle: int, scale: float) -> dict:
    return {
        "asset_id": asset_id,
        "cycle": cycle,
        "signals": {
            "fan_speed": 1.0 * scale,
            "airflow_rate": 0.7 * scale,
            "coolant_temp": 0.2,
        },
    }


def _single_mapped_packet(asset_id: str, cycle: int, scale: float) -> dict:
    return {
        "asset_id": asset_id,
        "cycle": cycle,
        "signals": {
            "fan_speed": 1.0 * scale,
            "sensor_z": 0.25,
        },
    }


def _watch_engine() -> NeraiumEngine:
    return NeraiumEngine(
        config={
            "watch_threshold": 0.10,
            "watch_commitment_threshold": -0.1,
            "watch_recovery_resistance_max": 1.0,
        }
    )


def test_operator_explanation_is_always_returned() -> None:
    engine = NeraiumEngine()

    frame = engine.update(_packet("explain-always", 1, 1.0))

    assert "operator_explanation" in frame
    assert frame["operator_explanation"]["status"] in {"STABLE", "WATCH", "ALERT"}


def test_stable_state_has_no_fake_causes() -> None:
    engine = NeraiumEngine()

    frame = engine.update(_packet("explain-stable", 1, 1.0))
    explanation = frame["operator_explanation"]

    assert explanation["status"] == "STABLE"
    assert explanation["primary_drivers"] == []
    assert explanation["relationship_breakdowns"] == []
    assert explanation["affected_subsystems"] == []
    assert explanation["confidence"]["level"] == "LOW"


def test_primary_drivers_are_ranked_consistently() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_packet("explain-ranked", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_packet("explain-ranked", cycle, 12.0))
    frame = engine.update(_packet("explain-ranked", 58, 12.0))
    explanation = frame["operator_explanation"]

    contributions = [driver["contribution_pct"] for driver in explanation["primary_drivers"]]
    assert explanation["status"] == "WATCH"
    assert contributions
    assert contributions == sorted(contributions, reverse=True)


def test_relationship_breakdowns_require_evidence() -> None:
    engine = NeraiumEngine()

    frame = engine.update(_packet("explain-relationships-stable", 1, 1.0))

    assert frame["operator_explanation"]["relationship_breakdowns"] == []


def test_low_confidence_cases_do_not_overclaim() -> None:
    engine = NeraiumEngine()

    frame = engine.update(_packet("explain-low-confidence", 1, 1.0))
    explanation = frame["operator_explanation"]

    assert explanation["confidence"]["level"] == "LOW"
    assert "root cause" not in str(explanation).lower()


def test_no_unsupported_exact_failure_prediction_language() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_packet("explain-no-rul", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_packet("explain-no-rul", cycle, 10.0))
    frame = engine.update(_packet("explain-no-rul", 58, 10.0))
    text = str(frame["operator_explanation"]).lower()

    assert "exact" not in text
    assert "rul" not in text
    assert "will fail" not in text


def test_mapped_signals_produce_subsystem_aware_drivers() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-airflow", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_mapped_packet("explain-airflow", cycle, 10.0))
    frame = engine.update(_mapped_packet("explain-airflow", 58, 10.0))
    explanation = frame["operator_explanation"]

    assert explanation["status"] == "WATCH"
    assert explanation["likely_affected_subsystem"] == "Airflow / heat exchange"
    assert explanation["affected_subsystems"][0]["subsystem"] == "Airflow / heat exchange"
    assert "fan_speed" in explanation["primary_drivers"][0]["evidence"]
    assert explanation["primary_drivers"][0]["signal"] == "airflow path"
    assert explanation["primary_drivers"][0]["raw_signal"] == "fan_speed"
    assert "fan_speed" in explanation["operator_check"]
    assert "airflow_rate" in explanation["operator_check"]


def test_unmapped_signals_fallback_to_raw_names() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_packet("explain-unmapped", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_packet("explain-unmapped", cycle, 12.0))
    frame = engine.update(_packet("explain-unmapped", 58, 12.0))
    explanation = frame["operator_explanation"]

    assert explanation["status"] == "WATCH"
    assert explanation["primary_drivers"][0]["signal"] == "sensor_x"
    assert explanation["primary_drivers"][0]["raw_signal"] == "sensor_x"
    assert explanation["affected_subsystems"] == []
    assert explanation["likely_affected_subsystem"] == "None indicated."
    assert explanation["operator_check"].startswith("Increase observation.")
    assert "sensor_x" in explanation["operator_check"]
    assert "sensor_y" in explanation["operator_check"]


def test_multiple_signals_support_ranked_affected_subsystem() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-multi-subsystem", cycle, 1.0))
    for cycle in range(56, 63):
        frame = engine.update(_mapped_packet("explain-multi-subsystem", cycle, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["subsystem"] == "Airflow / heat exchange"
    assert affected[0]["score"] > 0.5
    assert "fan_speed" in affected[0]["supporting_signals"]
    assert "airflow_rate" in affected[0]["supporting_signals"]


def test_weak_single_signal_evidence_does_not_exceed_medium_confidence() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_single_mapped_packet("explain-single-subsystem", cycle, 1.0))
    for cycle in range(56, 63):
        frame = engine.update(_single_mapped_packet("explain-single-subsystem", cycle, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["supporting_signals"] == ["fan_speed"]
    assert affected[0]["confidence"] in {"LOW", "MEDIUM"}
    assert affected[0]["confidence"] != "HIGH"


def test_relationship_breakdown_can_raise_subsystem_confidence() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-relationship-confidence", cycle, 1.0))
    for cycle in range(56, 64):
        frame = engine.update(_mapped_packet("explain-relationship-confidence", cycle, 10.0))
    explanation = frame["operator_explanation"]

    assert explanation["relationship_breakdowns"]
    assert explanation["affected_subsystems"][0]["confidence"] == "HIGH"


def test_two_signals_without_persistence_cannot_be_high_confidence() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-no-persistence", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_mapped_packet("explain-no-persistence", cycle, 10.0))
    frame = engine.update(_mapped_packet("explain-no-persistence", 58, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["confidence"] != "HIGH"
    assert affected[0]["score"] <= 0.75


def test_one_mapped_signal_score_is_capped() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_single_mapped_packet("explain-single-cap", cycle, 1.0))
    for cycle in range(56, 63):
        frame = engine.update(_single_mapped_packet("explain-single-cap", cycle, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["confidence"] in {"LOW", "MEDIUM"}
    assert affected[0]["score"] <= 0.65


def test_relationship_evidence_does_not_create_stable_subsystem_claims() -> None:
    engine = _watch_engine()

    frame = engine.update(_mapped_packet("explain-stable-no-relationship-claim", 1, 1.0))
    explanation = frame["operator_explanation"]

    assert explanation["status"] == "STABLE"
    assert explanation["relationship_breakdowns"] == []
    assert explanation["affected_subsystems"] == []


def test_persistent_multi_signal_evidence_can_be_high_confidence() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-persistent-high", cycle, 1.0))
    for cycle in range(56, 64):
        frame = engine.update(_mapped_packet("explain-persistent-high", cycle, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["confidence"] == "HIGH"
    assert affected[0]["score"] < 1.0


def test_weak_evidence_never_reaches_perfect_score() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-weak-score", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_mapped_packet("explain-weak-score", cycle, 10.0))
    frame = engine.update(_mapped_packet("explain-weak-score", 58, 10.0))
    affected = frame["operator_explanation"]["affected_subsystems"]

    assert affected
    assert affected[0]["score"] < 1.0


def test_low_confidence_action_uses_observation_and_raw_signal_basis() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_single_mapped_packet("explain-low-action", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_single_mapped_packet("explain-low-action", cycle, 10.0))
    frame = engine.update(_single_mapped_packet("explain-low-action", 58, 10.0))
    check = frame["operator_explanation"]["operator_check"]

    assert check.startswith("Increase observation.")
    assert "fan_speed" in check
    assert "persistent subsystem support" in check


def test_medium_confidence_action_inspects_subsystem_and_top_signals() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-medium-action", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_mapped_packet("explain-medium-action", cycle, 10.0))
    frame = engine.update(_mapped_packet("explain-medium-action", 58, 10.0))
    check = frame["operator_explanation"]["operator_check"]

    assert check.startswith("Inspect airflow and heat exchange path")
    assert "fan_speed" in check
    assert "airflow_rate" in check
    assert "persistence is still limited" in check


def test_high_confidence_action_uses_persistent_evidence_and_relationship_basis() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-high-action", cycle, 1.0))
    for cycle in range(56, 64):
        frame = engine.update(_mapped_packet("explain-high-action", cycle, 10.0))
    check = frame["operator_explanation"]["operator_check"]

    assert check.startswith("Inspect airflow and heat exchange path")
    assert "persistent" in check
    assert "fan_speed" in check
    assert "airflow_rate" in check
    assert "coupling weakening" in check


def test_stable_action_says_no_inspection_indicated() -> None:
    engine = NeraiumEngine()

    frame = engine.update(_mapped_packet("explain-stable-action", 1, 1.0))

    assert frame["operator_explanation"]["operator_check"] == "No subsystem inspection indicated by current evidence."


def test_operator_check_keeps_read_only_language() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-read-only-action", cycle, 1.0))
    for cycle in range(56, 64):
        frame = engine.update(_mapped_packet("explain-read-only-action", cycle, 10.0))
    check = frame["operator_explanation"]["operator_check"].lower()

    assert "fan_speed" in check
    assert "airflow_rate" in check
    assert "replace" not in check
    assert "shut down" not in check
    assert "adjust" not in check


def test_engine_update_does_not_require_or_use_event_context() -> None:
    engine = NeraiumEngine()

    frame = engine.update(
        {
            "asset_id": "explain-live-no-context",
            "cycle": 1,
            "known_event_cycle": 2803,
            "failure_cycle": 2803,
            "signals": {
                "fan_speed": 1.0,
                "airflow_rate": 0.55,
                "coolant_temp": 0.20,
            },
        }
    )

    assert "validation_context" not in frame["operator_explanation"]


def test_validation_context_attaches_after_explanation_without_changing_decision_fields() -> None:
    engine = _watch_engine()

    for cycle in range(1, 56):
        engine.update(_mapped_packet("explain-validation-context", cycle, 1.0))
    for cycle in range(56, 58):
        engine.update(_mapped_packet("explain-validation-context", cycle, 10.0))
    frame = engine.update(_mapped_packet("explain-validation-context", 58, 10.0))
    before = deepcopy(frame["operator_explanation"])

    attach_validation_context(
        frame,
        known_event_cycle=2803,
        event_label="bearing failure / end-of-life",
    )
    after = frame["operator_explanation"]

    assert after["validation_context"] == {
        "known_event_cycle": 2803,
        "event_label": "bearing failure / end-of-life",
        "cycles_before_known_event": 2745,
        "note": "Validation context only. This was not used by the engine.",
    }
    for key in (
        "status",
        "primary_drivers",
        "affected_subsystems",
        "relationship_breakdowns",
        "operator_check",
        "confidence",
        "recommended_operator_action",
    ):
        assert after[key] == before[key]
