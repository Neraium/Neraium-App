from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_validation import execute_validation
from validation.corpus.registry import CorpusSnapshotRegistry
from validation.release_policy import CORPUS_TYPES, aggregate_multi_corpus_release, evaluate_corpus_release


def _resolve_corpus_ids(registry: CorpusSnapshotRegistry, corpus_id: str | None, corpus_set: str | None) -> list[str]:
    if corpus_set:
        values = [v.strip() for v in corpus_set.split(",") if v.strip()]
        resolved: list[str] = []
        for value in values:
            if value in CORPUS_TYPES:
                resolved.extend(registry.list_corpus_ids_by_type(value))
            else:
                resolved.append(value)
        dedup = []
        seen = set()
        for cid in resolved:
            if cid not in seen:
                dedup.append(cid)
                seen.add(cid)
        return dedup
    if corpus_id:
        return [corpus_id]
    raise ValueError("Either --corpus-id or --corpus-set must be provided")


def _run_one(args: argparse.Namespace, *, corpus_id: str, out_root: Path) -> dict[str, Any]:
    run_args = argparse.Namespace(
        input=None,
        format=None,
        corpus_id=corpus_id,
        corpus_root=args.corpus_root,
        output=str(out_root / corpus_id / "real_world_validation_report.json"),
        core_output=str(out_root / corpus_id / "core_validation_report.json"),
        release_gate_output=str(out_root / corpus_id / "release_gate_report.json"),
        prior_core_report=None,
        history_root=args.history_root,
        write_history=True,
        mark_baseline=args.mark_baseline,
    )
    report = execute_validation(run_args)
    ctype = str(report.get("core_validation_report", {}).get("corpus_source", {}).get("corpus_type") or "baseline_clean")
    per_corpus_gate = evaluate_corpus_release(report["core_validation_report"], corpus_type=ctype)
    return {
        "corpus_id": corpus_id,
        "corpus_type": ctype,
        "summary_metrics": report.get("core_validation_report", {}).get("summary", {}),
        "gate_breakdown": per_corpus_gate.get("gate_breakdown", []),
        "release_passed": bool(per_corpus_gate.get("release_passed")),
        "release_recommendation": per_corpus_gate.get("release_recommendation"),
        "blocking_reasons": per_corpus_gate.get("blocking_reasons", []),
        "failure_mode_tags": per_corpus_gate.get("failure_mode_tags", []),
        "policy_thresholds": per_corpus_gate.get("policy_thresholds", {}),
        "run_metadata": report.get("run_metadata", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run canonical release-candidate evaluation")
    parser.add_argument("--corpus-id", default=None)
    parser.add_argument("--corpus-set", default=None, help="Comma-separated corpus IDs and/or corpus types")
    parser.add_argument("--corpus-root", default="validation/corpus")
    parser.add_argument("--history-root", default="reports/validation/history")
    parser.add_argument("--output", default="reports/validation/real_world_validation_report.json")
    parser.add_argument("--core-output", default="reports/validation/core_validation_report.json")
    parser.add_argument("--release-gate-output", default="reports/validation/release_gate_report.json")
    parser.add_argument("--multi-corpus-output", default="reports/validation/multi_corpus_release_report.json")
    parser.add_argument("--mark-baseline", action="store_true")
    args = parser.parse_args()

    registry = CorpusSnapshotRegistry(root=Path(args.corpus_root))
    corpus_ids = _resolve_corpus_ids(registry, args.corpus_id, args.corpus_set)

    out_root = Path(args.output).resolve().parent / "release_candidate_runs"
    out_root.mkdir(parents=True, exist_ok=True)
    corpus_results = [_run_one(args, corpus_id=cid, out_root=out_root) for cid in corpus_ids]

    aggregate = aggregate_multi_corpus_release(corpus_results)
    status = "RELEASE_PASS" if aggregate.get("release_passed") else "RELEASE_FAIL"

    Path(args.multi_corpus_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.multi_corpus_output).write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    # backward-compatible single report outputs
    if len(corpus_results) == 1:
        single = corpus_results[0]
        Path(args.release_gate_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.release_gate_output).write_text(json.dumps(single, indent=2), encoding="utf-8")
        Path(args.core_output).write_text(json.dumps(single.get("summary_metrics", {}), indent=2), encoding="utf-8")

    print(status)
    print(
        json.dumps(
            {
                "status": status,
                "overall_release_decision": aggregate.get("release_recommendation"),
                "blocking_corpus_classes": aggregate.get("blocking_corpus_classes", []),
                "failing_corpora": aggregate.get("failing_corpora", []),
                "failure_mode_frequency": aggregate.get("failure_mode_frequency", {}),
                "corpus_results": [
                    {
                        "corpus_id": row.get("corpus_id"),
                        "corpus_type": row.get("corpus_type"),
                        "release_passed": row.get("release_passed"),
                        "failure_mode_tags": row.get("failure_mode_tags", []),
                    }
                    for row in corpus_results
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
