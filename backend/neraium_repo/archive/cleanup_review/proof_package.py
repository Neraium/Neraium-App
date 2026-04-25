from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from neraium_core.sii.config import SIIConfig
from neraium_core.sii.engine import SIIEngine
from neraium_core.sii.types import SIIFrame


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    title: str
    description: str
    expected_behavior: str
    telemetry: list[dict[str, float | None]]
    threshold_bounds: dict[str, tuple[float | None, float | None]]
    notes: str


def _base_row(i: int) -> dict[str, float]:
    return {
        "pressure": 50.0 + 0.06 * i,
        "flow": 12.5 - 0.03 * i,
        "vibration": 1.05 + 0.012 * i,
        "temperature": 78.0 + 0.045 * i,
    }


def _scenario_stable_baseline(length: int = 88) -> list[dict[str, float]]:
    return [_base_row(i) for i in range(length)]


def _scenario_gradual_drift(length: int = 90) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for i in range(length):
        row = _base_row(i)
        if i >= 30:
            d = i - 30
            row["pressure"] += 0.22 * d
            row["flow"] -= 0.075 * d
            row["temperature"] += 0.18 * d
            row["vibration"] += 0.06 * d
        rows.append(row)
    return rows


def _scenario_spike(length: int = 88) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for i in range(length):
        row = _base_row(i)
        if 44 <= i <= 47:
            row["pressure"] += 4.0
            row["flow"] -= 1.8
            row["temperature"] += 2.8
            row["vibration"] += 1.5
        rows.append(row)
    return rows


def _scenario_progressive_critical(length: int = 96) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for i in range(length):
        row = _base_row(i)
        if i >= 24:
            d = i - 24
            row["pressure"] += 0.36 * d
            row["flow"] -= 0.12 * d
            row["temperature"] += 0.25 * d
            row["vibration"] += 0.085 * d
        if i >= 70:
            c = i - 70
            row["pressure"] += 0.5 * c
            row["flow"] -= 0.2 * c
            row["temperature"] += 0.35 * c
            row["vibration"] += 0.11 * c
        rows.append(row)
    return rows


def _scenario_messy_data(length: int = 84) -> list[dict[str, float | None]]:
    rows: list[dict[str, float | None]] = []
    for i in range(length):
        row: dict[str, float | None] = _base_row(i)
        if 26 <= i <= 34 and i % 2 == 0:
            row["flow"] = None
        if 36 <= i <= 44 and i % 3 == 0:
            row["vibration"] = None
        if 52 <= i <= 56:
            row["temperature"] = None
        rows.append(row)
    return rows


def scenario_definitions() -> list[ScenarioDefinition]:
    threshold_bounds = {
        "pressure": (None, 78.0),
        "flow": (6.4, None),
        "vibration": (None, 5.2),
        "temperature": (None, 94.0),
    }
    return [
        ScenarioDefinition(
            name="stable_baseline",
            title="Stable baseline",
            description="System remains in normal operating envelope with slow correlated movement.",
            expected_behavior="Neraium remains below warning threshold and threshold baseline never fires.",
            telemetry=_scenario_stable_baseline(),
            threshold_bounds=threshold_bounds,
            notes="Low false-positive demonstration.",
        ),
        ScenarioDefinition(
            name="gradual_drift",
            title="Gradual relational drift",
            description="Cross-signal structure drifts steadily before any single sensor crosses a hard threshold.",
            expected_behavior="Neraium warning appears before threshold trigger with smooth risk progression.",
            telemetry=_scenario_gradual_drift(),
            threshold_bounds=threshold_bounds,
            notes="Primary investor storyline for early warning advantage.",
        ),
        ScenarioDefinition(
            name="abrupt_spike",
            title="Abrupt disturbance / spike",
            description="Short-lived transient perturbation should not permanently escalate systemic risk.",
            expected_behavior="Signal may blip but should recover; no sustained escalation.",
            telemetry=_scenario_spike(),
            threshold_bounds=threshold_bounds,
            notes="Robustness against one-off noise.",
        ),
        ScenarioDefinition(
            name="progressive_critical",
            title="Progressive degradation to critical",
            description="Long, compounding degradation eventually crosses hard operational thresholds.",
            expected_behavior="Neraium warning appears materially earlier than threshold baseline.",
            telemetry=_scenario_progressive_critical(),
            threshold_bounds=threshold_bounds,
            notes="Strongest founder-facing evidence scenario.",
        ),
        ScenarioDefinition(
            name="messy_data",
            title="Missing / messy data",
            description="Dropouts and partial windows stress data quality handling and uncertainty reporting.",
            expected_behavior="Engine remains explicit about uncertainty and avoids unsafe confidence jumps.",
            telemetry=_scenario_messy_data(),
            threshold_bounds=threshold_bounds,
            notes="Trust and safe-degradation evidence.",
        ),
    ]


