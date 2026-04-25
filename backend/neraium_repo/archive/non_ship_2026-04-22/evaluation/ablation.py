from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.metrics import compute_metrics
from evaluation.runner import NeraiumModel, _record_from_prediction
from evaluation.scenarios import Scenario, build_benchmark_scenarios


ABLATION_COMPONENTS = {
    "trajectory_intelligence": "trajectory intelligence",
    "law_engine": "law extraction / law engine",
    "intervention_memory": "intervention intelligence memory",
    "reliability_calibration": "reliability/calibration layer",
    "cross_system_transfer": "cross-system transfer",
    "advisory_layers": "advisory layers",
}


def _success(metrics: dict[str, Any]) -> float:
    decision = float((metrics.get("decision_quality") or {}).get("success_rate", 0.0))
    harmful = float((metrics.get("decision_quality") or {}).get("harmful_intervention_rate", 0.0))
    brier = float((metrics.get("calibration") or {}).get("brier_score", 0.0))
    return decision - 0.5 * harmful - 0.25 * brier


def run_ablation_suite(
    scenarios: list[Scenario] | None = None,
    output_dir: str | Path = "reports/evaluation",
) -> dict[str, Any]:
    scenarios = scenarios or build_benchmark_scenarios()
    full_model = NeraiumModel(model_id="neraium_full_stack", component_flags={})

    full_records = [_record_from_prediction(s, full_model.predict(s)) for s in scenarios]
    baseline_metrics = compute_metrics(full_records)["neraium_full_stack"]
    baseline_success = _success(baseline_metrics)

    deltas: list[dict[str, Any]] = []
    for component_key, component_name in ABLATION_COMPONENTS.items():
        flags = {k: True for k in ABLATION_COMPONENTS}
        flags[component_key] = False
        model = NeraiumModel(model_id=f"ablation_without_{component_key}", component_flags=flags)
        records = [_record_from_prediction(s, model.predict(s)) for s in scenarios]
        metrics = compute_metrics(records)[model.model_id]
        success = _success(metrics)
        deltas.append(
            {
                "component": component_name,
                "key": component_key,
                "success_rate_full": baseline_success,
                "success_rate_ablated": success,
                "delta_success_rate": success - baseline_success,
                "harmful_rate_ablated": (metrics.get("decision_quality") or {}).get("harmful_intervention_rate", 0.0),
                "transfer_delta_ablated": (metrics.get("transfer_performance") or {}).get("transfer_delta", 0.0),
                "robustness_delta_ablated": (metrics.get("robustness") or {}).get("robustness_delta", 0.0),
            }
        )

    deltas.sort(key=lambda x: x["delta_success_rate"])
    report = {
        "baseline": baseline_metrics,
        "performance_delta_per_component": deltas,
        "component_importance_report": {
            "most_important_component": deltas[0]["component"] if deltas else None,
            "largest_drop": deltas[0]["delta_success_rate"] if deltas else 0.0,
        },
    }

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ablation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


__all__ = ["ABLATION_COMPONENTS", "run_ablation_suite"]
