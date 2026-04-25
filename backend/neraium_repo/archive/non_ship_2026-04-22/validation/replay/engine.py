from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass
class ReplayStepResult:
    timestep: int
    timestamp: float
    asset_id: str
    domain: str
    scenario_family: str
    scenario_id: str
    system_type: str
    novelty: float
    support_count: int
    drift_warning: bool
    predicted_state: dict[str, Any]
    recommended_intervention: str | None
    confidence: float
    law_usage: list[str]
    actual_intervention: str | None
    actual_outcome: str | None


class HistoricalReplayEngine:
    def __init__(self, decision_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.decision_fn = decision_fn

    @staticmethod
    def _float_or_default(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int_or_default(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def replay(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        step_logs: list[ReplayStepResult] = []
        trajectory_logs: dict[str, list[dict[str, Any]]] = {}

        for idx, row in enumerate(records):
            row = dict(row or {})
            observation = dict(row.get("observation") or {})
            observation["asset_id"] = row.get("asset_id", "unknown")
            # Feed replay metadata into the decision function so the platform can
            # apply the same cold-start / novelty / drift safeguards used in production.
            if "support_count" in row:
                observation["support_count"] = row.get("support_count")
            if "novelty" in row and "novelty_score" not in observation:
                observation["novelty_score"] = row.get("novelty")
            if "drift_warning" in row and "drift_warning" not in observation:
                observation["drift_warning"] = bool(row.get("drift_warning", False))
            output = self.decision_fn(observation)

            transition = dict(output.get("transition_dynamics") or {})
            intervention = dict((output.get("intervention_intelligence") or {}).get("recommendation") or {})
            best = dict(intervention.get("best_intervention") or {})
            recommended = best.get("name")
            confidence = self._float_or_default(
                best.get("confidence", (output.get("reliability_intelligence") or {}).get("risk_advisory", {}).get("calibrated_confidence", 0.0)),
                0.0,
            )
            confidence = max(0.0, min(1.0, confidence))
            governance = dict((output.get("structural_law_intelligence") or {}).get("structural_law_governance") or {})
            law_usage = [
                str(law.get("law_id"))
                for law in list(governance.get("laws") or [])
                if law.get("current_stage") != "rejected_or_falsified"
            ]

            step = ReplayStepResult(
                timestep=idx,
                timestamp=self._float_or_default(row.get("timestamp", idx), float(idx)),
                asset_id=str(row.get("asset_id", "unknown")),
                domain=str(row.get("domain") or row.get("vertical") or "unknown"),
                scenario_family=str(row.get("scenario_family") or row.get("scenario") or "unknown"),
                scenario_id=str(row.get("scenario_id") or f"{row.get('asset_id', 'unknown')}::{idx}"),
                system_type=str(row.get("system_type") or row.get("asset_type") or "unknown"),
                novelty=max(0.0, min(1.0, self._float_or_default(row.get("novelty"), 0.0))),
                support_count=max(0, self._int_or_default(row.get("support_count"), 0)),
                drift_warning=bool(row.get("drift_warning", False)),
                predicted_state=transition,
                recommended_intervention=str(recommended) if recommended else None,
                confidence=confidence,
                law_usage=law_usage,
                actual_intervention=row.get("actual_intervention"),
                actual_outcome=row.get("outcome_label"),
            )
            step_logs.append(step)
            trajectory_logs.setdefault(step.asset_id, []).append(asdict(step))

        return {
            "step_logs": [asdict(s) for s in step_logs],
            "trajectory_logs": trajectory_logs,
        }
