from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FeedbackAction = Literal["accepted", "ignored", "overridden"]


@dataclass
class FeedbackRecord:
    timestep: int
    asset_id: str
    recommended_intervention: str | None
    actual_intervention: str | None
    action: FeedbackAction
    operator_confidence: float | None = None
    operator_rationale: str | None = None
    outcome_label: str | None = None
    trajectory_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
