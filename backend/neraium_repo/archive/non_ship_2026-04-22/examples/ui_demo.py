from __future__ import annotations

from pathlib import Path
from pprint import pprint
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui.config import UIConfig
from ui.core_integration import build_system_state, classify_transition
from ui.layouts.operations_view import build_operations_view


def _row(**overrides):
    base = {
        "timestamp": "2026-04-10T00:00:00Z",
        "regime_name": "transition",
        "system_health": "watch",
        "confidence_score": 0.74,
        "structural_drift_score": 0.62,
        "relational_stability_score": 0.39,
    }
    base.update(overrides)
    return base


def run_demo() -> None:
    scenarios = [
        {
            "name": "step_1_stable",
            "rows": [
                _row(
                    timestamp="2026-04-10T00:00:00Z",
                    regime_name="baseline",
                    structural_drift_score=0.20,
                    relational_stability_score=0.82,
                    coherence_score=0.83,
                    persistence_minutes=2,
                )
            ],
            "gate_decision": {
                "decision": "SUPPRESS",
                "doctrine_version": "doctrine.v1",
                "timestamp": "2026-04-10T00:00:00Z",
                "confidence_label": "medium",
                "refusal_reason": "No meaningful structural movement from baseline.",
                "criteria_summary": ["stable drift", "high stability"],
                "persistence_minutes": 2,
            },
        },
        {
            "name": "step_2_drift_rising_suppress",
            "rows": [
                _row(
                    timestamp="2026-04-10T00:00:00Z",
                    regime_name="baseline",
                    structural_drift_score=0.20,
                    relational_stability_score=0.82,
                    coherence_score=0.83,
                    persistence_minutes=2,
                ),
                _row(
                    timestamp="2026-04-10T00:04:00Z",
                    regime_name="transition",
                    structural_drift_score=0.48,
                    relational_stability_score=0.61,
                    coherence_score=0.68,
                    persistence_minutes=6,
                ),
            ],
            "gate_decision": {
                "decision": "SUPPRESS",
                "doctrine_version": "doctrine.v1",
                "timestamp": "2026-04-10T00:04:00Z",
                "confidence_label": "medium",
                "refusal_reason": "Signal is moving, but persistence is below admission threshold.",
                "criteria_summary": ["insufficient persistence", "single-source evidence"],
                "persistence_minutes": 6,
            },
        },
        {
            "name": "step_3_persistence_achieved_admit",
            "rows": [
                _row(
                    timestamp="2026-04-10T00:00:00Z",
                    regime_name="baseline",
                    structural_drift_score=0.20,
                    relational_stability_score=0.82,
                    coherence_score=0.83,
                    persistence_minutes=2,
                ),
                _row(
                    timestamp="2026-04-10T00:04:00Z",
                    regime_name="transition",
                    structural_drift_score=0.48,
                    relational_stability_score=0.61,
                    coherence_score=0.68,
                    persistence_minutes=6,
                ),
                _row(
                    timestamp="2026-04-10T00:10:00Z",
                    regime_name="transition",
                    structural_drift_score=0.73,
                    relational_stability_score=0.36,
                    coherence_score=0.74,
                    persistence_minutes=18,
                ),
            ],
            "gate_decision": {
                "decision": "ADMIT",
                "doctrine_version": "doctrine.v1",
                "timestamp": "2026-04-10T00:10:00Z",
                "confidence_label": "high",
                "reason": "Persistence and coherence thresholds are now met.",
                "criteria_summary": ["coherence confirmed", "persistence confirmed", "multiple corroborating signals"],
                "persistence_minutes": 18,
            },
        },
    ]

    for scenario in scenarios:
        state = build_system_state(scenario["rows"], config=UIConfig())
        previous = scenario["rows"][-2] if len(scenario["rows"]) > 1 else None
        transition = classify_transition(previous, scenario["rows"][-1])
        scenario["gate_decision"]["transition"] = transition
        surface = build_operations_view(
            state,
            reasoning_context={"recent_admitted_events": []},
            gate_decision=scenario["gate_decision"],
        )
        print(f"\n=== UI DEMO: {scenario['name']} ===")
        pprint(surface["zones"]["gate"]["content"], sort_dicts=False)


if __name__ == "__main__":
    run_demo()
