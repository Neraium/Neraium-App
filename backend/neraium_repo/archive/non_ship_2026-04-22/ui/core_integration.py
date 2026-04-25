from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from neraium_core.gate.engine import AletheiasGate
from neraium_core.gate.schema import GateInput

from .config import UIConfig
from .utils import clamp, l2_norm, parse_iso8601, safe_float


@dataclass(frozen=True)
class TrajectoryPoint:
    x: float
    y: float
    t: str


@dataclass(frozen=True)
class StructuralEdge:
    source: str
    target: str
    strength: float
    trend: str


@dataclass(frozen=True)
class TimelineEvent:
    t: str
    regime: str
    drift_delta: float
    reaction_window_minutes: float


@dataclass(frozen=True)
class SystemState:
    position: TrajectoryPoint
    velocity: tuple[float, float]
    trajectory_history: list[TrajectoryPoint]
    projected_cone: list[TrajectoryPoint]
    stability_regions: dict[str, tuple[float, float]]
    structural_relationships: list[StructuralEdge]
    timeline: list[TimelineEvent]
    drift_intensity: float
    regime_state: str
    system_health: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": asdict(self.position),
            "velocity": {"dx": self.velocity[0], "dy": self.velocity[1]},
            "trajectory_history": [asdict(p) for p in self.trajectory_history],
            "projected_cone": [asdict(p) for p in self.projected_cone],
            "stability_regions": self.stability_regions,
            "structural_relationships": [asdict(e) for e in self.structural_relationships],
            "timeline": [asdict(e) for e in self.timeline],
            "drift_intensity": self.drift_intensity,
            "regime_state": self.regime_state,
            "system_health": self.system_health,
            "confidence": self.confidence,
        }


def _point_from_row(row: dict[str, Any], fallback_t: str) -> TrajectoryPoint:
    drift = clamp(safe_float(row.get("structural_drift_score"), 0.0), 0.0, 1.0)
    stability_loss = 1.0 - clamp(safe_float(row.get("relational_stability_score"), 1.0), 0.0, 1.0)
    return TrajectoryPoint(x=round(drift, 6), y=round(stability_loss, 6), t=str(row.get("timestamp") or fallback_t))


def _velocity(points: list[TrajectoryPoint]) -> tuple[float, float]:
    if len(points) < 2:
        return (0.0, 0.0)
    return (round(points[-1].x - points[-2].x, 6), round(points[-1].y - points[-2].y, 6))


def _projected_cone(anchor: TrajectoryPoint, velocity: tuple[float, float], steps: int) -> list[TrajectoryPoint]:
    vx, vy = velocity
    spread = max(0.02, l2_norm((vx, vy)) * 0.3)
    projection: list[TrajectoryPoint] = []
    for i in range(1, steps + 1):
        step_weight = i / max(steps, 1)
        projection.append(
            TrajectoryPoint(
                x=clamp(anchor.x + (vx * i) + spread * step_weight, 0.0, 1.0),
                y=clamp(anchor.y + (vy * i) - spread * step_weight, 0.0, 1.0),
                t=f"+{i}",
            )
        )
    return projection


def _optional_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


def classify_transition(previous: dict[str, Any] | None, current: dict[str, Any] | None) -> dict[str, float | str]:
    prev = previous or {}
    curr = current or {}
    if not previous:
        return {
            "type": "STABLE",
            "delta_drift": 0.0,
            "delta_stability": 0.0,
            "delta_coherence": 0.0,
        }

    prev_drift = safe_float(prev.get("structural_drift_score", prev.get("drift")), 0.0)
    curr_drift = safe_float(curr.get("structural_drift_score", curr.get("drift")), 0.0)
    prev_stability = safe_float(prev.get("relational_stability_score", prev.get("stability")), 1.0)
    curr_stability = safe_float(curr.get("relational_stability_score", curr.get("stability")), 1.0)
    prev_coherence = safe_float(prev.get("coherence_score"), 0.0)
    curr_coherence = safe_float(curr.get("coherence_score"), 0.0)

    delta_drift = round(curr_drift - prev_drift, 6)
    delta_stability = round(curr_stability - prev_stability, 6)
    delta_coherence = round(curr_coherence - prev_coherence, 6)
    movement_magnitude = abs(delta_drift) + abs(delta_stability) + abs(delta_coherence)

    transition_type = "STABLE"
    if movement_magnitude > 0.35:
        transition_type = "REORGANIZATION"
    elif movement_magnitude > 0.08:
        transition_type = "TRANSITION"

    return {
        "type": transition_type,
        "delta_drift": delta_drift,
        "delta_stability": delta_stability,
        "delta_coherence": delta_coherence,
    }


