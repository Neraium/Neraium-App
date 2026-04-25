from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.config import UIConfig
from ui.core_integration import build_system_state
from ui.reasoning import build_reasoning_context, generate_reasoned_response


if __name__ == "__main__":
    demo_rows = [
        {
            "timestamp": "2026-04-10T00:00:00Z",
            "structural_drift_score": 0.32,
            "relational_stability_score": 0.68,
            "regime_name": "baseline",
            "system_health": "nominal",
            "confidence_score": 0.86,
            "event_admitted": False,
        },
        {
            "timestamp": "2026-04-10T00:10:00Z",
            "structural_drift_score": 0.67,
            "relational_stability_score": 0.39,
            "regime_name": "transition",
            "system_health": "watch",
            "confidence_score": 0.82,
            "event_admitted": True,
            "evidence_summary": "drift breached threshold while stability remained suppressed",
            "top_contributing_signals": ["vibration_rms", "temp_gradient", "pressure_delta"],
        },
    ]

    state = build_system_state(demo_rows, config=UIConfig())
    reasoning_context = build_reasoning_context(state, demo_rows)
    result = generate_reasoned_response(operator_question="Why was this event flagged?", reasoning_context=reasoning_context)

    print("Reasoning context keys:", sorted(reasoning_context.keys()))
    print("\nGrounded Answer:\n")
    print(result["answer"])
