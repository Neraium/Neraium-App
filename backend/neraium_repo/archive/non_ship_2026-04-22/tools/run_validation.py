from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neraium_core.system_intelligence.law_governance import StructuralLawGovernance
from neraium_core.system_intelligence.platform import StructuralSystemIntelligencePlatform
from validation import RealWorldValidationPipeline
from validation.corpus import CorpusQualityError, CorpusSnapshotRegistry, build_run_context, compute_config_hash, load_records_for_run
from validation.history.tracker import record_validation_run, resolve_baseline_report
from validation.release_gates import evaluate_release_gates


def _build_feedback_rows(report: dict) -> list[dict]:
    rows = []
    for rec in report.get("feedback", []):
        rows.append(
            {
                "outcome_label": rec.get("outcome_label", "neutral"),
                "confidence": 0.8 if rec.get("action") == "accepted" else 0.4,
                "trajectory_family": "unknown",
                "transition_path": "unknown",
                "regime": "unknown",
                "novelty": 0.5,
                "support_count": 1,
            }
        )
    return rows


def _read_json_if_exists(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _annotate_artifacts(report: dict, run_context: dict, canonical_source: dict) -> None:
    release = report["release_gate_report"]
    release_meta = {
        "corpus_id": run_context["corpus_id"],
        "run_id": run_context["run_id"],
        "timestamp": run_context["timestamp"],
        "code_version": run_context["code_version"],
        "config_hash": run_context["config_hash"],
        "canonical_run": run_context["canonical"],
    }
    report["run_metadata"] = release_meta

    core = report["core_validation_report"]
    core["run_metadata"] = release_meta
    core["corpus_source"] = canonical_source["corpus"]
    core["release_decision"] = {
        "release_passed": release["release_passed"],
        "release_recommendation": release["release_recommendation"],
        "blocking_reasons": release["blocking_reasons"],
    }
    core["regression_comparison"] = release.get("regression_analysis", {})

    release["run_metadata"] = release_meta
    release["release_decision"] = {
        "release_passed": release["release_passed"],
        "release_recommendation": release["release_recommendation"],
        "blocking_reasons": release["blocking_reasons"],
    }
    release["regression_comparison"] = release.get("regression_analysis", {})
    release["corpus_id"] = run_context["corpus_id"]


def execute_validation(args: argparse.Namespace) -> dict:
    registry = CorpusSnapshotRegistry(root=Path(args.corpus_root))
    records, canonical_source, canonical = load_records_for_run(
        corpus_id=args.corpus_id,
        input_path=args.input,
        input_format=args.format,
        registry=registry,
    )

    config_hash = compute_config_hash(
        {
            "corpus_id": args.corpus_id,
            "input": args.input,
            "format": args.format,
            "corpus_root": str(args.corpus_root),
            "history_root": str(args.history_root),
        }
    )
    run_context = build_run_context(args.corpus_id or "non_canonical", canonical=canonical, config_hash=config_hash)

    platform = StructuralSystemIntelligencePlatform(operating_mode="production")
    law_governance = StructuralLawGovernance()
    pipeline = RealWorldValidationPipeline(decision_fn=platform.update)
    report = pipeline.run(records)

    intervention_memory = platform.production.intervention_intelligence.memory
    for rec in report.get("feedback", []):
        intervention_memory.ingest_feedback_event(
            intervention_type=str(rec.get("recommended_intervention") or "other"),
            action=str(rec.get("action") or "ignored"),
            outcome_label=str(rec.get("outcome_label") or "neutral"),
        )

    reliability = platform.production.reliability
    reliability.ingest_feedback_records(
        asset_id="validation_batch",
        step=len(records) + 1,
        feedback_records=_build_feedback_rows(report),
    )

    law_counts = defaultdict(lambda: {"helpful": 0, "harmful": 0, "neutral": 0})
    outcome_by_step = {o.get("timestep"): o for o in report.get("outcomes", [])}
    for step in report.get("replay", {}).get("step_logs", []):
        label = str((outcome_by_step.get(step.get("timestep"), {}) or {}).get("outcome_label", "neutral"))
        for law_id in step.get("law_usage", []) or []:
            if label not in {"helpful", "harmful", "neutral", "recovery-associated"}:
                label = "neutral"
            bucket = "helpful" if label in {"helpful", "recovery-associated"} else "harmful" if label == "harmful" else "neutral"
            law_counts[law_id][bucket] += 1

    law_validation_summary = {}
    for law_id, c in law_counts.items():
        evidence = law_governance.ingest_real_world_validation(
            law_id=law_id,
            helpful_count=c["helpful"],
            harmful_count=c["harmful"],
            neutral_count=c["neutral"],
        )
        law_validation_summary[law_id] = {
            "support_count": int(evidence["support_count"]),
            "contradiction_count": int(evidence["contradiction_count"]),
            "real_world_validation_score": round(float(evidence["validation_score"]), 6),
            "intervention_outcome_consistency": round(c["helpful"] / max(1, sum(c.values())), 6),
        }

    report["real_world_validation"]["law_validation"] = law_validation_summary
    report["core_validation_report"]["law_changes"] = [
        {
            "law_id": law_id,
            "support_count": row["support_count"],
            "contradiction_count": row["contradiction_count"],
            "real_world_validation_score": row["real_world_validation_score"],
        }
        for law_id, row in law_validation_summary.items()
    ][:25]
    report["evidence_summaries"] = {
        "intervention_memory": intervention_memory.support_summary(),
        "reliability_store": reliability.store.inspect(limit=32),
        "law_validation": law_validation_summary,
    }

    history_root = Path(args.history_root)
    baseline = resolve_baseline_report(history_root, run_context.corpus_id)
    if args.prior_core_report:
        baseline = _read_json_if_exists(Path(args.prior_core_report))

    release_gate = evaluate_release_gates(report["core_validation_report"], previous_core_report=baseline)
    report["release_gate_report"] = release_gate
    report["core_validation_report"]["release_gate_results"] = {
        "release_passed": release_gate["release_passed"],
        "release_recommendation": release_gate["release_recommendation"],
        "blocking_reasons": release_gate["blocking_reasons"],
    }
    report["core_validation_report"]["regression_analysis"] = release_gate["regression_analysis"]
    report["core_validation_report"]["release_regression_blockers"] = release_gate["regression_analysis"].get("release_regression_blockers", [])

    if not canonical:
        report["core_validation_report"]["non_canonical_reason"] = "raw_input_mode"
        report["release_gate_report"]["non_canonical_reason"] = "raw_input_mode"

    _annotate_artifacts(report, run_context.__dict__, canonical_source)

    platform.set_real_world_validation(report["real_world_validation"])

    out = Path(args.output)
    core_output_path = Path(args.core_output)
    release_out = Path(args.release_gate_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    core_output_path.parent.mkdir(parents=True, exist_ok=True)
    release_out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    core_output_path.write_text(json.dumps(report["core_validation_report"], indent=2), encoding="utf-8")
    release_out.write_text(json.dumps(release_gate, indent=2), encoding="utf-8")

    if args.write_history:
        record_validation_run(
            history_root=history_root,
            run_context=run_context.__dict__,
            core_validation_report=report["core_validation_report"],
            release_gate_report=report["release_gate_report"],
            real_world_report=report,
            mark_baseline=bool(args.mark_baseline),
        )

    print(str(out))
    print(str(core_output_path))
    print(str(release_out))
    print(f"run_id={run_context.run_id}")
    print(f"corpus_id={run_context.corpus_id}")
    print(f"release_recommendation={release_gate['release_recommendation']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-world replay + validation loop")
    parser.add_argument("--input", default=None, help="Path to dataset")
    parser.add_argument("--format", default=None, choices=["csv", "json", "event"], help="Dataset format")
    parser.add_argument("--corpus-id", default=None, help="Canonical corpus snapshot id")
    parser.add_argument("--corpus-root", default="validation/corpus", help="Corpus registry root")
    parser.add_argument("--output", default="reports/validation/real_world_validation_report.json", help="Output report path")
    parser.add_argument("--core-output", default="reports/validation/core_validation_report.json", help="Compact core validation artifact path")
    parser.add_argument("--release-gate-output", default="reports/validation/release_gate_report.json", help="Release gate report artifact path")
    parser.add_argument("--prior-core-report", default=None, help="Optional override baseline report path")
    parser.add_argument("--history-root", default="reports/validation/history")
    parser.add_argument("--write-history", action="store_true", help="Persist run artifacts under history root")
    parser.add_argument("--mark-baseline", action="store_true", help="Mark this run as explicit baseline")
    args = parser.parse_args()

    try:
        execute_validation(args)
    except CorpusQualityError as exc:
        detail = json.loads(str(exc))
        payload = {
            "release_passed": False,
            "release_recommendation": "no-ship",
            "blocking_reasons": ["insufficient_corpus_quality"],
            "corpus_quality": detail,
        }
        print(json.dumps(payload, indent=2))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