def build_gate_input_from_state(
    latest_row: dict[str, Any] | None,
    previous_row: dict[str, Any] | None = None,
    current_state: SystemState | None = None,
) -> GateInput:
    row = latest_row or {}
    previous = previous_row or {}
    state = current_state
    fallback_ts = parse_iso8601(None).isoformat()

    drift_from_state = state.drift_intensity if state is not None else None
    stability_from_state = (1.0 - state.position.y) if state is not None else None

    return GateInput(
        timestamp=str(row.get("timestamp") or (state.position.t if state is not None else fallback_ts)),
        asset_id=str(row.get("asset_id") or row.get("unit_id") or row.get("system_id") or "neraium-system"),
        site_id=str(row.get("site_id")) if row.get("site_id") is not None else None,
        drift_score=_optional_float(row.get("structural_drift_score", row.get("drift", drift_from_state))),
        stability_score=_optional_float(row.get("relational_stability_score", row.get("stability", stability_from_state))),
        coherence_score=_optional_float(row.get("coherence_score")),
        snr_score=_optional_float(row.get("snr_score")),
        persistence_minutes=_optional_float(row.get("persistence_minutes")),
        corroborating_signal_count=int(safe_float(row.get("corroborating_signal_count"), 0))
        if row.get("corroborating_signal_count") is not None
        else None,
        context_flags=row.get("context_flags") if isinstance(row.get("context_flags"), dict) else {},
        candidate_assertion=str(row.get("candidate_assertion") or "Observed structural state under admitted telemetry."),
        raw_metrics={
            "confidence": _optional_float(row.get("confidence_score", row.get("confidence"))),
            "system_health": row.get("system_health"),
            "regime": row.get("regime_name") or row.get("state"),
        },
        current=row,
        previous=previous,
        system_state=state.to_dict() if state is not None else None,
    )


def evaluate_gate(
    latest_row: dict[str, Any] | None,
    previous_row: dict[str, Any] | None = None,
    current_state: SystemState | None = None,
) -> dict[str, Any]:
    gate = AletheiasGate()
    gate_input = build_gate_input_from_state(latest_row, previous_row, current_state)
    decision = gate.evaluate(gate_input)
    payload = asdict(decision)
    payload["timestamp"] = str(gate_input.timestamp)
    payload["transition"] = classify_transition(previous_row, latest_row)
    return payload


def build_system_state(records: list[dict[str, Any]] | None, *, config: UIConfig) -> SystemState:
    rows = records or [{}]
    fallback_t = parse_iso8601(None).isoformat()
    history = [_point_from_row(row, fallback_t) for row in rows][-config.trajectory_tail :]
    position = history[-1]
    velocity = _velocity(history)

    latest = rows[-1]
    regime = str(latest.get("regime_name") or latest.get("state") or "baseline")
    health = str(latest.get("system_health") or "nominal")
    confidence = clamp(safe_float(latest.get("confidence_score", latest.get("confidence", 0.0))), 0.0, 1.0)
    drift = position.x

    relationships = [
        StructuralEdge("baseline_cluster", "current_cluster", round(max(0.0, 1.0 - drift), 4), "weakening" if velocity[0] > 0 else "stable"),
        StructuralEdge("correlation_core", "causal_frontier", round(max(0.0, 1.0 - position.y), 4), "weakening" if velocity[1] > 0 else "strengthening"),
    ]

    timeline: list[TimelineEvent] = []
    for idx, point in enumerate(history):
        prev = history[idx - 1] if idx > 0 else point
        timeline.append(
            TimelineEvent(
                t=point.t,
                regime=regime,
                drift_delta=round(point.x - prev.x, 6),
                reaction_window_minutes=round(max(1.0, config.reaction_window_default_minutes * (1.0 - point.x)), 2),
            )
        )

    return SystemState(
        position=position,
        velocity=velocity,
        trajectory_history=history,
        projected_cone=_projected_cone(position, velocity, config.projection_horizon_steps),
        stability_regions={
            "stable_basin": (0.0, 0.35),
            "transition_band": (0.35, 0.65),
            "divergence_zone": (0.65, 1.0),
        },
        structural_relationships=relationships,
        timeline=timeline,
        drift_intensity=drift,
        regime_state=regime,
        system_health=health,
        confidence=confidence,
    )
