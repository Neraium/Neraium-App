from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SystemState = Literal["NORMAL", "WATCH", "INTERVENE"]


@dataclass
class EscalationResult:
    state: SystemState
    zone: str | None
    confidence: float
    persistence: int
    progression: str  # "Increasing" | "Spreading" | "Stable"


class EscalationEngine:
    def __init__(
        self,
        watch_threshold: float = 0.35,
        intervene_threshold: float = 0.65,
        min_persistence_cycles: int = 5,
    ):
        self.watch_threshold = watch_threshold
        self.intervene_threshold = intervene_threshold
        self.min_persistence_cycles = min_persistence_cycles

    def evaluate(self, signal: dict) -> EscalationResult:
        drift = signal.get("structural_drift_score", 0.0)
        try:
            drift = float(drift)
        except (TypeError, ValueError):
            drift = 0.0

        persistence = signal.get("persistence", 0)
        try:
            persistence = int(persistence)
        except (TypeError, ValueError):
            persistence = 0

        zone = signal.get("dominant_zone")
        if zone is not None:
            zone = str(zone)

        progression = self._infer_progression(signal)

        # INTERVENE
        if drift >= self.intervene_threshold and persistence >= self.min_persistence_cycles:
            return EscalationResult(
                state="INTERVENE",
                zone=zone,
                confidence=drift,
                persistence=persistence,
                progression=progression,
            )

        # WATCH
        if drift >= self.watch_threshold:
            return EscalationResult(
                state="WATCH",
                zone=zone,
                confidence=drift,
                persistence=persistence,
                progression=progression,
            )

        return EscalationResult(
            state="NORMAL",
            zone=None,
            confidence=drift,
            persistence=persistence,
            progression="Stable",
        )

    def _infer_progression(self, signal: dict) -> str:
        trend = signal.get("drift_trend", 0)
        try:
            trend = float(trend)
        except (TypeError, ValueError):
            trend = 0.0

        if trend > 0.05:
            return "Increasing"
        if bool(signal.get("spread_detected")):
            return "Spreading"
        return "Stable"

