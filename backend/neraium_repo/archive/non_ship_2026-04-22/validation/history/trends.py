from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import pstdev
from typing import Any

from validation.history.tracker import load_history_index


def _series(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        out.append({"timestamp": row.get("timestamp"), "corpus_id": row.get("corpus_id"), "run_id": row.get("run_id"), "value": value})
    return out


def build_trend_summary(history_root: Path) -> dict[str, Any]:
    index = load_history_index(history_root)
    rows = list(index.get("runs", []))
    total = len(rows)
    release_pass = sum(1 for r in rows if r.get("release_passed"))

    regressions = 0
    by_corpus: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_corpus.setdefault(str(row.get("corpus_id")), []).append(row)

    for corpus_rows in by_corpus.values():
        ordered = sorted(corpus_rows, key=lambda r: r.get("timestamp", ""))
        prev = None
        for row in ordered:
            if prev and row.get("decision_accuracy") is not None and prev.get("decision_accuracy") is not None:
                if float(row["decision_accuracy"]) < float(prev["decision_accuracy"]):
                    regressions += 1
            prev = row

    return {
        "run_count": total,
        "accuracy_over_time": _series(rows, "decision_accuracy"),
        "harm_rate_over_time": _series(rows, "harm_rate"),
        "calibration_over_time": _series(rows, "calibration_quality"),
        "release_gate_pass_rate": round(release_pass / max(1, total), 6),
        "regression_frequency": round(regressions / max(1, total), 6),
    }


def build_multi_corpus_trend_summary(history_root: Path) -> dict[str, Any]:
    index = load_history_index(history_root)
    rows = sorted(index.get("runs", []), key=lambda r: r.get("timestamp", ""))
    by_corpus: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_corpus.setdefault(str(row.get("corpus_id")), []).append(row)

    per_corpus: dict[str, Any] = {}
    latest_accuracy_values: list[float] = []
    for corpus_id, corpus_rows in by_corpus.items():
        ordered = sorted(corpus_rows, key=lambda r: r.get("timestamp", ""))
        latest = ordered[-1]
        latest_acc = latest.get("decision_accuracy")
        if latest_acc is not None:
            latest_accuracy_values.append(float(latest_acc))
        per_corpus[corpus_id] = {
            "corpus_type": latest.get("corpus_type", "unknown"),
            "accuracy_over_time": _series(ordered, "decision_accuracy"),
            "harm_rate_over_time": _series(ordered, "harm_rate"),
            "pass_fail_over_time": [
                {"timestamp": r.get("timestamp"), "run_id": r.get("run_id"), "release_passed": bool(r.get("release_passed"))}
                for r in ordered
            ],
            "latest": {
                "decision_accuracy": latest.get("decision_accuracy"),
                "harm_rate": latest.get("harm_rate"),
                "release_passed": bool(latest.get("release_passed")),
            },
        }

    return {
        "run_count": len(rows),
        "per_corpus": per_corpus,
        "cross_corpus_stability": {
            "latest_accuracy_stddev": round(pstdev(latest_accuracy_values), 6) if len(latest_accuracy_values) > 1 else 0.0,
            "latest_accuracy_min": round(min(latest_accuracy_values), 6) if latest_accuracy_values else None,
            "latest_accuracy_max": round(max(latest_accuracy_values), 6) if latest_accuracy_values else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute validation trend summary from history index")
    parser.add_argument("--history-root", default="reports/validation/history")
    parser.add_argument("--output", default="reports/validation/history/trend_summary.json")
    parser.add_argument("--multi-output", default="reports/validation/history/multi_corpus_trend_summary.json")
    args = parser.parse_args()

    history_root = Path(args.history_root)
    summary = build_trend_summary(history_root)
    multi_summary = build_multi_corpus_trend_summary(history_root)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    multi_out = Path(args.multi_output)
    multi_out.parent.mkdir(parents=True, exist_ok=True)
    multi_out.write_text(json.dumps(multi_summary, indent=2), encoding="utf-8")

    print(str(out))
    print(str(multi_out))


if __name__ == "__main__":
    main()
