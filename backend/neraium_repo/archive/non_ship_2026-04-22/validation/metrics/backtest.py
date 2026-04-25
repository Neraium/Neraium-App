from __future__ import annotations

from typing import Any


def compute_backtest_metrics(decision_logs: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    if not decision_logs:
        return {
            "decision_alignment_with_successful_outcomes": 0.0,
            "intervention_success_rate_vs_operator": 0.0,
            "avoided_failures": 0,
            "false_confidence_events": 0,
            "calibration_under_real_world_noise": 0.0,
            "decision_accuracy": 0.0,
            "harm_rate": 0.0,
            "calibration_error": 0.0,
            "calibration": 0.0,
            "per_step": [],
        }

    outcome_by_step = {int(o.get("timestep", -1)): o for o in outcomes}
    per_step = []
    aligned_success = 0
    model_success = 0
    operator_success = 0
    avoided_failures = 0
    false_confidence = 0
    harms = 0

    for row in decision_logs:
        step = int(row.get("timestep", -1))
        outcome = outcome_by_step.get(step, {})
        label = str(outcome.get("outcome_label", "neutral"))
        confidence = float(row.get("confidence", 0.0) or 0.0)
        calibration_confidence = float(row.get("calibration_confidence", confidence) or confidence)
        rec = row.get("recommended_intervention")
        actual = row.get("actual_intervention")

        success = label in {"helpful", "recovery-associated"}
        harmful = label == "harmful"
        # Decision accuracy is binary: neutral counts as non-harmful (correct).
        accuracy_correct = 0.0 if harmful else 1.0
        # Calibration targets treat neutral/unknown outcomes as indeterminate.
        if success:
            calibration_target = 1.0
        elif harmful:
            calibration_target = 0.0
        else:
            calibration_target = 0.5

        if rec == actual and success:
            aligned_success += 1
        if rec and success:
            model_success += 1
        if actual and success:
            operator_success += 1
        if rec and actual and rec != actual and harmful:
            avoided_failures += 1
        if confidence >= 0.7 and harmful:
            false_confidence += 1
        if harmful:
            harms += 1

        per_step.append(
            {
                "timestep": step,
                "correct": accuracy_correct,
                "calibration_target": calibration_target,
                "confidence": confidence,
                "calibration_confidence": calibration_confidence,
                "outcome": label,
            }
        )

    n = len(decision_logs)
    calibration_error = sum(
        abs(float(r["calibration_confidence"]) - float(r["calibration_target"]))
        for r in per_step
    ) / n
    calibration = max(0.0, 1.0 - calibration_error)

    return {
        "decision_alignment_with_successful_outcomes": round(aligned_success / n, 6),
        "intervention_success_rate_vs_operator": round(model_success / max(1, operator_success), 6),
        "avoided_failures": avoided_failures,
        "false_confidence_events": false_confidence,
        "calibration_under_real_world_noise": round(calibration, 6),
        "decision_accuracy": round(sum(r["correct"] for r in per_step) / n, 6),
        "harm_rate": round(harms / n, 6),
        "calibration_error": round(calibration_error, 6),
        "calibration": round(calibration, 6),
        "per_step": per_step,
    }
