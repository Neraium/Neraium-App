from __future__ import annotations

import math
from datetime import datetime, timezone

from backend.services.neraium_engine import NeraiumEngine


def _packet(cycle: int, *, drift_start: int = 90, asset_id: str = "TEST-ASSET") -> dict:
    phase = cycle / 9.0
    drift = min(max(0.0, cycle - drift_start) / 33.0, 1.0)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id,
        "cycle": cycle,
        "signals": {
            "spindle_vibration": 0.50 + 0.010 * math.sin(phase) + 0.28 * drift,
            "spindle_load": 0.62 + 0.010 * math.cos(phase / 1.6) + 0.20 * drift,
            "bearing_temperature": 0.42 + 0.006 * math.sin(phase / 2.0) + 0.08 * drift,
            "acoustic_kurtosis": 3.02 + 0.030 * math.cos(phase / 2.4) + 0.92 * drift,
            "motor_current": 0.57 + 0.008 * math.sin(phase / 3.0) + 0.10 * drift,
        },
    }


def _run(max_cycle: int, *, drift_start: int = 90) -> list[dict]:
    engine = NeraiumEngine()
    return [engine.update(_packet(cycle, drift_start=drift_start)) for cycle in range(1, max_cycle + 1)]


def test_output_frame_is_hazard_centered() -> None:
    frame = _run(80)[-1]

    assert {"hazard_score", "hazard_rate", "time_to_threshold", "state", "confidence", "drivers"} <= set(frame)
    assert set(frame["drivers"]) == {
        "structural_drift",
        "trajectory_strength",
        "relational_instability",
    }
    assert frame["audit"]["future_data_used"] is False
    assert frame["audit"]["failure_endpoint_used_during_ingestion"] is False

    stale_primary_outputs = {
        "metrics",
        "trajectory",
        "decision",
        "hazard_estimate",
        "intervention_boundary",
        "failure_time_distribution",
        "where_changed",
    }
    assert stale_primary_outputs.isdisjoint(frame)


def test_no_early_hazard_inflation_during_baseline_and_hold() -> None:
    frames = _run(80)
    hazards = [frame["hazard_score"] for frame in frames]

    assert max(hazards[:49]) == 0.0
    assert max(hazards[:80]) < 0.12
    assert frames[-1]["state"] == "STABLE"
    assert frames[-1]["time_to_threshold"] is None


def test_hazard_rises_under_sustained_degradation_pressure() -> None:
    frames = _run(145)
    early = [frame["hazard_score"] for frame in frames[70:90]]
    watch_window = [frame["hazard_score"] for frame in frames[92:105]]
    late = [frame["hazard_score"] for frame in frames[125:145]]

    assert sum(watch_window) / len(watch_window) > (sum(early) / len(early)) + 0.35
    assert sum(late) / len(late) > (sum(watch_window) / len(watch_window))
    assert any(frame["state"] == "WATCH" for frame in frames)
    assert any(frame["state"] == "ALERT" for frame in frames)


def test_hazard_rate_precedes_alert_confirmation() -> None:
    frames = _run(150)
    alert_index = next(index for index, frame in enumerate(frames) if frame["state"] == "ALERT")
    preceding_rates = [frame["hazard_rate"] for frame in frames[max(0, alert_index - 12) : alert_index]]

    assert max(preceding_rates) > 0.0
    assert frames[alert_index]["hazard_score"] >= 0.60
    assert frames[alert_index]["state"] == "ALERT"
