from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _index_path(history_root: Path) -> Path:
    return history_root / "index.json"


def load_history_index(history_root: Path) -> dict[str, Any]:
    path = _index_path(history_root)
    if not path.exists():
        return {"runs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_history_index(history_root: Path, index: dict[str, Any]) -> None:
    history_root.mkdir(parents=True, exist_ok=True)
    _index_path(history_root).write_text(json.dumps(index, indent=2), encoding="utf-8")


def resolve_baseline_report(history_root: Path, corpus_id: str, explicit_baseline_run_id: str | None = None) -> dict[str, Any] | None:
    index = load_history_index(history_root)
    runs = [r for r in index.get("runs", []) if r.get("corpus_id") == corpus_id]
    if not runs:
        return None

    selected = None
    if explicit_baseline_run_id:
        for row in runs:
            if row.get("run_id") == explicit_baseline_run_id:
                selected = row
                break
    if selected is None:
        explicit = [r for r in runs if r.get("is_baseline")]
        if explicit:
            selected = sorted(explicit, key=lambda r: r.get("timestamp", ""))[-1]
    if selected is None:
        passing = [r for r in runs if r.get("release_passed")]
        if passing:
            selected = sorted(passing, key=lambda r: r.get("timestamp", ""))[-1]

    if not selected:
        return None
    path = history_root / str(selected["core_validation_report_path"])
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def record_validation_run(
    *,
    history_root: Path,
    run_context: dict[str, Any],
    core_validation_report: dict[str, Any],
    release_gate_report: dict[str, Any],
    real_world_report: dict[str, Any],
    mark_baseline: bool = False,
) -> dict[str, Any]:
    corpus_id = str(run_context["corpus_id"])
    run_id = str(run_context["run_id"])
    timestamp = str(run_context["timestamp"])

    run_dir = history_root / corpus_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    core_rel = Path(corpus_id) / run_id / "core_validation_report.json"
    gate_rel = Path(corpus_id) / run_id / "release_gate_report.json"
    full_rel = Path(corpus_id) / run_id / "real_world_validation_report.json"

    (history_root / core_rel).write_text(json.dumps(core_validation_report, indent=2), encoding="utf-8")
    (history_root / gate_rel).write_text(json.dumps(release_gate_report, indent=2), encoding="utf-8")
    (history_root / full_rel).write_text(json.dumps(real_world_report, indent=2), encoding="utf-8")

    summary = dict(core_validation_report.get("summary") or {})
    index = load_history_index(history_root)
    for row in index.get("runs", []):
        if row.get("corpus_id") == corpus_id and row.get("is_baseline") and mark_baseline:
            row["is_baseline"] = False

    corpus_source = dict(core_validation_report.get("corpus_source") or {})

    row = {
        "corpus_id": corpus_id,
        "run_id": run_id,
        "timestamp": timestamp,
        "canonical": bool(run_context.get("canonical", False)),
        "release_passed": bool(release_gate_report.get("release_passed", False)),
        "release_recommendation": release_gate_report.get("release_recommendation"),
        "decision_accuracy": summary.get("decision_accuracy"),
        "harm_rate": summary.get("harm_rate"),
        "calibration_quality": summary.get("calibration_quality"),
        "core_validation_report_path": str(core_rel),
        "release_gate_report_path": str(gate_rel),
        "real_world_report_path": str(full_rel),
        "is_baseline": bool(mark_baseline),
        "corpus_type": corpus_source.get("corpus_type", "unknown"),
    }
    index.setdefault("runs", []).append(row)
    index["runs"] = sorted(index["runs"], key=lambda r: (r.get("timestamp", ""), r.get("run_id", "")))
    _save_history_index(history_root, index)
    return row
