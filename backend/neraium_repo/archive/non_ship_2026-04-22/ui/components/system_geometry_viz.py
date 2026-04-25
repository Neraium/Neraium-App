"""System Geometry Visualization: Structural representation of system relationships.

Replaces the line chart with a geometric view showing:
- Nodes: Sensors or functional units
- Edges: Relationships/coupling between nodes
- Structure deformation: Reflects stability vs. drift
- Trails: Prior stable states leave subtle geometric markers

Visual encoding:
- Tight, clustered structure = Stable
- Deformed structure = Drift
- Transitioning structure = Active change
- Settled structure = New equilibrium

GEOMETRY ANIMATION:
- Nodes move smoothly between frames using easing functions
- Drift intensity applies spring-like deformation
- Velocity vector pulls structure in direction of phase change
- Smooth interpolation prevents twitching/snapping
"""

from __future__ import annotations

import math
from typing import Any

from ui.utils import clamp, safe_float


def _ease_out_cubic(t: float) -> float:
    """Smooth cubic easing function (out).

    Used for animations between frames to create premium feel.
    t is in range [0, 1].
    """
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between two values.

    Args:
        a: Start value
        b: End value
        t: Interpolation factor [0, 1]

    Returns:
        Interpolated value
    """
    return a + (b - a) * clamp(t, 0.0, 1.0)


def _spring_damping(velocity: float, damping: float = 0.92) -> float:
    """Apply damping to velocity for spring-like motion.

    Args:
        velocity: Current velocity magnitude
        damping: Damping coefficient (0.0-1.0)

    Returns:
        Damped velocity
    """
    return velocity * clamp(damping, 0.0, 1.0)


def _generate_sensor_nodes(num_sensors: int = 8) -> list[dict[str, Any]]:
    """Generate a regular arrangement of sensor nodes in a circle.

    Args:
        num_sensors: Number of sensors (nodes) to arrange

    Returns:
        List of node positions in normalized [0, 1] space
    """
    nodes = []
    for i in range(num_sensors):
        angle = (i / num_sensors) * 2 * math.pi
        # Arrange in circle with center offset to create visual interest
        x = 0.5 + 0.35 * math.cos(angle)
        y = 0.5 + 0.35 * math.sin(angle)
        nodes.append({
            "id": f"sensor_{i}",
            "index": i,
            "x": clamp(x, 0.0, 1.0),
            "y": clamp(y, 0.0, 1.0),
            "label": f"S{i+1}",
            "base_x": x,
            "base_y": y,
        })
    return nodes


def _compute_smooth_velocity(current_drift: float, previous_drift: float, transition_type: str) -> tuple[float, float]:
    """Compute smooth velocity vector based on drift progression and transition type.

    This creates directional deformation without raw 1:1 mapping.
    - Stable to Transition: velocity increases, pulls nodes outward
    - Transition to Reorganization: high velocity, strong directional pull
    - Reorganization to Stable: velocity decreases, nodes settle inward

    Args:
        current_drift: Current drift intensity [0, 1]
        previous_drift: Previous frame drift intensity [0, 1]
        transition_type: "STABLE", "TRANSITION", or "REORGANIZATION"

    Returns:
        Velocity vector (vx, vy) with magnitude reflecting phase
    """
    drift_delta = current_drift - previous_drift

    # Base velocity magnitude
    if transition_type == "REORGANIZATION":
        # Strong directional pull during reorganization
        base_magnitude = 0.35 + (current_drift * 0.4)
    elif transition_type == "TRANSITION":
        # Medium velocity during transition
        base_magnitude = 0.25 + (current_drift * 0.3)
    else:
        # Stable: minimal directional pull
        base_magnitude = clamp(current_drift * 0.15, 0.0, 0.1)

    # Direction: use delta to determine pull direction
    if abs(drift_delta) < 0.01:
        # No change, use previous drift to modulate angular direction
        angle = (current_drift * 2 * math.pi) % (2 * math.pi)
    else:
        # Change direction based on drift acceleration
        angle = math.atan2(drift_delta, max(0.1, current_drift))

    vx = _spring_damping(base_magnitude * math.cos(angle))
    vy = _spring_damping(base_magnitude * math.sin(angle))

    return (vx, vy)


def _apply_drift_deformation(
    nodes: list[dict[str, Any]],
    drift_intensity: float,
    velocity: tuple[float, float],
    frame_progress: float = 1.0,
) -> list[dict[str, Any]]:
    """Apply drift-based deformation to node positions with smooth animation.

    Nodes shift in the direction of system velocity, with magnitude proportional
    to drift intensity. Creates visual sense of structure being "pulled" or deformed.

    The frame_progress parameter enables smooth interpolation between frames:
    - When scrubbing or stepping, use frame_progress=1.0 for immediate effect
    - During continuous playback, use easing on frame_progress for smoothness

    Args:
        nodes: Base node positions
        drift_intensity: Magnitude of drift (0-1)
        velocity: System velocity vector (vx, vy)
        frame_progress: Animation progress [0, 1] for current frame

    Returns:
        Deformed node positions with smooth motion
    """
    deformed = []

    # Apply easing to frame progress for smooth animation
    eased_progress = _ease_out_cubic(frame_progress)

    for node in nodes:
        # Distance from center affects deformation magnitude
        dx_from_center = node["base_x"] - 0.5
        dy_from_center = node["base_y"] - 0.5
        distance_from_center = math.sqrt(dx_from_center**2 + dy_from_center**2)

        # Outer nodes deform more (closer to perimeter)
        deformation_factor = (distance_from_center / 0.35) if distance_from_center > 0 else 0.0

        # Apply drift-based displacement with spring-damped velocity
        vx, vy = velocity[0] if len(velocity) > 0 else 0.0, velocity[1] if len(velocity) > 1 else 0.0
        vx = float(vx or 0.0)
        vy = float(vy or 0.0)

        # Displacement magnitude increases with drift but respects frame progress
        displacement_magnitude = drift_intensity * deformation_factor * 0.18 * eased_progress

        x = node["base_x"] + vx * displacement_magnitude
        y = node["base_y"] + vy * displacement_magnitude

        deformed.append({
            **node,
            "x": clamp(x, 0.0, 1.0),
            "y": clamp(y, 0.0, 1.0),
            "deformation": displacement_magnitude,
        })
    return deformed


def _compute_edge_strength(nodes: list[dict[str, Any]], drift_intensity: float, stability: float) -> list[dict[str, Any]]:
    """Compute edges between adjacent nodes with strength based on system state.

    Edges become weaker (more transparent) under high drift, stronger under stability.

    Args:
        nodes: List of deformed nodes
        drift_intensity: System drift (0-1)
        stability: System stability (0-1)

    Returns:
        List of edges between nodes
    """
    edges = []
    num_nodes = len(nodes)

    for i in range(num_nodes):
        # Connect each node to its neighbors (circular topology)
        for j in range(i + 1, min(i + 3, num_nodes)):  # Connect to next 2 neighbors
            node_a = nodes[i]
            node_b = nodes[j]

            # Distance between nodes
            dx = node_b["x"] - node_a["x"]
            dy = node_b["y"] - node_a["y"]
            distance = math.sqrt(dx**2 + dy**2)

            # Edge strength inversely proportional to drift
            strength = clamp(stability * 0.9, 0.1, 1.0)

            edges.append({
                "id": f"edge_{i}_{j}",
                "from": node_a["id"],
                "to": node_b["id"],
                "x1": node_a["x"],
                "y1": node_a["y"],
                "x2": node_b["x"],
                "y2": node_b["y"],
                "distance": distance,
                "strength": strength,
                "opacity": clamp(0.3 + strength * 0.5, 0.1, 0.8),
                "color": _edge_color_by_drift(drift_intensity),
            })

    return edges


def _edge_color_by_drift(drift_intensity: float) -> str:
    """Select edge color based on drift intensity.

    - Low drift (stable): Cool blue
    - Medium drift (transition): Purple
    - High drift (reorganization): Warm orange

    Args:
        drift_intensity: Drift value (0-1)

    Returns:
        Color hex string
    """
    if drift_intensity < 0.35:
        # Stable: cool blue
        return "#60A5FA"
    elif drift_intensity < 0.65:
        # Transition: purple
        return "#A78BFA"
    else:
        # Reorganization: warm orange
        return "#FB923C"


def _to_state_level(drift: float, stability: float, confidence: float) -> str:
    """Derive high-level system state from current metrics."""
    if drift >= 0.78 or (drift >= 0.62 and stability <= 0.36):
        return "Alert"
    if drift >= 0.48 or stability <= 0.52:
        return "Drifting"
    if drift <= 0.14 and stability >= 0.84 and confidence >= 0.78:
        return "Baseline"
    return "Stable"


def _trend_word(delta: float, *, deadband: float = 0.012) -> str:
    if delta > deadband:
        return "increasing"
    if delta < -deadband:
        return "decreasing"
    return "holding"


def _trend_label(metric: str, value: float, delta: float) -> str:
    direction = _trend_word(delta)
    if metric == "stability":
        if value >= 0.76:
            level = "High"
        elif value >= 0.56:
            level = "Moderate"
        else:
            level = "Low"
    elif metric == "drift":
        if value <= 0.26:
            level = "Low"
        elif value <= 0.56:
            level = "Moderate"
        else:
            level = "High"
    else:
        if value >= 0.76:
            level = "Strong"
        elif value >= 0.56:
            level = "Moderate"
        else:
            level = "Weak"
    return f"{metric.title()}: {level} and {direction}"


def _triangle_point_from_metrics(drift: float, stability: float, coherence: float) -> tuple[float, float]:
    """Map metrics to a 2D triangle coordinate using weighted vertices.

    Vertex layout:
    - top: Stability
    - left: Coherence / Structure
    - right: Drift
    """
    stability_v = (0.5, 0.14)
    coherence_v = (0.18, 0.84)
    drift_v = (0.82, 0.84)
    total = max(drift + stability + coherence, 1e-6)
    w_d = drift / total
    w_s = stability / total
    w_c = coherence / total
    x = (w_s * stability_v[0]) + (w_c * coherence_v[0]) + (w_d * drift_v[0])
    y = (w_s * stability_v[1]) + (w_c * coherence_v[1]) + (w_d * drift_v[1])
    return (round(clamp(x, 0.0, 1.0), 4), round(clamp(y, 0.0, 1.0), 4))


def render_system_geometry_viz(
    state: Any,  # SystemState
    gate_decision: dict[str, Any] | None = None,
    records: list[dict[str, Any]] | None = None,
    frame_state: dict[str, Any] | None = None,
    previous_frame_state: dict[str, Any] | None = None,
    current_frame: int = 1,
    total_frames: int = 1,
) -> dict[str, object]:
    """Render structural geometry visualization of system relationships.

    This replaces the previous line chart with a geometric view that shows:
    - System structure as a network of sensors (nodes) and relationships (edges)
    - Deformation reflects stability (tight/organized) vs. drift (spread/deformed)
    - Trails show prior stable states as subtle geometric ghosts
    - Current state highlighted with emphasis

    **ANIMATION & SMOOTHING:**
    - Nodes move smoothly between frames using ease-out-cubic easing
    - Velocity vectors computed from drift delta and transition type
    - No raw 1:1 mapping - drift values drive spring-like deformation
    - Frame progress enables smooth interpolation during playback

    Args:
        state: SystemState object with position, velocity, drift info
        gate_decision: Gate decision dict with verdict info
        records: List of historical records for context
        current_frame: Current replay frame index (1-based)
        total_frames: Total number of frames in replay

    Returns:
        Dict containing geometry visualization model with smooth animation data
    """
    # Generate base sensor nodes
    num_sensors = 8
    nodes = _generate_sensor_nodes(num_sensors)

    # Extract system metrics from state
    drift_intensity = clamp(
        safe_float((frame_state or {}).get("structural_drift"), state.drift_intensity if state else 0.0),
        0.0,
        1.0,
    )
    stability = clamp(
        safe_float((frame_state or {}).get("stability"), 1.0 - drift_intensity),
        0.0,
        1.0,
    )
    confidence = clamp(
        safe_float((frame_state or {}).get("confidence"), state.confidence if state else 0.0),
        0.0,
        1.0,
    )

    # Compute smooth velocity from drift progression
    previous_drift = 0.0
    transition_type = "STABLE"

    if previous_frame_state is not None:
        previous_drift = clamp(safe_float(previous_frame_state.get("structural_drift"), 0.0), 0.0, 1.0)
    elif records and len(records) > 1:
        # Get previous drift for velocity calculation
        prev_record = records[-2]
        previous_drift = clamp(float(prev_record.get("structural_drift_score", 0.0)), 0.0, 1.0)

    if records and len(records) > 0:
        # Get current transition type
        transition_type = str(records[-1].get("transition_type", "STABLE")).upper()

    velocity = _compute_smooth_velocity(drift_intensity, previous_drift, transition_type)

    # Apply deformation based on drift and velocity with frame-aware smoothing
    # Frame progress enables smooth animation during continuous playback
    if total_frames > 1:
        frame_progress = clamp((current_frame - 1) / (total_frames - 1), 0.0, 1.0)
    else:
        frame_progress = 1.0
    deformed_nodes = _apply_drift_deformation(nodes, drift_intensity, velocity, frame_progress)

    # Compute edges with strength based on stability
    edges = _compute_edge_strength(deformed_nodes, drift_intensity, stability)

    rows = records or []
    latest_row = rows[-1] if rows else {}
    previous_row = rows[-2] if len(rows) > 1 else {}
    coherence_value = clamp(
        safe_float(
            (frame_state or {}).get("coherence"),
            safe_float(latest_row.get("coherence_score"), max(0.0, 1.0 - (drift_intensity * 0.72))),
        ),
        0.0,
        1.0,
    )
    previous_drift_value = clamp(
        safe_float(
            (previous_frame_state or {}).get("structural_drift"),
            safe_float(previous_row.get("structural_drift_score"), drift_intensity),
        ),
        0.0,
        1.0,
    )
    previous_stability_value = clamp(
        safe_float(
            (previous_frame_state or {}).get("stability"),
            safe_float(previous_row.get("relational_stability_score"), max(0.0, 1.0 - previous_drift_value)),
        ),
        0.0,
        1.0,
    )
    previous_coherence_value = clamp(
        safe_float(
            (previous_frame_state or {}).get("coherence"),
            safe_float(previous_row.get("coherence_score"), max(0.0, 1.0 - (previous_drift_value * 0.72))),
        ),
        0.0,
        1.0,
    )
    drift_delta = round(drift_intensity - previous_drift_value, 6)
    stability_delta = round(stability - previous_stability_value, 6)
    coherence_delta = round(coherence_value - previous_coherence_value, 6)

    current_triangle_point = _triangle_point_from_metrics(drift_intensity, stability, coherence_value)
    previous_triangle_point = _triangle_point_from_metrics(previous_drift_value, previous_stability_value, previous_coherence_value)
    state_label = str((frame_state or {}).get("state") or _to_state_level(drift_intensity, stability, confidence)).title()
    trend_lines = {
        "stability": _trend_label("stability", stability, stability_delta),
        "drift": _trend_label("drift", drift_intensity, drift_delta),
        "coherence": _trend_label("coherence", coherence_value, coherence_delta),
        "state": f"State: {state_label}",
    }

    # Generate prior stable states as subtle trails
    prior_trails = []
    if len(rows) > 1:
        # Show trails from 2 and 4 steps back
        for steps_back in [2, 4]:
            if len(rows) > steps_back:
                prior_drift = safe_float(rows[-steps_back - 1].get("structural_drift_score"), 0.0)
                1.0 - prior_drift
                opacity = clamp(0.08 + (5 - steps_back) * 0.04, 0.04, 0.16)
                prior_trails.append({
                    "steps_back": steps_back,
                    "drift": prior_drift,
                    "opacity": opacity,
                    "color": f"rgba(148, 163, 184, {opacity:.3f})",
                })

    # Preserve event-layer semantics expected by replay consumers.
    event_points = []
    if rows:
        sensor_count = len(deformed_nodes)
        start_idx = max(0, len(rows) - sensor_count)
        visible_rows = rows[start_idx:]

        for local_idx, row in enumerate(visible_rows):
            idx = start_idx + local_idx
            node = deformed_nodes[local_idx]
            event_points.append({
                "index": idx,
                "timestamp": row.get("timestamp"),
                "event_admitted": row.get("event_admitted"),
                "transition_type": str(row.get("transition_type", "STABLE")).upper(),
                "x": node.get("x", 0.5),
                "y": node.get("y", 0.5),
            })
    admitted_events = [point for point in event_points if bool(point.get("event_admitted"))]
    suppressed_events = [point for point in event_points if point.get("event_admitted") is False]
    stable_events = [point for point in event_points if point.get("transition_type") == "STABLE"]
    transition_events = [point for point in event_points if point.get("transition_type") == "TRANSITION"]
    reorganization_events = [point for point in event_points if point.get("transition_type") == "REORGANIZATION"]

    # Determine phase for visual encoding
    decision = (gate_decision or {}).get("decision", "SUPPRESS").upper() if gate_decision else "SUPPRESS"

    phase_visual = {
        "STABLE": {
            "tone": "coherent",
            "glow": 0.12,
            "color_accent": "#60A5FA",
        },
        "TRANSITION": {
            "tone": "mobilizing",
            "glow": 0.34,
            "color_accent": "#A78BFA",
        },
        "REORGANIZATION": {
            "tone": "transformative",
            "glow": 0.52,
            "color_accent": "#FB923C",
        },
    }.get(transition_type, {
        "tone": "coherent",
        "glow": 0.12,
        "color_accent": "#60A5FA",
    })

    return {
        "component": "system_geometry_visualization",
        "type": "structural_geometry",
        "title": "System Geometry",
        "subtitle": "Live structural analysis • Deformation reflects system drift and stability",
        "explanation": (
            "Nodes represent monitored sensors/functional units. Edges represent relationships. "
            "Stable systems maintain tight, organized structure. Drifting systems show deformation. "
            "Reorganization appears as structural settling into new configuration. "
            "Motion uses spring-damped interpolation for premium smoothness."
        ),
        "canvas": {
            "width": 900,
            "height": 400,
            "background": "#040713",
            "radial_gradient": ["#11183A", "#0A1230", "#05070F"],
        },
        "nodes": deformed_nodes,
        "edges": edges,
        "prior_trails": prior_trails,
        "current_position": {
            "x": state.position.x if state else 0.5,
            "y": state.position.y if state else 0.5,
            "highlight": True,
        },
        "metrics": {
            "drift_intensity": drift_intensity,
            "stability": stability,
            "structure_coherence": coherence_value,
            "deformation_magnitude": drift_intensity,
            "velocity_magnitude": math.sqrt(velocity[0]**2 + velocity[1]**2),
            "confidence": confidence,
            "drift_delta": drift_delta,
            "stability_delta": stability_delta,
            "coherence_delta": coherence_delta,
        },
        "global_state": state_label,
        "triangle_state": {
            "labels": {
                "top": "Stability",
                "left": "Coherence (System Alignment)",
                "right": "Drift",
                "center": "System State",
            },
            "current_point": {"x": current_triangle_point[0], "y": current_triangle_point[1]},
            "previous_point": {"x": previous_triangle_point[0], "y": previous_triangle_point[1]},
            "direction_vector": {
                "dx": round(current_triangle_point[0] - previous_triangle_point[0], 5),
                "dy": round(current_triangle_point[1] - previous_triangle_point[1], 5),
            },
            "geometry_warp": {
                "drift_pull": round(drift_intensity * 0.08, 5),
                "coherence_collapse": round((1.0 - coherence_value) * 0.06, 5),
            },
        },
        "interpretation": trend_lines,
        "animation": {
            "current_frame": current_frame,
            "total_frames": total_frames,
            "easing_function": "ease_out_cubic",
            "transition_type": transition_type,
            "velocity_vector": {"vx": velocity[0], "vy": velocity[1]},
            "is_animating": True,
        },
        "phase_visual": phase_visual,
        "phase_layers": {
            "stable_baseline": stable_events,
            "transition": transition_events,
            "reorganization": reorganization_events,
            "admitted_events": admitted_events,
            "suppressed_events": suppressed_events,
        },
        "gate_decision": decision,
        "admitted": decision == "ADMIT",
        "visual_hierarchy": {
            "nodes": "primary_focus",
            "edges": "supporting_context",
            "trails": "historical_context",
        },
    }
