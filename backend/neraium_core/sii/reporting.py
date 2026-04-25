from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .errors import SIIIOError


def results_to_json(results: list[dict[str, Any]]) -> str:
    return json.dumps(results, indent=2)


def write_json_report(path: str | Path, results: list[dict[str, Any]]) -> None:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(results_to_json(results), encoding="utf-8")
    except Exception as exc:
        raise SIIIOError(f"Failed to write JSON report: {p}") from exc


def results_to_csv_text(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    fields = [
        "timestamp",
        "site_id",
        "asset_id",
        "state",
        "interpreted_state",
        "confidence",
        "structural_drift_score",
        "relational_instability_score",
        "regime_distance",
        "coherence_score",
        "graph_deformation_score",
        "risk_level",
        "risk_trend",
        "inspection_target",
        "explanation",
    ]
    # csv.DictWriter needs file-like object; create via StringIO
    from io import StringIO

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for item in results:
        writer.writerow(
            {
                "timestamp": item.get("timestamp"),
                "site_id": item.get("site_id"),
                "asset_id": item.get("asset_id"),
                "state": item.get("state"),
                "interpreted_state": item.get("interpreted_state"),
                "confidence": item.get("confidence"),
                "structural_drift_score": item.get("structural_drift_score"),
                "relational_instability_score": item.get("relational_instability_score"),
                "regime_distance": item.get("regime_distance"),
                "coherence_score": item.get("coherence_score"),
                "graph_deformation_score": item.get("graph_deformation_score"),
                "risk_level": ((item.get("risk_assessment") or {}) if isinstance(item.get("risk_assessment"), dict) else {}).get(
                    "current_risk_level"
                ),
                "risk_trend": ((item.get("risk_assessment") or {}) if isinstance(item.get("risk_assessment"), dict) else {}).get(
                    "projected_near_term_trend"
                ),
                "inspection_target": (
                    ((item.get("operator_guidance") or {}) if isinstance(item.get("operator_guidance"), dict) else {}).get(
                        "first_inspection_target"
                    )
                ),
                "explanation": item.get("explanation"),
            }
        )
    return buf.getvalue()


def write_csv_report(path: str | Path, results: list[dict[str, Any]]) -> None:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(results_to_csv_text(results), encoding="utf-8")
    except Exception as exc:
        raise SIIIOError(f"Failed to write CSV report: {p}") from exc
