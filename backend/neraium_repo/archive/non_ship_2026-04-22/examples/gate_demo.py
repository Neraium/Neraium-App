from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from pprint import pprint
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from neraium_core.gate import AletheiasGate, GateInput


def run_demo() -> None:
    gate = AletheiasGate()
    cases = [
        (
            "ADMIT",
            GateInput(
                timestamp="2026-04-10T00:00:00Z",
                asset_id="pump-17",
                site_id="site-a",
                drift_score=0.81,
                stability_score=0.23,
                coherence_score=0.79,
                snr_score=2.4,
                persistence_minutes=42.0,
                corroborating_signal_count=3,
                context_flags={"maintenance_mode": False, "startup_transient": False},
                candidate_assertion="Persistent structural drift is present in the vibration manifold.",
                raw_metrics={"vibration_rms": 6.2, "thermal_delta_c": 4.7},
            ),
        ),
        (
            "SUPPRESS",
            GateInput(
                timestamp="2026-04-10T00:05:00Z",
                asset_id="pump-17",
                site_id="site-a",
                drift_score=0.55,
                stability_score=0.38,
                coherence_score=0.68,
                snr_score=1.7,
                persistence_minutes=4.0,
                corroborating_signal_count=1,
                context_flags={"startup_transient": True},
                candidate_assertion="Short spike observed in pressure envelope during startup transient.",
                raw_metrics={"pressure_spike": 1.8, "startup": True},
            ),
        ),
        (
            "ADMISSIBILITY_VOID",
            GateInput(
                timestamp="2026-04-10T00:09:00Z",
                asset_id="pump-17",
                site_id="site-a",
                drift_score=0.93,
                stability_score=0.21,
                coherence_score=0.12,
                snr_score=0.33,
                persistence_minutes=26.0,
                corroborating_signal_count=0,
                context_flags={"instrumentation_compromised": True},
                candidate_assertion="Operator must shut down immediately.",
                raw_metrics={"sensor_fault": True, "stream_gap_s": 36},
            ),
        ),
    ]

    for expected, gate_input in cases:
        decision = gate.evaluate(gate_input)
        print(f"\n=== Expected: {expected} | Actual: {decision.decision} ===")
        pprint(asdict(decision), sort_dicts=False)


if __name__ == "__main__":
    run_demo()
