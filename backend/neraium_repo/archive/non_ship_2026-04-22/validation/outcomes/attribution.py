from __future__ import annotations

from typing import Any


class OutcomeAttributor:
    """Conservative attribution for intervention outcomes with delayed windows."""

    def __init__(
        self,
        *,
        window: int = 3,
        medium_window: int = 6,
        helpful_threshold: float = 0.1,
        harmful_threshold: float = -0.1,
    ) -> None:
        self.window = max(1, int(window))
        self.medium_window = max(self.window + 1, int(medium_window))
        self.helpful_threshold = float(helpful_threshold)
        self.harmful_threshold = float(harmful_threshold)

    def _fallback_from_predicted_state(self, row: dict[str, Any]) -> tuple[str, float]:
        state = dict(row.get("predicted_state") or {})
        escalation = float(state.get("escalation_probability", 0.5) or 0.5)
        reversibility = float(state.get("reversibility_score", 0.5) or 0.5)
        score = reversibility - escalation
        if score >= self.helpful_threshold:
            return "helpful", score
        if score <= self.harmful_threshold:
            return "harmful", score
        return "neutral", score

    @staticmethod
    def _step_score(row: dict[str, Any]) -> float:
        state = dict(row.get("predicted_state") or {})
        return float(state.get("reversibility_score", 0.5)) - float(state.get("escalation_probability", 0.5))

    def attribute(self, decision_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, row in enumerate(decision_logs):
            actual = row.get("actual_outcome")
            source = "explicit_outcome"
            attribution_confidence = 1.0
            assumptions = ["Observed outcomes are interpreted conservatively."]
            if actual in {"helpful", "neutral", "harmful", "recovery-associated"}:
                label = str(actual)
                score = 1.0 if label in {"helpful", "recovery-associated"} else -1.0 if label == "harmful" else 0.0
            else:
                short_scores: list[float] = []
                medium_scores: list[float] = []
                current_ts = float(row.get("timestamp", idx) or idx)
                for j in range(idx + 1, min(len(decision_logs), idx + self.medium_window + 1)):
                    future = decision_logs[j]
                    if future.get("asset_id") != row.get("asset_id"):
                        continue
                    future_ts = float(future.get("timestamp", j) or j)
                    if future_ts < current_ts:
                        continue
                    age = j - idx
                    step_score = self._step_score(future)
                    if age <= self.window:
                        short_scores.append(step_score)
                    elif age <= self.medium_window:
                        medium_scores.append(step_score)
                delayed_scores = short_scores + medium_scores
                if delayed_scores:
                    short_mean = sum(short_scores) / max(1, len(short_scores))
                    medium_mean = sum(medium_scores) / max(1, len(medium_scores)) if medium_scores else short_mean
                    score = 0.65 * short_mean + 0.35 * medium_mean
                    if score >= self.helpful_threshold:
                        label = "helpful"
                    elif score <= self.harmful_threshold:
                        label = "harmful"
                    elif any(s >= self.helpful_threshold * 0.8 for s in delayed_scores):
                        label = "recovery-associated"
                    else:
                        label = "neutral"
                    attribution_confidence = max(
                        0.35,
                        min(
                            0.9,
                            0.45
                            + 0.25 * min(1.0, len(short_scores) / max(1.0, float(self.window)))
                            + 0.20 * min(1.0, len(medium_scores) / max(1.0, float(self.medium_window - self.window))),
                        ),
                    )
                    source = "delayed_window_estimate"
                    assumptions.append("Delayed attribution is based on short/medium horizon trajectory deltas.")
                else:
                    label, score = self._fallback_from_predicted_state(row)
                    attribution_confidence = 0.3
                    source = "fallback_predicted_state"
                    assumptions.append("No delayed evidence available; fallback uses same-step predicted state only.")

            out.append({
                "timestep": row.get("timestep"),
                "asset_id": row.get("asset_id"),
                "recommended_intervention": row.get("recommended_intervention"),
                "actual_intervention": row.get("actual_intervention"),
                "outcome_label": label,
                "outcome_score": round(float(score), 6),
                "attribution_confidence": round(float(attribution_confidence), 6),
                "attribution_source": source,
                "attribution_assumptions": assumptions,
            })
        return out