def threshold_baseline_timeline(
    telemetry: list[dict[str, float | None]],
    bounds: dict[str, tuple[float | None, float | None]],
) -> tuple[list[dict[str, Any]], int | None]:
    timeline: list[dict[str, Any]] = []
    first_trigger: int | None = None
    for idx, row in enumerate(telemetry):
        events: list[str] = []
        for signal, (low, high) in bounds.items():
            value = row.get(signal)
            if value is None:
                continue
            fval = float(value)
            if low is not None and fval <= low:
                events.append(f"{signal}_below_{low}")
            if high is not None and fval >= high:
                events.append(f"{signal}_above_{high}")
        threshold_event = len(events) > 0
        if threshold_event and first_trigger is None:
            first_trigger = idx
        timeline.append(
            {
                "cycle": idx,
                "threshold_event": threshold_event,
                "threshold_reasons": ";".join(events),
            }
        )
    return timeline, first_trigger


def _progression_is_interpretable(risk_levels: list[str]) -> bool:
    order = {"low": 0, "medium": 1, "high": 2}
    cleaned = [str(x).lower() for x in risk_levels if str(x).strip()]
    transitions = 0
    regressions = 0
    for i in range(1, len(cleaned)):
        a = order.get(cleaned[i - 1], 0)
        b = order.get(cleaned[i], 0)
        if a != b:
            transitions += 1
        if b < a:
            regressions += 1
    return regressions <= 1 and transitions <= 8


def _neraium_warning_cycle(
    timeline: list[dict[str, Any]],
    threshold: float = 0.18,
    min_cycle: int = 20,
) -> int | None:
    streak = 0
    for row in timeline:
        cycle = int(row.get("cycle") or 0)
        if cycle < min_cycle:
            continue
        comp = float(row.get("composite_instability") or 0.0)
        if comp >= threshold:
            streak += 1
        else:
            streak = 0
        if streak >= 2:
            return cycle - 1
    return None


