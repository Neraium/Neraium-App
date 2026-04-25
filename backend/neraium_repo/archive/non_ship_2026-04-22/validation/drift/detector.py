from __future__ import annotations

from typing import Any


class DriftDetector:
    def __init__(self, *, window: int = 10, degradation_threshold: float = 0.15) -> None:
        self.window = max(3, int(window))
        self.degradation_threshold = float(degradation_threshold)

    def detect(self, metrics_by_step: list[dict[str, Any]]) -> dict[str, Any]:
        if len(metrics_by_step) < self.window:
            return {"status": "insufficient_history", "warnings": [], "actions": []}

        early = metrics_by_step[: self.window]
        late = metrics_by_step[-self.window :]

        early_acc = sum(float(r.get("correct", 0.0)) for r in early) / len(early)
        late_acc = sum(float(r.get("correct", 0.0)) for r in late) / len(late)
        early_conf = sum(float(r.get("confidence", 0.0)) for r in early) / len(early)
        late_conf = sum(float(r.get("confidence", 0.0)) for r in late) / len(late)

        warnings: list[str] = []
        actions: list[str] = []
        if early_acc - late_acc > self.degradation_threshold:
            warnings.append("performance_degradation_detected")
            actions.append("review_recent_failed_decisions_and_context_shift")
        if late_conf > early_conf + 0.1 and late_acc < early_acc:
            warnings.append("confidence_rising_while_accuracy_falls")
            actions.append("tighten_confidence_thresholds_and_require_operator_confirmation")
        if late_acc < 0.45 and len(late) >= max(5, self.window // 2):
            warnings.append("low_recent_accuracy")
            actions.append("temporarily_fallback_to_conservative_monitoring")

        return {
            "status": "drift_detected" if warnings else "stable",
            "accuracy_delta": round(late_acc - early_acc, 6),
            "confidence_delta": round(late_conf - early_conf, 6),
            "warnings": warnings,
            "actions": actions,
        }
