"""Post-processing helpers for operator explanation validation context.

These helpers intentionally run outside NeraiumEngine.update(). Known event
cycles are validation/demo annotations only; they must not influence detection,
drivers, confidence, or recommended actions.
"""

from __future__ import annotations

from typing import Any, Dict


def attach_validation_context(
    frame: Dict[str, Any],
    *,
    known_event_cycle: int | None,
    event_label: str,
) -> Dict[str, Any]:
    if known_event_cycle is None:
        return frame
    explanation = frame.get("operator_explanation")
    if not isinstance(explanation, dict):
        return frame
    cycle = int(frame.get("cycle") or 0)
    explanation["validation_context"] = {
        "known_event_cycle": int(known_event_cycle),
        "event_label": event_label,
        "cycles_before_known_event": int(known_event_cycle) - cycle,
        "note": "Validation context only. This was not used by the engine.",
    }
    return frame
