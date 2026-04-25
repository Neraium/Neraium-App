from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from typing import Any

from neraium_core.fd004_synthetic import generate_fd004_synthetic_dataset
from neraium_core.sii import SIIConfig, SIIEngine


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    meaning: str
    expected_range: str
    better_direction: str
    caveat: str


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "structural_rank_compactness_mean": MetricDefinition(
        name="structural_rank_compactness_mean",
        meaning=(
            "Average of SII geometry-layer coherence_score (effective covariance rank / feature count). "
            "Captures structural dimensional compactness, not decision stability."
        ),
        expected_range="[0, 1]",
        better_direction="context-dependent",
        caveat="Lower values can be normal for strongly coupled systems; do not read as decision incoherence.",
    ),
    "decision_stability_mean": MetricDefinition(
        name="decision_stability_mean",
        meaning="Mean per-unit stability score derived from action flips after warmup (1=no flips, 0=maximally unstable).",
        expected_range="[0, 1]",
        better_direction="higher",
        caveat="Depends on warmup and action-availability windows.",
    ),
    "early_signal_rate": MetricDefinition(
        name="early_signal_rate",
        meaning=(
            "Fraction of units with first canonical early-signal cycle at least lead_cycles_before_end before terminal cycle. "
            "Canonical early signal = decision available AND risk level in {medium, high} AND risk trend increasing."
        ),
        expected_range="[0, 1]",
        better_direction="higher",
        caveat="Sensitive to lead-cycle requirement and risk-trend smoothing.",
    ),
    "confidence_threshold_hit_rate": MetricDefinition(
        name="confidence_threshold_hit_rate",
        meaning="Fraction of units that reach decision.confidence >= configured threshold at least once.",
        expected_range="[0, 1]",
        better_direction="higher",
        caveat="Threshold-dependent; compare runs only with identical threshold.",
    ),
    "action_flip_count_total": MetricDefinition(
        name="action_flip_count_total",
        meaning="Total number of action label changes across all units after warmup.",
        expected_range="[0, +∞)",
        better_direction="lower",
        caveat="Counts only when decision actions are available.",
    ),
    "attribution_alignment_coupled_mean": MetricDefinition(
        name="attribution_alignment_coupled_mean",
        meaning=(
            "Mean of causal_analysis.attribution_causal_overlap_score; uses causal primary drivers seeded from attribution top sensors."
        ),
        expected_range="[0, 1]",
        better_direction="higher",
        caveat="Partially attribution-coupled and not an independence test.",
    ),
    "attribution_alignment_independent_mean": MetricDefinition(
        name="attribution_alignment_independent_mean",
        meaning=(
            "Mean overlap between attribution top sensors and independent dominant drivers from score components (out['dominant_drivers'])."
        ),
        expected_range="[0, 1]",
        better_direction="higher",
        caveat="Still heuristic, but less self-referential than coupled overlap.",
    ),
}

OLD_TO_NEW_NAMES = {
    "coherence": "structural_rank_compactness_mean",
    "attribution_alignment": "attribution_alignment_coupled_mean",
    "decision_coherence": "decision_stability_mean",
}


def _unit_action_stability(actions: list[str]) -> tuple[int, float]:
    if len(actions) <= 1:
        return 0, 1.0
    flips = sum(1 for prev, curr in zip(actions, actions[1:]) if prev != curr)
    denom = max(1, len(actions) - 1)
    return flips, max(0.0, 1.0 - (flips / denom))


def _independent_alignment(top_sensors: list[str], dominant_drivers: list[str]) -> float:
    attr_set = {s for s in top_sensors[:5] if s}
    dom_set = {d for d in dominant_drivers[:3] if d}
    if not dom_set:
        return 0.0
    return min(1.0, len(attr_set & dom_set) / len(dom_set))


