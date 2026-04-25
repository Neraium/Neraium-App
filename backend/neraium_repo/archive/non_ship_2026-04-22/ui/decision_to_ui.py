"""
Integration layer: maps gate decision + records → UI state.

Core responsibility: transform decision engine output into decision-centric UI state.
No internal variables exposed. Only interpreted labels and decision output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class Severity(Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"


class Trajectory(Enum):
    STABLE = "Stable"
    DEGRADING = "Degrading"
    UNCERTAIN = "Uncertain"


class DegradationStage(Enum):
    BASELINE = "baseline"
    EARLY_SHIFT = "early_shift"
    EMERGING = "emerging"
    PERSISTENT = "persistent"
    ACCELERATED = "accelerated"
    FAILURE_APPROACH = "failure_approach"


class ActionHorizon(Enum):
    NOW = "now"
    SOON = "soon"
    WATCHLIST = "watchlist"


@dataclass(frozen=True)
class Point3D:
    """Position in 3D tetrahedron space."""
    x: float
    y: float
    z: float

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class TrailPoint:
    """Single point in the system trajectory."""
    position: Point3D
    timestamp: str
    frame_idx: int


@dataclass(frozen=True)
class PatternInsight:
    """Pattern matching insight (shown only if moderate+ confidence)."""
    tier: str  # "weak" | "moderate" | "strong"
    outcome_type: str  # e.g. "failure-progressing", "recovery", "neutral"
    influence_summary: str  # Human-readable summary


@dataclass(frozen=True)
class StatusHeader:
    """Top-level status at a glance."""
    degradation_stage: DegradationStage
    severity: Severity
    trajectory: Trajectory
    confidence: str  # "LOW" | "MEDIUM" | "HIGH"


@dataclass(frozen=True)
class ActionPanel:
    """Primary action: what to do now."""
    horizon: ActionHorizon
    primary_action: str
    urgency_level: int  # 1-5, where 5 is most urgent


@dataclass(frozen=True)
class TetrahedronState:
    """3D visualization state."""
    current_position: Point3D
    severity_scalar: float  # 0-1, drives coloring
    trail_points: list[TrailPoint]  # last 10-20 frames
    velocity: tuple[float, float, float]  # direction of movement
    nearest_vertex: str  # which structural dimension is dominant


@dataclass(frozen=True)
class DecisionTrace:
    """Why we made this decision."""
    primary_factor: str
    secondary_factors: list[str]
    confidence_rationale: str
    pattern_insight: Optional[PatternInsight] = None


@dataclass(frozen=True)
class TimelineStage:
    """Single stage in the progression."""
    stage: DegradationStage
    label: str
    is_current: bool


@dataclass(frozen=True)
class SystemTimeline:
    """Stage progression baseline → failure_approach."""
    stages: list[TimelineStage]
    current_index: int


@dataclass(frozen=True)
class ChartDataPoint:
    """Single data point for drift chart."""
    timestamp: str
    drift_score: float
    frame_idx: int


@dataclass(frozen=True)
class DriftChart:
    """Drift progression over last 24 cycles."""
    data_points: list[ChartDataPoint]
    detection_threshold: float = 0.2
    current_frame_idx: int = 0


@dataclass(frozen=True)
class DecisionUIState:
    """Complete UI state derived from decision."""
    status_header: StatusHeader
    action_panel: ActionPanel
    tetrahedron: TetrahedronState
    decision_trace: DecisionTrace
    timeline: SystemTimeline
    drift_chart: DriftChart
    timestamp: str


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _compute_degradation_stage(records: list[dict[str, Any]]) -> DegradationStage:
    """Map drift score + persistence to degradation stage."""
    if not records:
        return DegradationStage.BASELINE

    latest = records[-1]
    drift = _clamp(float(latest.get("structural_drift_score", 0.0)), 0.0, 1.0)
    persistence_minutes = float(latest.get("persistence_minutes", 0.0))

    # Stages based on drift and persistence
    if drift < 0.25:
        return DegradationStage.BASELINE
    elif drift < 0.40:
        return DegradationStage.EARLY_SHIFT
    elif drift < 0.55:
        return DegradationStage.EMERGING
    elif drift < 0.70 and persistence_minutes < 120:
        return DegradationStage.PERSISTENT
    elif drift < 0.85:
        return DegradationStage.ACCELERATED
    else:
        return DegradationStage.FAILURE_APPROACH


def _compute_severity(
    gate_decision: dict[str, Any],
    drift_score: float,
    stability_score: float,
) -> Severity:
    """Compute severity from decision confidence + drift/stability."""
    confidence_label = (gate_decision.get("confidence_label") or "LOW").upper()

    # Drift and instability contribute to severity
    instability = 1.0 - _clamp(stability_score)
    max_metric = max(drift_score, instability)

    # Decision + metrics → severity
    if confidence_label == "HIGH" and max_metric >= 0.6:
        return Severity.HIGH
    elif confidence_label == "HIGH" or max_metric >= 0.5:
        return Severity.ELEVATED
    elif confidence_label == "MEDIUM" or max_metric >= 0.3:
        return Severity.MODERATE
    else:
        return Severity.LOW


def _compute_trajectory(records: list[dict[str, Any]]) -> Trajectory:
    """Determine trajectory from recent drift changes."""
    if len(records) < 2:
        return Trajectory.STABLE

    latest = records[-1]
    previous = records[-2]

    delta_drift = float(latest.get("structural_drift_score", 0.0)) - float(
        previous.get("structural_drift_score", 0.0)
    )
    delta_stability = float(latest.get("relational_stability_score", 1.0)) - float(
        previous.get("relational_stability_score", 1.0)
    )

    # Degrading if drift increasing or stability decreasing
    if delta_drift > 0.08 or delta_stability < -0.08:
        return Trajectory.DEGRADING
    elif abs(delta_drift) > 0.03 or abs(delta_stability) > 0.03:
        return Trajectory.UNCERTAIN
    else:
        return Trajectory.STABLE


def _compute_tetrahedron_position(
    gate_decision: dict[str, Any],
    latest_record: dict[str, Any],
) -> Point3D:
    """Map decision + latest record → 3D point inside tetrahedron.

    Dimensions:
    - x: severity (0=center=low, 1=edge=high)
    - y: confidence (0=uncertain, 1=certain)
    - z: trajectory rate (0=stable, 1=rapidly changing)
    """
    # X-axis: severity
    confidence_label = (gate_decision.get("confidence_label") or "LOW").upper()
    drift = _clamp(float(latest_record.get("structural_drift_score", 0.0)))

    severity_x = (
        0.8 if confidence_label == "HIGH" else 0.5 if confidence_label == "MEDIUM" else 0.2
    )

    # Y-axis: confidence in the decision
    confidence_y = (
        0.85 if confidence_label == "HIGH" else 0.5 if confidence_label == "MEDIUM" else 0.2
    )

    # Z-axis: rate of change (trajectory)
    persistence_minutes = float(latest_record.get("persistence_minutes", 0.0))
    delta_drift = float(latest_record.get("delta_drift", 0.0))
    trajectory_z = min(1.0, (abs(delta_drift) * 2.0) + (persistence_minutes / 300.0))

    return Point3D(
        x=_clamp(severity_x),
        y=_clamp(confidence_y),
        z=_clamp(trajectory_z),
    )


def _nearest_tetrahedron_vertex(position: Point3D) -> str:
    """Find which structural dimension is nearest.

    Vertices:
    - STRUCTURAL: (1, 1, 1) - coherence & integrity
    - RELATIONAL: (1, -1, -1) - stability
    - TEMPORAL: (-1, -1, 1) - persistence
    - AUTHORITY: (-1, 1, -1) - confidence
    """
    vertices = {
        "STRUCTURAL": (1.0, 1.0, 1.0),
        "RELATIONAL": (1.0, -1.0, -1.0),
        "TEMPORAL": (-1.0, -1.0, 1.0),
        "AUTHORITY": (-1.0, 1.0, -1.0),
    }

    min_distance = float("inf")
    nearest = "STRUCTURAL"

    p = (position.x, position.y, position.z)
    for vertex_name, vertex_pos in vertices.items():
        distance = sum((a - b) ** 2 for a, b in zip(p, vertex_pos)) ** 0.5
        if distance < min_distance:
            min_distance = distance
            nearest = vertex_name

    return nearest


def _extract_primary_factor(
    gate_decision: dict[str, Any],
    latest_record: dict[str, Any],
) -> str:
    """Extract the single most important factor from decision."""
    # Priority: persistence > confidence > drift > stability
    persistence = float(latest_record.get("persistence_minutes", 0.0))
    drift = float(latest_record.get("structural_drift_score", 0.0))
    stability = float(latest_record.get("relational_stability_score", 1.0))
    coherence = float(latest_record.get("coherence_score", 0.0))

    if persistence > 60:
        return f"High severity persisted {int(persistence)} minutes"
    elif drift >= 0.6:
        return f"Structural drift reached {(drift * 100):.0f}%"
    elif stability < 0.4:
        return f"Relational stability dropped to {(stability * 100):.0f}%"
    else:
        return gate_decision.get("explanation", "System state change detected")


def _extract_secondary_factors(
    gate_decision: dict[str, Any],
    latest_record: dict[str, Any],
) -> list[str]:
    """Extract 1-2 secondary supporting factors."""
    factors = []
    corroborating = latest_record.get("corroborating_signal_count", 0)
    if corroborating > 0:
        factors.append(f"{int(corroborating)} corroborating signals")

    delta_drift = latest_record.get("delta_drift", 0.0)
    if abs(delta_drift) > 0.08:
        direction = "increasing" if delta_drift > 0 else "decreasing"
        factors.append(f"Drift {direction} by {(abs(delta_drift) * 100):.0f}%")

    return factors[:2]


def _extract_pattern_insight(
    gate_decision: dict[str, Any],
) -> Optional[PatternInsight]:
    """Extract pattern matching info (only if moderate+ confidence)."""
    pattern = gate_decision.get("pattern_match")
    if not isinstance(pattern, dict):
        return None

    tier = str(pattern.get("tier", "weak")).lower()
    if tier not in {"moderate", "strong"}:
        return None

    return PatternInsight(
        tier=tier,
        outcome_type=str(pattern.get("outcome_type", "unknown")),
        influence_summary=str(pattern.get("influence_summary", "")),
    )


def _build_trail(
    records: list[dict[str, Any]],
    gate_decision: dict[str, Any],
    limit: int = 20,
) -> list[TrailPoint]:
    """Build the trajectory trail from recent records."""
    trail = []
    for idx, record in enumerate(records[-limit:]):
        position = _compute_tetrahedron_position(gate_decision, record)
        timestamp = str(record.get("timestamp", ""))
        trail.append(
            TrailPoint(
                position=position,
                timestamp=timestamp,
                frame_idx=idx,
            )
        )
    return trail


def _build_timeline(records: list[dict[str, Any]]) -> SystemTimeline:
    """Build stage progression from records."""
    stages = []
    current_stage = _compute_degradation_stage(records)

    for stage in DegradationStage:
        is_current = stage == current_stage
        stages.append(
            TimelineStage(
                stage=stage,
                label=stage.value.replace("_", " ").upper(),
                is_current=is_current,
            )
        )

    return SystemTimeline(
        stages=stages,
        current_index=list(DegradationStage).index(current_stage),
    )


def _build_drift_chart(records: list[dict[str, Any]]) -> DriftChart:
    """Build drift chart data from last 24 records."""
    data_points = []
    for idx, record in enumerate(records[-24:]):
        data_points.append(
            ChartDataPoint(
                timestamp=str(record.get("timestamp", "")),
                drift_score=_clamp(float(record.get("structural_drift_score", 0.0))),
                frame_idx=idx,
            )
        )

    return DriftChart(
        data_points=data_points,
        current_frame_idx=len(data_points) - 1,
    )


def transform_decision_to_ui_state(
    gate_decision: dict[str, Any],
    records: list[dict[str, Any]],
) -> DecisionUIState:
    """Main entry point: transform decision + records → complete UI state.

    Args:
        gate_decision: Output from gate decision engine
        records: Historical telemetry records (most recent last)

    Returns:
        Complete UI state ready for rendering
    """
    if not records:
        # Fallback for empty records
        latest = {}
    else:
        latest = records[-1]

    # Extract base metrics
    drift_score = _clamp(float(latest.get("structural_drift_score", 0.0)))
    stability_score = _clamp(float(latest.get("relational_stability_score", 1.0)))
    timestamp = str(latest.get("timestamp", ""))

    # Build status header
    degradation_stage = _compute_degradation_stage(records)
    severity = _compute_severity(gate_decision, drift_score, stability_score)
    trajectory = _compute_trajectory(records)
    confidence_label = (gate_decision.get("confidence_label") or "LOW").upper()

    status_header = StatusHeader(
        degradation_stage=degradation_stage,
        severity=severity,
        trajectory=trajectory,
        confidence=confidence_label,
    )

    # Build action panel
    is_admitted = gate_decision.get("decision", "SUPPRESS").upper() == "ADMIT"
    is_high_severity = severity in {Severity.HIGH, Severity.ELEVATED}

    if is_admitted and is_high_severity:
        horizon = ActionHorizon.NOW
        urgency = 5
    elif is_admitted:
        horizon = ActionHorizon.SOON
        urgency = 3
    else:
        horizon = ActionHorizon.WATCHLIST
        urgency = 1

    primary_action = gate_decision.get("explanation", "Monitor system state")

    action_panel = ActionPanel(
        horizon=horizon,
        primary_action=primary_action,
        urgency_level=urgency,
    )

    # Build tetrahedron state
    current_position = _compute_tetrahedron_position(gate_decision, latest)
    velocity_magnitude = (
        abs(float(latest.get("delta_drift", 0.0))),
        abs(float(latest.get("delta_stability", 0.0))),
        abs(float(latest.get("persistence_minutes", 0.0)) / 100.0),
    )

    trail = _build_trail(records, gate_decision)
    severity_scalar = severity.value  # Map enum to scalar for coloring
    severity_scalars = {"LOW": 0.2, "MODERATE": 0.5, "ELEVATED": 0.75, "HIGH": 0.95}
    severity_scalar_float = severity_scalars.get(severity.value, 0.5)

    nearest_vertex = _nearest_tetrahedron_vertex(current_position)

    tetrahedron = TetrahedronState(
        current_position=current_position,
        severity_scalar=severity_scalar_float,
        trail_points=trail,
        velocity=velocity_magnitude,
        nearest_vertex=nearest_vertex,
    )

    # Build decision trace
    primary_factor = _extract_primary_factor(gate_decision, latest)
    secondary_factors = _extract_secondary_factors(gate_decision, latest)
    confidence_rationale = f"Confidence level: {confidence_label}"

    pattern_insight = _extract_pattern_insight(gate_decision)

    decision_trace = DecisionTrace(
        primary_factor=primary_factor,
        secondary_factors=secondary_factors,
        confidence_rationale=confidence_rationale,
        pattern_insight=pattern_insight,
    )

    # Build timeline
    timeline = _build_timeline(records)

    # Build drift chart
    drift_chart = _build_drift_chart(records)

    return DecisionUIState(
        status_header=status_header,
        action_panel=action_panel,
        tetrahedron=tetrahedron,
        decision_trace=decision_trace,
        timeline=timeline,
        drift_chart=drift_chart,
        timestamp=timestamp,
    )
