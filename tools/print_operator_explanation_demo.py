#!/usr/bin/env python3
"""Print PRONOSTIA operator explanations with validation context."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.neraium_engine import NeraiumEngine  # noqa: E402
from backend.services.operator_explanation_context import attach_validation_context  # noqa: E402
from backend.services.pronostia_demo import TIMELINE  # noqa: E402
from tools.run_pronostia_ingestion_demo import SignalFeatureContext  # noqa: E402


def _print_explanation(label: str, frame: dict) -> None:
    explanation = frame["operator_explanation"]
    print(f"\n[{label}] cycle={frame['cycle']} state={frame['state']}")
    print(f"SYSTEM STATUS: {explanation['status']}")
    print(f"WHAT IS HAPPENING: {explanation['what_is_happening']}")
    print("PRIMARY DRIVERS:")
    if explanation["primary_drivers"]:
        for index, driver in enumerate(explanation["primary_drivers"], start=1):
            print(
                f"{index}. {driver['signal']} ({driver['raw_signal']}), "
                f"{driver['contribution_pct']}%, {driver['direction']}"
            )
    else:
        print("None supported by current evidence.")
    print("RELATIONSHIP BREAKDOWN:")
    if explanation["relationship_breakdowns"]:
        for item in explanation["relationship_breakdowns"]:
            print(f"{item['relationship']} {item['change']}")
    else:
        print("None supported by current evidence.")
    print("RANKED AFFECTED SUBSYSTEMS:")
    if explanation["affected_subsystems"]:
        for item in explanation["affected_subsystems"]:
            print(
                f"- {item['subsystem']} score={item['score']} "
                f"confidence={item['confidence']} signals={', '.join(item['supporting_signals'])}"
            )
    else:
        print("None supported by current evidence.")
    print("OPERATOR CHECK:")
    print(explanation["operator_check"])
    context = explanation.get("validation_context")
    if context:
        print("VALIDATION CONTEXT:")
        print(
            f"{context['cycles_before_known_event']} cycles before "
            f"{context['event_label']} at cycle {context['known_event_cycle']}."
        )
        print(context["note"])


def main() -> int:
    signal_context = SignalFeatureContext()
    if not signal_context.available:
        print("PRONOSTIA vibration cache is not available.", file=sys.stderr)
        return 1

    engine = NeraiumEngine()
    examples: dict[str, dict] = {}
    failure_cycle = int(TIMELINE["failure_endpoint"])
    for cycle in range(1, failure_cycle + 2):
        signals = signal_context.features_at(cycle)
        if not signals:
            continue
        frame = engine.update(
            {
                "asset_id": "FEMTO-BEARING-01",
                "bearing_id": "run_1_1",
                "cycle": cycle,
                "signals": signals,
            }
        )
        attach_validation_context(
            frame,
            known_event_cycle=failure_cycle,
            event_label="bearing failure / end-of-life",
        )
        status = str(frame["operator_explanation"]["status"])
        examples.setdefault(status, frame)
        if {"STABLE", "WATCH", "ALERT"}.issubset(examples):
            break

    for label in ("STABLE", "WATCH", "ALERT"):
        if label in examples:
            _print_explanation(label, examples[label])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
