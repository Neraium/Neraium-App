#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize broader FD001 validation outputs into lightweight artifacts.")
    p.add_argument("--summary-csv", type=Path, required=True)
    p.add_argument("--milestones-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--confidence-threshold", type=float, default=0.60)
    p.add_argument("--warmup-cycles", type=int, default=20)
    return p.parse_args()


def _to_int(value: str | None) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


def _norm_token(text: str | None) -> str:
    return (text or "").strip().lower().replace("-", "_")


def _hypothesis_matches_driver(hypothesis_id: str | None, driver: str | None) -> bool:
    h = _norm_token(hypothesis_id)
    d = _norm_token(driver)
    if not h or not d:
        return False
    return d in h or h in d


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = load_csv(args.summary_csv)
    milestone_rows = load_csv(args.milestones_csv)

    by_unit: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in summary_rows:
        uid = _to_int(row.get("unit_id"))
        if uid is None:
            continue
        by_unit[uid].append(row)

    for uid in by_unit:
        by_unit[uid].sort(key=lambda r: _to_int(r.get("cycle")) or 0)

    base_milestones: dict[int, dict[str, int | None]] = {}
    for row in milestone_rows:
        uid = _to_int(row.get("unit_id"))
        if uid is None:
            continue
        base_milestones[uid] = {
            "max_cycle_observed": _to_int(row.get("max_cycle_observed")),
            "first_risk_cycle": _to_int(row.get("first_risk_cycle")),
            "first_decision_cycle": _to_int(row.get("first_decision_cycle")),
            "first_stable_hypothesis_cycle": _to_int(row.get("first_stable_hypothesis_cycle")),
        }

    per_unit_rows: list[dict[str, object]] = []
    summary_stats_rows: list[dict[str, object]] = []

    usable_confidence_units = 0
    early_signal_units = 0
    coherent_units = 0

    for uid, rows in sorted(by_unit.items()):
        m = base_milestones.get(uid, {})
        max_cycle = m.get("max_cycle_observed")
        if max_cycle is None:
            max_cycle = max((_to_int(r.get("cycle")) or 0) for r in rows)

        first_conf_cycle = None
        for r in rows:
            if _to_float(r.get("decision_confidence")) >= args.confidence_threshold:
                first_conf_cycle = _to_int(r.get("cycle"))
                break

        first_decision = m.get("first_decision_cycle")
        warmup_start = max(args.warmup_cycles, first_decision or 0)

        post_warmup = [r for r in rows if (_to_int(r.get("cycle")) or 0) >= warmup_start]
        actions = [str(r.get("decision_action") or "") for r in post_warmup if str(r.get("decision_action") or "").strip()]

        action_flips = 0
        for a_prev, a_curr in zip(actions, actions[1:]):
            if a_prev != a_curr:
                action_flips += 1

        def avg_step(key: str) -> float:
            vals = [_to_float(r.get(key)) for r in post_warmup]
            if len(vals) < 2:
                return 0.0
            steps = [abs(v2 - v1) for v1, v2 in zip(vals, vals[1:])]
            return mean(steps)

        avg_dec_step = avg_step("decision_confidence")
        avg_hyp_step = avg_step("top_hypothesis_confidence")

        matches = 0
        match_total = 0
        for r in post_warmup:
            h = r.get("top_hypothesis_id")
            d = r.get("top_attribution_driver")
            if _norm_token(h) and _norm_token(d):
                match_total += 1
                if _hypothesis_matches_driver(h, d):
                    matches += 1
        match_rate = (matches / match_total) if match_total else 0.0

        lead = lambda c: (max_cycle - c) if (c is not None and max_cycle is not None) else None

        per_unit_rows.append(
            {
                "unit_id": uid,
                "max_cycle_observed": max_cycle,
                "first_risk_cycle": m.get("first_risk_cycle"),
                "first_decision_cycle": first_decision,
                "first_stable_hypothesis_cycle": m.get("first_stable_hypothesis_cycle"),
                "first_confidence_threshold_cycle": first_conf_cycle,
                "lead_from_first_risk_to_max": lead(m.get("first_risk_cycle")),
                "lead_from_first_decision_to_max": lead(first_decision),
                "lead_from_first_stable_hypothesis_to_max": lead(m.get("first_stable_hypothesis_cycle")),
                "lead_from_conf_threshold_to_max": lead(first_conf_cycle),
                "action_flip_count_post_warmup": action_flips,
                "avg_decision_conf_step_post_warmup": round(avg_dec_step, 4),
                "avg_hypothesis_conf_step_post_warmup": round(avg_hyp_step, 4),
                "attribution_causal_match_rate_post_warmup": round(match_rate, 4),
            }
        )

        usable_confidence = (first_conf_cycle is not None) and (avg_dec_step <= 0.08)
        early_signal = (first_decision is not None) and (lead(first_decision) is not None) and (lead(first_decision) >= 15)
        coherent = (action_flips <= 3) and (avg_hyp_step <= 0.10)

        usable_confidence_units += 1 if usable_confidence else 0
        early_signal_units += 1 if early_signal else 0
        coherent_units += 1 if coherent else 0

        summary_stats_rows.append(
            {
                "unit_id": uid,
                "early_signal": int(early_signal),
                "usable_confidence": int(usable_confidence),
                "coherent": int(coherent),
                "attribution_causal_match_rate_post_warmup": round(match_rate, 4),
            }
        )

    units_tested = len(per_unit_rows)

    unit_csv = args.output_dir / "fd001_broad_unit_milestones.csv"
    summary_csv = args.output_dir / "fd001_broad_summary.csv"
    report_md = args.output_dir / "fd001_broad_report.md"

    if per_unit_rows:
        with unit_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(per_unit_rows[0].keys()))
            writer.writeheader()
            writer.writerows(per_unit_rows)

    if summary_stats_rows:
        with summary_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_stats_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_stats_rows)

    match_rates = [float(r["attribution_causal_match_rate_post_warmup"]) for r in per_unit_rows]
    dec_steps = [float(r["avg_decision_conf_step_post_warmup"]) for r in per_unit_rows]
    hyp_steps = [float(r["avg_hypothesis_conf_step_post_warmup"]) for r in per_unit_rows]

    lines = [
        "# FD001 Broader Validation Sweep (Early-Warning Evidence)",
        "",
        f"- Units tested: {units_tested}",
        f"- Decision confidence threshold: {args.confidence_threshold:.2f}",
        f"- Warmup cycle floor for stability metrics: {args.warmup_cycles}",
        "",
        "## Early signal coverage",
        f"- Units with first decision at least 15 cycles before max observed cycle: {early_signal_units}/{units_tested} ({(100*early_signal_units/max(1, units_tested)):.1f}%)",
        "",
        "## Confidence usability",
        f"- Units reaching confidence threshold: {sum(1 for r in per_unit_rows if r['first_confidence_threshold_cycle'] is not None)}/{units_tested}",
        f"- Units with usable confidence profile (threshold reached + avg step <= 0.08): {usable_confidence_units}/{units_tested} ({(100*usable_confidence_units/max(1, units_tested)):.1f}%)",
        f"- Mean decision confidence step size (post-warmup): {(mean(dec_steps) if dec_steps else 0.0):.4f}",
        f"- Mean hypothesis confidence step size (post-warmup): {(mean(hyp_steps) if hyp_steps else 0.0):.4f}",
        "",
        "## Cross-unit coherence",
        f"- Units passing coherence rule (<=3 action flips and avg hypothesis step <=0.10): {coherent_units}/{units_tested} ({(100*coherent_units/max(1, units_tested)):.1f}%)",
        f"- Mean attribution↔causal match rate (post-warmup): {(mean(match_rates) if match_rates else 0.0):.3f}",
        "",
        "## Prototype credibility verdict",
        "- Credible early-warning prototype if early signal is common, confidence is stable enough for actioning, and outputs remain coherent across units.",
        f"- Result for this sweep: {'Supported' if (units_tested > 0 and early_signal_units/units_tested >= 0.7 and coherent_units/units_tested >= 0.7) else 'Partially supported'}.",
    ]
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"units_tested={units_tested}")
    print(f"unit_milestones_csv={unit_csv}")
    print(f"summary_csv={summary_csv}")
    print(f"report_md={report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
