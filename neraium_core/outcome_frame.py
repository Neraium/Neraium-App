"""Central Neraium decision output object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class NeraiumOutcomeFrame:
    state: str
    what_changed: str
    where_changed: str
    trajectory: Dict[str, Any]
    future_paths: List[Dict[str, Any]]
    decision: Dict[str, Any]
    confidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "what_changed": self.what_changed,
            "where_changed": self.where_changed,
            "trajectory": dict(self.trajectory),
            "future_paths": [dict(path) for path in self.future_paths],
            "decision": dict(self.decision),
            "confidence": {
                "level": self.confidence.get("level"),
                "basis": list(self.confidence.get("basis") or []),
            },
        }


def outcome_frame_from_dict(payload: Dict[str, Any]) -> NeraiumOutcomeFrame:
    return NeraiumOutcomeFrame(
        state=str(payload.get("state") or "STABLE"),
        what_changed=str(payload.get("what_changed") or ""),
        where_changed=str(payload.get("where_changed") or ""),
        trajectory=dict(payload.get("trajectory") or {}),
        future_paths=list(payload.get("future_paths") or []),
        decision=dict(payload.get("decision") or {}),
        confidence=dict(payload.get("confidence") or {}),
    )
