from __future__ import annotations

from collections import Counter
from typing import Any

from .schema import FeedbackRecord


class FeedbackIntegrator:
    def infer_feedback(self, decision_logs: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> list[FeedbackRecord]:
        outcome_by_step = {int(o.get("timestep", -1)): o for o in outcomes}
        records: list[FeedbackRecord] = []
        for row in decision_logs:
            step = int(row.get("timestep", -1))
            rec = row.get("recommended_intervention")
            actual = row.get("actual_intervention")
            if rec and actual and rec == actual:
                action = "accepted"
            elif rec and actual and rec != actual:
                action = "overridden"
            else:
                action = "ignored"

            outcome = outcome_by_step.get(step, {})
            records.append(
                FeedbackRecord(
                    timestep=step,
                    asset_id=str(row.get("asset_id", "unknown")),
                    recommended_intervention=rec,
                    actual_intervention=actual,
                    action=action,
                    outcome_label=outcome.get("outcome_label"),
                    trajectory_context={"law_usage": row.get("law_usage", []), "predicted_state": row.get("predicted_state", {})},
                )
            )
        return records

    def summarize(self, feedback: list[FeedbackRecord]) -> dict[str, Any]:
        action_counter = Counter(f.action for f in feedback)
        outcome_counter = Counter((f.outcome_label or "unknown") for f in feedback)
        return {
            "actions": dict(action_counter),
            "outcomes": dict(outcome_counter),
            "total": len(feedback),
        }
