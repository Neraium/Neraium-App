#!/usr/bin/env python3
"""Generate a PRONOSTIA operator explanation validation report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.neraium_engine import NeraiumEngine  # noqa: E402
from backend.services.operator_explanation_context import attach_validation_context  # noqa: E402
from backend.services.pronostia_demo import TIMELINE  # noqa: E402
from tools.run_pronostia_ingestion_demo import SignalFeatureContext  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PRONOSTIA operator explanation report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/operator_explanation_report.md",
    )
    return parser.parse_args()


def collect_examples() -> Dict[str, Dict[str, Any]]:
    signal_context = SignalFeatureContext()
    if not signal_context.available:
        raise FileNotFoundError("PRONOSTIA vibration cache is not available.")

    engine = NeraiumEngine()
    examples: Dict[str, Dict[str, Any]] = {}
    known_event_cycle = int(TIMELINE["failure_endpoint"])
    for cycle in range(1, known_event_cycle + 2):
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
            known_event_cycle=known_event_cycle,
            event_label="bearing failure / end-of-life",
        )
        status = str(frame["operator_explanation"]["status"])
        examples.setdefault(status, frame)
        if {"STABLE", "WATCH", "ALERT"}.issubset(examples):
            break
    return examples


def section(label: str, frame: Dict[str, Any] | None) -> str:
    if frame is None:
        return f"## {label}\n\nNo {label} sample was emitted during this validation run.\n"

    explanation = frame["operator_explanation"]
    context = explanation.get("validation_context") or {}
    lines = [
        f"## {label}",
        "",
        f"- Cycle: {frame['cycle']}",
        f"- Engine state: {frame['state']}",
        f"- Explanation status: {explanation['status']}",
        f"- Confidence: {explanation['confidence']['level']} - {explanation['confidence']['basis']}",
        f"- What is happening: {explanation['what_is_happening']}",
        "",
        "### Validation Context",
    ]
    if context:
        lines.extend(
            [
                f"- Known event cycle: {context['known_event_cycle']}",
                f"- Event label: {context['event_label']}",
                f"- Cycles before known event: {context['cycles_before_known_event']}",
                f"- Note: {context['note']}",
            ]
        )
    else:
        lines.append("- None attached.")

    lines.extend(["", "### Primary Drivers"])
    if explanation["primary_drivers"]:
        for index, driver in enumerate(explanation["primary_drivers"], start=1):
            lines.append(
                f"{index}. {driver['signal']} (`{driver['raw_signal']}`), "
                f"{driver['contribution_pct']}%, {driver['direction']}. "
                f"Evidence: {driver['evidence']}"
            )
    else:
        lines.append("- None supported by current evidence.")

    lines.extend(["", "### Affected Subsystems"])
    if explanation["affected_subsystems"]:
        for item in explanation["affected_subsystems"]:
            signals = ", ".join(f"`{signal}`" for signal in item["supporting_signals"])
            lines.append(
                f"- {item['subsystem']} - score {item['score']}, confidence {item['confidence']}. "
                f"Supporting signals: {signals}. Evidence: {item['evidence']}"
            )
    else:
        lines.append("- None indicated.")

    lines.extend(["", "### Relationship Breakdowns"])
    if explanation["relationship_breakdowns"]:
        for item in explanation["relationship_breakdowns"]:
            raw = ", ".join(f"`{signal}`" for signal in item.get("raw_signals", []))
            lines.append(
                f"- {item['relationship']} - {item['change']}. "
                f"Raw signals: {raw}. Evidence: {item['evidence']}"
            )
    else:
        lines.append("- None supported by current evidence.")

    lines.extend(
        [
            "",
            "### Operator Check",
            explanation["operator_check"],
            "",
        ]
    )
    return "\n".join(lines)


def build_report(examples: Dict[str, Dict[str, Any]]) -> str:
    return "\n".join(
        [
            "# PRONOSTIA Operator Explanation Validation Report",
            "",
            "Dataset: PRONOSTIA / FEMTO bearing degradation",
            "",
            "This report is generated by replaying PRONOSTIA feature packets forward-only through NeraiumEngine. Known event context is attached only after each explanation is emitted.",
            "",
            "Validation context only. This was not used by the engine.",
            "",
            section("STABLE", examples.get("STABLE")),
            section("WATCH", examples.get("WATCH")),
            section("ALERT", examples.get("ALERT")),
        ]
    )


def main() -> int:
    args = parse_args()
    examples = collect_examples()
    report = build_report(examples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"[REPORT] {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