def run_fd004_canonical_evaluation(
    *,
    num_units: int = 20,
    num_steps: int = 200,
    seed: int = 7,
    confidence_threshold: float = 0.90,
    early_lead_cycles: int = 15,
    warmup_cycles: int = 20,
    output_dir: str | None = None,
) -> dict[str, Any]:
    frames, _ = generate_fd004_synthetic_dataset(num_units=num_units, num_steps=num_steps, seed=seed)

    by_unit: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        by_unit.setdefault(frame["asset_id"], []).append(frame)

    per_unit: list[dict[str, Any]] = []

    with TemporaryDirectory() as td:
        for asset_id, unit_frames in sorted(by_unit.items()):
            engine = SIIEngine(SIIConfig(regime_store_path=str(Path(td) / f"{asset_id}_regimes.json")))

            coherence_values: list[float] = []
            coupled_alignment_values: list[float] = []
            independent_alignment_values: list[float] = []
            actions_all: list[tuple[int, str]] = []

            first_decision_cycle: int | None = None
            first_risk_cycle: int | None = None
            first_early_signal_cycle: int | None = None
            first_confidence_hit_cycle: int | None = None

            for cycle, frame in enumerate(unit_frames):
                out = engine.process_payload(
                    {
                        "timestamp": frame["timestamp"],
                        "site_id": frame["site_id"],
                        "asset_id": frame["asset_id"],
                        "sensor_values": frame["sensor_values"],
                    }
                )

                decision = out.get("decision", {}) if isinstance(out, dict) else {}
                decision_status = decision.get("status", {}) if isinstance(decision, dict) else {}
                decision_available = bool(decision_status.get("available"))
                if first_decision_cycle is None and decision_available:
                    first_decision_cycle = cycle

                confidence = float(decision.get("confidence", 0.0) or 0.0) if isinstance(decision, dict) else 0.0
                if first_confidence_hit_cycle is None and confidence >= confidence_threshold:
                    first_confidence_hit_cycle = cycle

                action = str(decision.get("action", "")).strip() if isinstance(decision, dict) else ""
                if decision_available and action:
                    actions_all.append((cycle, action))

                risk = out.get("risk_assessment", {}) if isinstance(out, dict) else {}
                risk_level = str(risk.get("current_risk_level", "")).strip().lower()
                risk_trend = str(risk.get("risk_trend_smoothed") or risk.get("projected_near_term_trend") or "").strip().lower()

                if first_risk_cycle is None and risk_level in {"medium", "high"}:
                    first_risk_cycle = cycle
                if (
                    first_early_signal_cycle is None
                    and decision_available
                    and risk_level in {"medium", "high"}
                    and risk_trend == "increasing"
                ):
                    first_early_signal_cycle = cycle

                coherence_values.append(float(out.get("coherence_score", 1.0) or 0.0))

                causal = out.get("causal_analysis", {}) if isinstance(out, dict) else {}
                coupled_alignment_values.append(
                    float(causal.get("attribution_causal_overlap_score", 0.0) or 0.0)
                )

                top_sensors = [
                    str(item.get("sensor", "")).strip()
                    for item in (out.get("attribution", {}).get("top_sensors", []) if isinstance(out, dict) else [])[:5]
                    if isinstance(item, dict)
                ]
                dominant_drivers = [str(x).strip() for x in (out.get("dominant_drivers", []) if isinstance(out, dict) else [])]
                independent_alignment_values.append(_independent_alignment(top_sensors, dominant_drivers))

            action_start = max(warmup_cycles, first_decision_cycle or 0)
            post_warmup_actions = [a for c, a in actions_all if c >= action_start]
            flip_count, stability_score = _unit_action_stability(post_warmup_actions)

            per_unit.append(
                {
                    "asset_id": asset_id,
                    "first_decision_cycle": first_decision_cycle,
                    "first_risk_cycle": first_risk_cycle,
                    "first_early_signal_cycle": first_early_signal_cycle,
                    "first_confidence_hit_cycle": first_confidence_hit_cycle,
                    "action_flip_count_post_warmup": flip_count,
                    "decision_stability_score": round(float(stability_score), 4),
                    "structural_rank_compactness_mean": round(mean(coherence_values), 4),
                    "attribution_alignment_coupled_mean": round(mean(coupled_alignment_values), 4),
                    "attribution_alignment_independent_mean": round(mean(independent_alignment_values), 4),
                }
            )

    totals = len(per_unit)
    early_cutoff = num_steps - early_lead_cycles

    aggregate = {
        "units_total": totals,
        "structural_rank_compactness_mean": round(mean(r["structural_rank_compactness_mean"] for r in per_unit), 4),
        "decision_stability_mean": round(mean(r["decision_stability_score"] for r in per_unit), 4),
        "early_signal_rate": round(
            sum(1 for r in per_unit if r["first_early_signal_cycle"] is not None and r["first_early_signal_cycle"] <= early_cutoff)
            / max(1, totals),
            4,
        ),
        "confidence_threshold_hit_rate": round(
            sum(1 for r in per_unit if r["first_confidence_hit_cycle"] is not None) / max(1, totals),
            4,
        ),
        "action_flip_count_total": int(sum(r["action_flip_count_post_warmup"] for r in per_unit)),
        "attribution_alignment_coupled_mean": round(mean(r["attribution_alignment_coupled_mean"] for r in per_unit), 4),
        "attribution_alignment_independent_mean": round(mean(r["attribution_alignment_independent_mean"] for r in per_unit), 4),
    }

    report = {
        "config": {
            "num_units": num_units,
            "num_steps": num_steps,
            "seed": seed,
            "confidence_threshold": confidence_threshold,
            "early_lead_cycles": early_lead_cycles,
            "warmup_cycles": warmup_cycles,
        },
        "name_aliases": OLD_TO_NEW_NAMES,
        "metric_definitions": {key: vars(value) for key, value in METRIC_DEFINITIONS.items()},
        "aggregate": aggregate,
        "per_unit": per_unit,
    }

    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "fd004_canonical_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = [
            "# FD004 Canonical Metric Report",
            "",
            "## Aggregate",
        ]
        for key, value in aggregate.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("## Metric definitions")
        for key, definition in METRIC_DEFINITIONS.items():
            lines.extend(
                [
                    f"### {key}",
                    f"- meaning: {definition.meaning}",
                    f"- expected_range: {definition.expected_range}",
                    f"- better_direction: {definition.better_direction}",
                    f"- caveat: {definition.caveat}",
                    "",
                ]
            )
        (out_dir / "fd004_canonical_metrics.md").write_text("\n".join(lines), encoding="utf-8")

    return report
