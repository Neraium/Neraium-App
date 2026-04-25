from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReleaseGateThresholds:
    min_decision_accuracy: float = 0.70
    max_harm_rate: float = 0.20
    min_calibration_quality: float = 0.65
    max_false_confidence_rate: float = 0.10
    max_drift_warning_rate: float = 0.25
    min_records: int = 50
    min_domain_count: int = 1
    min_asset_count: int = 3
    min_intervention_memory_contribution: float | None = None
    regression_accuracy_drop_limit: float = 0.03
    regression_harm_increase_limit: float = 0.02
    regression_calibration_drop_limit: float = 0.03
    regression_drift_increase_limit: float = 0.05


def _gate_result(name: str, passed: bool, observed: float | int | str | None, threshold: float | int | str | None, reason: str | None = None) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": passed,
        "observed": observed,
        "threshold": threshold,
        "reason": reason,
    }


def compare_against_previous(
    current_report: dict[str, Any],
    previous_report: dict[str, Any] | None,
    thresholds: ReleaseGateThresholds,
) -> dict[str, Any]:
    if not previous_report:
        return {
            "has_baseline": False,
            "regressions": [],
            "improvements": [],
            "release_regression_blockers": [],
        }

    current_summary = dict(current_report.get("summary") or {})
    prev_summary = dict(previous_report.get("summary") or {})

    metrics = {
        "decision_accuracy": (1.0, thresholds.regression_accuracy_drop_limit),
        "harm_rate": (-1.0, thresholds.regression_harm_increase_limit),
        "calibration_quality": (1.0, thresholds.regression_calibration_drop_limit),
        "drift_warning_rate": (-1.0, thresholds.regression_drift_increase_limit),
    }

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    blockers: list[str] = []

    for metric_name, (direction, limit) in metrics.items():
        current_value = float(current_summary.get(metric_name, 0.0) or 0.0)
        previous_value = float(prev_summary.get(metric_name, 0.0) or 0.0)
        delta = current_value - previous_value

        if direction > 0 and delta < 0:
            regressions.append({"metric": metric_name, "delta": round(delta, 6), "current": current_value, "previous": previous_value})
            if abs(delta) > limit:
                blockers.append(f"{metric_name} regression {delta:.4f} exceeds allowed drop {limit:.4f}")
        elif direction < 0 and delta > 0:
            regressions.append({"metric": metric_name, "delta": round(delta, 6), "current": current_value, "previous": previous_value})
            if delta > limit:
                blockers.append(f"{metric_name} regression +{delta:.4f} exceeds allowed increase {limit:.4f}")
        elif abs(delta) > 0:
            improvements.append({"metric": metric_name, "delta": round(delta, 6), "current": current_value, "previous": previous_value})

    return {
        "has_baseline": True,
        "regressions": regressions,
        "improvements": improvements,
        "release_regression_blockers": blockers,
    }


def evaluate_release_gates(
    core_validation_report: dict[str, Any],
    *,
    previous_core_report: dict[str, Any] | None = None,
    thresholds: ReleaseGateThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or ReleaseGateThresholds()
    summary = dict(core_validation_report.get("summary") or {})
    corpus = dict(core_validation_report.get("corpus_summary") or {})

    total_records = int(corpus.get("total_records", 0) or 0)
    domain_count = int(corpus.get("domain_count", 0) or 0)
    asset_count = int(corpus.get("asset_count", 0) or 0)

    decision_accuracy = float(summary.get("decision_accuracy", 0.0))
    harm_rate = float(summary.get("harm_rate", 1.0))
    calibration_quality = float(summary.get("calibration_quality", 0.0))
    false_confidence_rate = float(summary.get("false_confidence_rate", 1.0))
    drift_warning_rate = float(summary.get("drift_warning_rate", 1.0))
    intervention_memory = summary.get("intervention_memory_contribution")

    gates = [
        _gate_result(
            "minimum_data_volume",
            total_records >= thresholds.min_records,
            total_records,
            f">= {thresholds.min_records}",
            None if total_records >= thresholds.min_records else "Replay corpus too small for release confidence",
        ),
        _gate_result(
            "minimum_domain_coverage",
            domain_count >= thresholds.min_domain_count,
            domain_count,
            f">= {thresholds.min_domain_count}",
            None if domain_count >= thresholds.min_domain_count else "Insufficient domain coverage",
        ),
        _gate_result(
            "minimum_asset_coverage",
            asset_count >= thresholds.min_asset_count,
            asset_count,
            f">= {thresholds.min_asset_count}",
            None if asset_count >= thresholds.min_asset_count else "Insufficient asset coverage",
        ),
        _gate_result(
            "minimum_decision_accuracy",
            decision_accuracy >= thresholds.min_decision_accuracy,
            round(decision_accuracy, 6),
            f">= {thresholds.min_decision_accuracy}",
            None if decision_accuracy >= thresholds.min_decision_accuracy else "Decision accuracy below release floor",
        ),
        _gate_result(
            "maximum_harm_rate",
            harm_rate <= thresholds.max_harm_rate,
            round(harm_rate, 6),
            f"<= {thresholds.max_harm_rate}",
            None if harm_rate <= thresholds.max_harm_rate else "Harm rate exceeds safe operating bound",
        ),
        _gate_result(
            "minimum_calibration_quality",
            calibration_quality >= thresholds.min_calibration_quality,
            round(calibration_quality, 6),
            f">= {thresholds.min_calibration_quality}",
            None if calibration_quality >= thresholds.min_calibration_quality else "Calibration quality degraded below floor",
        ),
        _gate_result(
            "maximum_false_confidence_rate",
            false_confidence_rate <= thresholds.max_false_confidence_rate,
            round(false_confidence_rate, 6),
            f"<= {thresholds.max_false_confidence_rate}",
            None if false_confidence_rate <= thresholds.max_false_confidence_rate else "False-confidence rate exceeds limit",
        ),
        _gate_result(
            "maximum_drift_warning_rate",
            drift_warning_rate <= thresholds.max_drift_warning_rate,
            round(drift_warning_rate, 6),
            f"<= {thresholds.max_drift_warning_rate}",
            None if drift_warning_rate <= thresholds.max_drift_warning_rate else "Drift warning rate too high",
        ),
    ]

    if thresholds.min_intervention_memory_contribution is not None:
        observed = float(intervention_memory or 0.0)
        gates.append(
            _gate_result(
                "minimum_intervention_memory_contribution",
                observed >= thresholds.min_intervention_memory_contribution,
                round(observed, 6),
                f">= {thresholds.min_intervention_memory_contribution}",
                None if observed >= thresholds.min_intervention_memory_contribution else "Intervention-memory contribution below floor",
            )
        )

    regression = compare_against_previous(core_validation_report, previous_core_report, thresholds)
    if regression["release_regression_blockers"]:
        gates.append(
            _gate_result(
                "regression_guard",
                False,
                len(regression["release_regression_blockers"]),
                "0 blockers",
                "Regression blockers detected against previous validation report",
            )
        )

    blocking_reasons = [g["reason"] for g in gates if not g["passed"] and g.get("reason")]
    blocking_reasons.extend(regression["release_regression_blockers"])

    passed = all(g["passed"] for g in gates)
    recommendation = "ship" if passed else "no-ship"

    return {
        "release_passed": passed,
        "release_recommendation": recommendation,
        "gate_breakdown": gates,
        "blocking_reasons": blocking_reasons,
        "policy_thresholds": asdict(thresholds),
        "regression_analysis": regression,
    }
