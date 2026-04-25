from __future__ import annotations

from pathlib import Path

from neraium_core.grow.state_engine import GrowStateEngine
from neraium_core.grow.validation import load_records_from_path, parse_json_payload


def _engine(tmp_path: Path) -> GrowStateEngine:
    return GrowStateEngine(db_path=tmp_path / "grow.db", baseline_window=3, recent_window=2)


def test_scope_aggregation_and_rankings(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.ingest_records(load_records_from_path(Path("examples/grow/demo_telemetry.json")))

    assert len(engine.list_states("plant")) >= 4
    assert len(engine.list_states("zone")) >= 4
    assert len(engine.list_states("room")) >= 4
    assert len(engine.list_states("facility")) >= 2
    assert engine.get_state("portfolio", "portfolio-global") is not None


def test_measured_vs_inferred_plant_mode(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.ingest_records(
        parse_json_payload(
            {
                "records": [
                    {
                        "timestamp": "2026-04-03T08:00:00Z",
                        "site_id": "site-a",
                        "facility_id": "fac-a",
                        "room_id": "room-a",
                        "zone_id": "zone-a",
                        "plant_id": "plant-measured",
                        "signals": {"growth_rate_proxy": 0.5, "stress_index": 0.2, "zone_temperature": 76.0},
                    },
                    {
                        "timestamp": "2026-04-03T08:15:00Z",
                        "site_id": "site-a",
                        "facility_id": "fac-a",
                        "room_id": "room-a",
                        "zone_id": "zone-b",
                        "plant_id": "plant-inferred",
                        "signals": {"stress_index": 0.4, "zone_temperature": 79.0, "zone_relative_humidity": 66.0},
                    },
                ]
            }
        )
    )
    measured = engine.get_state("plant", "plant-measured")
    inferred = engine.get_state("plant", "plant-inferred")
    assert measured is not None and measured.plant_view_mode == "measured_plant_state"
    assert inferred is not None and inferred.plant_view_mode == "inferred_plant_risk_view"


def test_comparison_and_inefficiency_generation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.ingest_records(load_records_from_path(Path("examples/grow/demo_telemetry.json")))

    compare = engine.compare_scope("room", "flower-2")
    assert compare["anchor"]["scope_id"] == "flower-2"
    assert "relative_inefficiency" in compare["summary"]
    assert compare["anchor"]["inefficiency_summary"]


def test_subsystem_and_portfolio_decisions_exist(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    decisions = engine.ingest_records(load_records_from_path(Path("examples/grow/demo_telemetry.json")))
    decision_scopes = {decision.scope_type for decision in decisions}
    assert "subsystem" in decision_scopes or engine.get_state("subsystem", "dehum-fl2") is not None
    assert engine.get_state("facility", "fac-chi-1") is not None