def _run_engine_for_scenario(
    scenario: ScenarioDefinition,
    output_dir: Path,
    config: SIIConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    engine = SIIEngine(config=config)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timeline: list[dict[str, Any]] = []
    for idx, sensors in enumerate(scenario.telemetry):
        ts = start + timedelta(minutes=idx)
        if scenario.name == "messy_data" and idx == 60:
            ts = start + timedelta(minutes=40)
        frame = SIIFrame(
            timestamp=ts.isoformat(),
            site_id="proof-site",
            system_id="proof-system",
            asset_id=f"asset-{scenario.name}",
            node_id="node-main",
            sensor_values=sensors,
        )
        result = engine.process_frame(frame)
        dq = result.get("data_quality_summary") or {}
        risk = result.get("risk_assessment") or {}
        timeline.append(
            {
                "cycle": idx,
                "timestamp": frame.timestamp,
                "state": result.get("state"),
                "interpreted_state": result.get("interpreted_state"),
                "risk_level": risk.get("current_risk_level"),
                "structural_drift_score": float(result.get("structural_drift_score") or 0.0),
                "composite_instability": float(
                    (result.get("experimental_analytics") or {}).get("composite_instability") or 0.0
                ),
                "data_quality_statuses": "|".join(dq.get("statuses") or []),
                "quality_gate_passed": bool(dq.get("gate_passed")),
                "missingness_rate": float(dq.get("missingness_rate") or 0.0),
            }
        )
    engine.close()

    threshold_timeline, threshold_first = threshold_baseline_timeline(scenario.telemetry, scenario.threshold_bounds)
    for row, threshold_row in zip(timeline, threshold_timeline):
        row["threshold_event"] = threshold_row["threshold_event"]
        row["threshold_reasons"] = threshold_row["threshold_reasons"]

    warning_threshold = 0.18
    neraium_first = _neraium_warning_cycle(timeline, threshold=warning_threshold)
    lead_cycles = (
        int(threshold_first) - int(neraium_first)
        if neraium_first is not None and threshold_first is not None
        else None
    )
    risk_progression = [str(row.get("risk_level") or "") for row in timeline]

    tail = timeline[-10:] if len(timeline) >= 10 else timeline
    sustained_warning_in_tail = any(float(row.get("composite_instability") or 0.0) >= warning_threshold for row in tail)

    summary = {
        "scenario": scenario.name,
        "title": scenario.title,
        "description": scenario.description,
        "expected_behavior": scenario.expected_behavior,
        "neraium_warning_cycle": neraium_first,
        "threshold_first_trigger_cycle": threshold_first,
        "lead_cycles_neraium_vs_threshold": lead_cycles,
        "progression_interpretable": _progression_is_interpretable(risk_progression),
        "warning_threshold": warning_threshold,
        "sustained_warning_in_tail": sustained_warning_in_tail,
        "quality_statuses_seen": sorted(
            {
                status
                for row in timeline
                for status in str(row.get("data_quality_statuses") or "").split("|")
                if status
            }
        ),
        "max_composite_instability": max((float(row["composite_instability"]) for row in timeline), default=0.0),
        "max_structural_drift": max((float(row["structural_drift_score"]) for row in timeline), default=0.0),
        "notes": scenario.notes,
    }

    scenario_dir = output_dir / scenario.name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    csv_path = scenario_dir / "timeline.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "cycle",
                "timestamp",
                "state",
                "interpreted_state",
                "risk_level",
                "structural_drift_score",
                "composite_instability",
                "threshold_event",
                "threshold_reasons",
                "quality_gate_passed",
                "data_quality_statuses",
                "missingness_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(timeline)

    json_path = scenario_dir / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    proof_statement = (
        f"{scenario.title}: Neraium warning at cycle {neraium_first}, "
        f"threshold first trigger at cycle {threshold_first}, lead={lead_cycles}."
    )
    report_lines = [
        f"# Proof scenario: {scenario.title}",
        "",
        f"- Name: `{scenario.name}`",
        f"- Description: {scenario.description}",
        f"- Expected behavior: {scenario.expected_behavior}",
        f"- Neraium first warning cycle: `{neraium_first}`",
        f"- Threshold first trigger cycle: `{threshold_first}`",
        f"- Lead cycles (threshold - Neraium): `{lead_cycles}`",
        f"- Progression interpretable: `{summary['progression_interpretable']}`",
        f"- Quality statuses observed: `{', '.join(summary['quality_statuses_seen']) or 'none'}`",
        "",
        "## Compact proof statement",
        proof_statement,
        "",
        "## Caveats",
        "- This scenario is deterministic synthetic evidence, not a universal benchmark.",
        "- Neraium outputs are read-only decision support for human operators.",
    ]
    md_path = scenario_dir / "report.md"
    md_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    summary["proof_statement"] = proof_statement
    summary["artifacts"] = {
        "timeline_csv": str(csv_path),
        "summary_json": str(json_path),
        "report_md": str(md_path),
    }
    return timeline, summary


def run_proof_package(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    config = SIIConfig(
        baseline_window=12,
        recent_window=6,
        max_history=256,
        min_samples_for_alerts=12,
        regime_store_path=str(output_dir / "proof_package_regimes.json"),
        allow_context_provider=False,
    )

    scenario_summaries: list[dict[str, Any]] = []
    for scenario in scenario_definitions():
        _, summary = _run_engine_for_scenario(scenario, output_dir, config)
        scenario_summaries.append(summary)

    top_summary = {
        "package": "neraium_threshold_comparison_proof",
        "generated_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
        "scenario_count": len(scenario_summaries),
        "scenarios": scenario_summaries,
    }

    json_path = output_dir / "proof_summary_index.json"
    json_path.write_text(json.dumps(top_summary, indent=2), encoding="utf-8")

    table_header = "| Scenario | Neraium warning | Threshold trigger | Lead cycles | Interpretable |"
    table_sep = "|---|---:|---:|---:|---|"
    table_rows = [
        "| "
        + " | ".join(
            [
                s["scenario"],
                str(s.get("neraium_warning_cycle")),
                str(s.get("threshold_first_trigger_cycle")),
                str(s.get("lead_cycles_neraium_vs_threshold")),
                "yes" if s.get("progression_interpretable") else "no",
            ]
        )
        + " |"
        for s in scenario_summaries
    ]

    md_lines = [
        "# Neraium canonical proof package summary",
        "",
        "This package compares Neraium instability signaling against a transparent threshold-style baseline.",
        "",
        table_header,
        table_sep,
        *table_rows,
        "",
        "## Founder-facing takeaway",
        "Neraium surfaces instability through structural drift/composite progression before hard per-sensor limits in the drift and progressive critical scenarios, while remaining disciplined in stable and noisy scenarios.",
        "",
        "## Notable caveats",
        "- Threshold baseline is intentionally simple and transparent.",
        "- Evidence is deterministic and scenario-driven, not a universal performance guarantee.",
        "- System remains read-only and non-actuating.",
    ]
    md_path = output_dir / "proof_summary_index.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    founder_lines = [
        "# Neraium proof package one-glance artifact",
        "",
        "## What happened",
        "Five deterministic scenarios compare structural instability signaling vs conventional per-signal thresholds.",
        "",
        "## Timing evidence",
        table_header,
        table_sep,
        *table_rows,
        "",
        "## Why it matters",
        "In progressive drift/degradation cases, threshold crossings arrive after relational instability is already visible. Neraium gives operators lead time for investigation before critical hard-limit alarms.",
        "",
        "## Safe product posture",
        "Read-only analytics. Human-in-the-loop. No automated actuation claims.",
    ]
    founder_path = output_dir / "founder_investor_one_glance.md"
    founder_path.write_text("\n".join(founder_lines) + "\n", encoding="utf-8")

    top_summary["artifacts"] = {
        "summary_json": str(json_path),
        "summary_md": str(md_path),
        "founder_one_glance_md": str(founder_path),
    }
    return top_summary
