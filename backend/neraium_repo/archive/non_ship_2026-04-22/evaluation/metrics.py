from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationRecord:
    model_id: str
    scenario_id: str
    scenario_type: str
    domain: str
    variant: str
    predicted_risk: float
    predicted_unstable: bool
    first_alert_step: int | None
    recommended_intervention: str
    confidence: float
    calibration_probability: float
    intervention_effect: str
    critical_step: int | None
    actual_unstable: bool


def _bucket(p: float, bins: int = 5) -> int:
    p = max(0.0, min(0.999999, float(p)))
    return int(p * bins)


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def compute_metrics(records: list[EvaluationRecord]) -> dict[str, Any]:
    by_model: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for rec in records:
        by_model[rec.model_id].append(rec)

    report: dict[str, Any] = {}
    for model_id, rows in by_model.items():
        n = len(rows)
        helpful = sum(1 for r in rows if r.intervention_effect == "helpful")
        harmful = sum(1 for r in rows if r.intervention_effect == "harmful")
        neutral = sum(1 for r in rows if r.intervention_effect == "neutral")

        lead_times = [
            (r.critical_step - r.first_alert_step)
            for r in rows
            if r.critical_step is not None and r.first_alert_step is not None
        ]
        false_positive_den = sum(1 for r in rows if r.scenario_id.startswith("stable_system"))
        false_positive_num = sum(1 for r in rows if r.scenario_id.startswith("stable_system") and r.predicted_unstable)

        brier = sum((r.calibration_probability - (1.0 if r.actual_unstable else 0.0)) ** 2 for r in rows) / max(1, n)

        buckets: dict[int, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "expected": 0.0, "observed": 0.0})
        for r in rows:
            idx = _bucket(r.calibration_probability)
            buckets[idx]["count"] += 1.0
            buckets[idx]["expected"] += r.calibration_probability
            buckets[idx]["observed"] += 1.0 if r.actual_unstable else 0.0

        calibration_curve = []
        for idx in sorted(buckets):
            count = buckets[idx]["count"]
            calibration_curve.append(
                {
                    "bucket": idx,
                    "count": int(count),
                    "expected_accuracy": _safe_div(buckets[idx]["expected"], count),
                    "observed_accuracy": _safe_div(buckets[idx]["observed"], count),
                }
            )

        non_transfer = [r for r in rows if "cross_domain_transfer_case" not in r.scenario_id]
        transfer = [r for r in rows if "cross_domain_transfer_case" in r.scenario_id]
        non_transfer_success = _safe_div(sum(1 for r in non_transfer if r.intervention_effect == "helpful"), len(non_transfer))
        transfer_success = _safe_div(sum(1 for r in transfer if r.intervention_effect == "helpful"), len(transfer))

        base_variant = [r for r in rows if r.variant == "base"]
        noisy_variant = [r for r in rows if r.variant in {"noise", "missing"}]
        base_success = _safe_div(sum(1 for r in base_variant if r.intervention_effect == "helpful"), len(base_variant))
        noisy_success = _safe_div(sum(1 for r in noisy_variant if r.intervention_effect == "helpful"), len(noisy_variant))

        confusion = {
            "tp": sum(1 for r in rows if r.predicted_unstable and r.actual_unstable),
            "tn": sum(1 for r in rows if (not r.predicted_unstable) and (not r.actual_unstable)),
            "fp": sum(1 for r in rows if r.predicted_unstable and (not r.actual_unstable)),
            "fn": sum(1 for r in rows if (not r.predicted_unstable) and r.actual_unstable),
        }

        report[model_id] = {
            "decision_quality": {
                "success_rate": _safe_div(helpful, n),
                "harmful_intervention_rate": _safe_div(harmful, n),
                "neutral_intervention_rate": _safe_div(neutral, n),
            },
            "early_warning_utility": {
                "lead_time_before_critical": _safe_div(sum(lead_times), len(lead_times)),
                "covered_critical_cases": len(lead_times),
            },
            "false_positive_rate": _safe_div(false_positive_num, false_positive_den),
            "calibration": {
                "brier_score": brier,
                "calibration_curve": calibration_curve,
            },
            "transfer_performance": {
                "train_domain_success_rate": non_transfer_success,
                "cross_domain_success_rate": transfer_success,
                "transfer_delta": transfer_success - non_transfer_success,
            },
            "robustness": {
                "base_success_rate": base_success,
                "noise_missing_success_rate": noisy_success,
                "robustness_delta": noisy_success - base_success,
            },
            "confusion_matrix": confusion,
            "num_scenarios": n,
        }

    return report


__all__ = ["EvaluationRecord", "compute_metrics"]
