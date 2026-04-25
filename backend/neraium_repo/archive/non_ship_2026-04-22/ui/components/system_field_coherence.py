"""System Field with Coherence Core.

The heart of the Neraium operational interface:
- Dynamic tetrahedral structure representing subsystem relationships
- Coherence Core at center that pulses, glows, and degrades based on system health
- Visual deformation reflects system state: stable, drift, instability, critical
- Interactive: hover/click subsystems to focus and explore

The tetrahedron represents:
  Vertices: Climate, Airflow, Irrigation, Plant Response (or generic domains)
  Edges: Relationships and coupling between subsystems
  Center: System Coherence (unity, integration, health)
"""

from __future__ import annotations

import math
from typing import Any

from ui.utils import clamp, safe_float


SUBSYSTEM_DOMAINS = {
    "climate": {"label": "Climate", "angle": 0},
    "airflow": {"label": "Airflow", "angle": 90},
    "irrigation": {"label": "Irrigation", "angle": 180},
    "plant_response": {"label": "Plant Response", "angle": 270},
}


def _compute_tetrahedron_geometry(
    coherence: float,
    drift: float,
    stability: float,
    state: str = "stable",
    history_max_drift: float = 0.0,
    history_min_coherence: float = 1.0,
) -> dict[str, Any]:
    """Compute tetrahedron vertex positions governed by physics.

    Physics principles:
    - Pre-deformation at low drift (anticipation before threshold)
    - Coherence core tightens under stress (resisting force)
    - Irreversibility: permanent deformation after critical threshold
    - Resistance between subsystems creates balance
    - All deformation eases, not snaps
    - Core color marks threshold breach: once coherence < 0.4, core shifts to orange

    Args:
        coherence: Coherence score (0-1). Core resistance strength.
        drift: Structural drift (0-1). Deformation driver.
        stability: Relational stability (0-1). Edge smoothness.
        state: One of stable, drift, instability, critical
        history_max_drift: Maximum drift ever reached (for hysteresis)
        history_min_coherence: Minimum coherence ever reached (for threshold memory)

    Returns:
        Dictionary with vertex positions, edge states, coherence core params
    """

    base_scale = 1.0

    pre_deformation = drift * 0.08 if drift > 0.05 else 0.0
    explicit_deformation = max(0.0, drift - 0.15) * 0.4 if drift > 0.15 else 0.0

    if state == "stable":
        explicit_deformation = 0.0
        tension_color = "#22C55E"
        edge_opacity = 0.8
        core_resistance = coherence * 0.15
        core_pulse_intensity = 0.3
        instability_axis = (0, 0, 0)
    elif state == "drift":
        explicit_deformation = drift * 0.3
        tension_color = "#3B82F6"
        edge_opacity = 0.6 + 0.2 * drift
        core_resistance = coherence * 0.12
        core_pulse_intensity = 0.4 + 0.2 * drift
        instability_axis = (math.sin(drift * math.pi * 0.5), 0, math.cos(drift * math.pi))
    elif state == "instability":
        explicit_deformation = 0.2 + (drift * 0.4)
        tension_color = "#F97316"
        edge_opacity = 0.7 + 0.3 * drift
        core_resistance = coherence * 0.08
        core_pulse_intensity = 0.5 + 0.35 * drift
        instability_axis = (math.sin(drift * math.pi), math.cos(drift * math.pi * 0.3), 1)
    else:
        explicit_deformation = 0.55 + (0.15 * (1.0 - coherence))
        tension_color = "#EF4444"
        edge_opacity = 0.95
        core_resistance = coherence * 0.04
        core_pulse_intensity = 0.7 + 0.3 * (1.0 - coherence)
        instability_axis = (1, 0.5, 0.8)

    hysteresis_residual = 0.0
    if history_max_drift > 0.6 and drift < history_max_drift:
        hysteresis_residual = (history_max_drift - 0.6) * (history_max_drift - drift) * 0.15

    total_deformation = clamp(pre_deformation + explicit_deformation + hysteresis_residual, 0.0, 0.6)

    base_vertices = {
        "top": (0, -0.5 * base_scale, 0.5 * base_scale),
        "front_right": (0.5 * base_scale, 0.3 * base_scale, 0.3 * base_scale),
        "front_left": (-0.5 * base_scale, 0.3 * base_scale, 0.3 * base_scale),
        "back": (0, 0.3 * base_scale, -0.5 * base_scale),
    }

    drift_direction = instability_axis

    deformed_vertices = {}
    for name, (x, y, z) in base_vertices.items():
        magnitude = math.sqrt(x * x + y * y + z * z)
        if magnitude > 0:
            push_strength = magnitude * total_deformation * (1.8 - core_resistance)
        else:
            push_strength = total_deformation * (1.0 - core_resistance)

        dx = drift_direction[0] * push_strength * (1.0 + abs(x) * 0.5)
        dy = drift_direction[1] * push_strength * (1.0 + abs(y) * 0.5)
        dz = drift_direction[2] * push_strength * (1.0 + abs(z) * 0.5)

        scale_factor = 1.0 - (total_deformation * 0.25)

        deformed_vertices[name] = (
            (x + dx) * scale_factor,
            (y + dy) * scale_factor,
            (z + dz) * scale_factor,
        )

    edges = [
        ("top", "front_right"),
        ("top", "front_left"),
        ("top", "back"),
        ("front_right", "front_left"),
        ("front_right", "back"),
        ("front_left", "back"),
    ]

    edge_states = []
    for v1_name, v2_name in edges:
        v1 = deformed_vertices[v1_name]
        v2 = deformed_vertices[v2_name]

        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))
        stress_factor = clamp(abs(dist - 1.0), 0.0, 1.0)

        edge_states.append({
            "from": v1_name,
            "to": v2_name,
            "p1": v1,
            "p2": v2,
            "tension": stress_factor,
            "glow_intensity": (stress_factor * 0.8) + (edge_opacity * 0.2),
            "color": tension_color,
        })

    coherence_ring = {
        "radius": 0.65,
        "is_stable": state == "stable",
        "deformation": clamp(total_deformation, 0.0, 0.3),
        "glow_color": tension_color,
        "glow_intensity": 0.4 + (1.0 - coherence) * 0.6,
        "opacity": 0.5 + (coherence * 0.5),
    }

    core_radius = 0.14 + 0.10 * clamp(coherence, 0.0, 1.0)

    core_tightening = core_resistance * 2.0
    effective_core_radius = max(0.06, core_radius - core_tightening)

    threshold_breached = history_min_coherence < 0.4
    if threshold_breached:
        core_color = "#F97316"
    elif coherence > 0.6:
        core_color = "#22C55E"
    elif coherence > 0.3:
        core_color = "#3B82F6"
    else:
        core_color = "#F97316"

    coherence_core = {
        "radius": effective_core_radius,
        "base_radius": core_radius,
        "color": core_color,
        "pulse_intensity": core_pulse_intensity + (core_tightening * 0.5),
        "pulse_frequency": 1.0 + (drift * 0.6),
        "glow_spread": max(0.08, 0.15 + (drift * 0.1) - core_tightening),
        "opacity": 0.8 + (coherence * 0.2),
        "resistance": core_resistance,
    }

    subsystem_influence = []
    resistance_factor = core_resistance
    for domain_key, domain_info in SUBSYSTEM_DOMAINS.items():
        angle = math.radians(domain_info["angle"])
        influence_distance = 0.75
        x = influence_distance * math.cos(angle)
        y = influence_distance * math.sin(angle)

        base_magnitude = drift * (1.0 if "climate" in domain_key else 0.7)
        resisted_magnitude = base_magnitude * (1.0 - resistance_factor)
        magnitude = clamp(resisted_magnitude, 0.0, 1.0)

        subsystem_influence.append({
            "domain": domain_key,
            "label": domain_info["label"],
            "position": (x, y),
            "influence_magnitude": magnitude,
            "influence_direction": (math.cos(angle), math.sin(angle)),
            "resistance": resistance_factor,
        })

    return {
        "vertices": deformed_vertices,
        "edges": edge_states,
        "coherence_ring": coherence_ring,
        "coherence_core": coherence_core,
        "subsystem_influence": subsystem_influence,
        "state": state,
        "drift": drift,
        "stability": stability,
        "coherence": coherence,
        "total_deformation": total_deformation,
        "core_resistance": core_resistance,
        "pre_deformation": pre_deformation,
        "hysteresis_residual": hysteresis_residual,
    }


def render_system_field_svg(
    coherence: float,
    drift: float,
    stability: float,
    state: str = "stable",
    width: int = 800,
    height: int = 600,
    interactive: bool = True,
    critical_subsystem_id: str | None = None,
    records: list[dict[str, Any]] | None = None,
    no_action_projection: list[dict[str, Any]] | None = None,
) -> str:
    """Render the system field with divergence visualization for no-action trajectory.

    Args:
        coherence: System coherence score (0-1)
        drift: Structural drift score (0-1)
        stability: Relational stability score (0-1)
        state: System state (stable, drift, instability, critical)
        width: SVG width in pixels
        height: SVG height in pixels
        interactive: If True, add hover/click interactivity
        critical_subsystem_id: ID of the most critical subsystem to highlight (climate, airflow, irrigation, plant_response)
        records: Historical records list for computing minimum coherence
        no_action_projection: Projected drift if no intervention occurs (shows divergence)

    Returns:
        SVG markup string
    """
    history_min_coherence = 1.0
    if records:
        coherence_values = [float(r.get("coherence_score", 1.0)) for r in records]
        if coherence_values:
            history_min_coherence = min(coherence_values)

    geometry = _compute_tetrahedron_geometry(
        coherence, drift, stability, state,
        history_min_coherence=history_min_coherence
    )

    no_action_drift = drift
    if no_action_projection and len(no_action_projection) > 0:
        no_action_drift = float(no_action_projection[0].get("drift", drift))

    divergence_geometry = None
    if no_action_drift > drift and drift > 0.15:
        divergence_geometry = _compute_tetrahedron_geometry(
            coherence, no_action_drift, stability, state,
            history_min_coherence=history_min_coherence
        )

    center_x = width / 2
    center_y = height / 2
    scale = min(width, height) * 0.25

    def to_svg(x: float, y: float, z: float) -> tuple[float, float]:
        """Project 3D tetrahedron to 2D SVG.

        Simple isometric projection for clarity and performance.
        """
        proj_x = (x - y) * 0.866
        proj_y = (x + y) * 0.5 - z
        return center_x + proj_x * scale, center_y + proj_y * scale

    svg_parts = []

    pulse_freq = geometry["coherence_core"]["pulse_frequency"]
    pulse_duration = max(0.6, 2.0 - (pulse_freq * 0.4))
    drift = geometry["drift"]
    core_tension = geometry["core_resistance"]

    if drift < 0.15:
        motion_responsivity = "minimal"
        ambient_drift_duration = 12.0
        breathing_duration = 4.0
        shimmer_duration = 0.8
    elif drift < 0.4:
        motion_responsivity = "moderate"
        ambient_drift_duration = 10.0
        breathing_duration = 2.5
        shimmer_duration = 1.2
    elif drift < 0.6:
        motion_responsivity = "elevated"
        ambient_drift_duration = 6.0
        breathing_duration = 1.8
        shimmer_duration = 1.5
    else:
        motion_responsivity = "critical"
        ambient_drift_duration = 3.5
        breathing_duration = 1.2
        shimmer_duration = 2.0

    fragility = drift * (1.0 - geometry["coherence"]) if geometry["coherence"] > 0 else drift
    fragility_level = "critical" if fragility > 0.5 else "high" if fragility > 0.35 else "moderate" if fragility > 0.15 else "low"

    svg_parts.append(f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
        xmlns="http://www.w3.org/2000/svg" class="ner-system-field" preserveAspectRatio="xMidYMid meet"
        data-drift="{drift:.2f}" data-coherence="{geometry['coherence']:.2f}" data-motion="{motion_responsivity}" data-fragility="{fragility_level}">
        <defs>
            <filter id="coherenceGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="8" result="blur"/>
                <feFlood flood-color="rgba(34,197,94,0.3)" result="color"/>
                <feComposite in="color" in2="blur" operator="in" result="coloredBlur"/>
                <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
            <filter id="coreRadiance" x="-80%" y="-80%" width="260%" height="260%">
                <feGaussianBlur stdDeviation="14" result="blur"/>
                <feFlood flood-color="rgba(34,197,94,0.4)" result="color"/>
                <feComposite in="color" in2="blur" operator="in" result="coloredBlur"/>
                <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
            <filter id="edgeTension">
                <feGaussianBlur stdDeviation="1.5" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
            <filter id="tensionShimmer" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="6" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                </feMerge>
            </filter>
            <style>
                @keyframes coreRadiate {{
                    0% {{ r: {geometry["coherence_core"]["radius"]:.3f}; }}
                    50% {{ r: {geometry["coherence_core"]["radius"] + 0.05:.3f}; }}
                    100% {{ r: {geometry["coherence_core"]["radius"]:.3f}; }}
                }}
                @keyframes ringBreathing {{
                    0%, 100% {{ stroke-width: 1.8; opacity: 0.5; }}
                    50% {{ stroke-width: 2.2; opacity: 0.7; }}
                }}
                @keyframes tensionShimmer {{
                    0%, 100% {{ opacity: 0.3; }}
                    50% {{ opacity: 0.6; }}
                }}
                @keyframes ambientDrift {{
                    0%, 100% {{ transform: translate(0, 0) scale(1); }}
                    25% {{ transform: translate(1px, -1px) scale(1.002); }}
                    50% {{ transform: translate(0, 1px) scale(1); }}
                    75% {{ transform: translate(-1px, -1px) scale(0.998); }}
                }}
                @keyframes warningJitter {{
                    0% {{ transform: translate(0, 0); }}
                    12% {{ transform: translate(0.5px, -0.3px); }}
                    25% {{ transform: translate(-0.2px, 0.4px); }}
                    37% {{ transform: translate(0.3px, 0.1px); }}
                    50% {{ transform: translate(-0.4px, -0.2px); }}
                    62% {{ transform: translate(0.2px, 0.3px); }}
                    75% {{ transform: translate(-0.3px, -0.1px); }}
                    87% {{ transform: translate(0.4px, 0.2px); }}
                    100% {{ transform: translate(0, 0); }}
                }}
                .ner-coherence-core {{
                    animation: coreRadiate {breathing_duration:.2f}s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
                    filter: url(#coreRadiance);
                }}
                .ner-coherence-ring {{
                    animation: ringBreathing {breathing_duration * 1.5:.2f}s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
                }}
                .ner-system-field {{
                    animation: ambientDrift {ambient_drift_duration:.1f}s ease-in-out infinite;
                    transform-origin: center;
                }}
                .ner-system-field[data-fragility="critical"] {{
                    animation: warningJitter 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
                }}
                .ner-system-field[data-fragility="high"] {{
                    animation: warningJitter 1.2s ease-in-out infinite;
                }}
                .ner-tension-shimmer {{
                    animation: tensionShimmer {shimmer_duration:.2f}s ease-in-out infinite;
                }}
            </style>
        </defs>
    """)

    svg_parts.append(f"""
        <rect width="{width}" height="{height}" fill="#020617" opacity="0"/>
        <defs>
            <radialGradient id="fieldGradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="rgba(59,130,246,0.05)" stop-opacity="1"/>
                <stop offset="100%" stop-color="rgba(59,130,246,0.0)" stop-opacity="1"/>
            </radialGradient>
        </defs>
        <circle cx="{center_x}" cy="{center_y}" r="{min(width,height)*0.45}" fill="url(#fieldGradient)"/>
    """)

    coherence_ring = geometry["coherence_ring"]
    ring_cx, ring_cy = center_x, center_y
    ring_r = coherence_ring["radius"] * scale

    glow_opacity = coherence_ring["glow_intensity"] * 0.5
    glow_spread = ring_r * (1.0 + coherence_ring["glow_intensity"] * 0.2)

    svg_parts.append(f"""
        <circle cx="{ring_cx}" cy="{ring_cy}" r="{glow_spread}"
            fill="none" stroke="{coherence_ring["glow_color"]}"
            stroke-width="3" opacity="{glow_opacity * 0.3}" filter="url(#coherenceGlow)"/>
    """)

    svg_parts.append(f"""
        <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}"
            fill="none" stroke="{coherence_ring["glow_color"]}"
            stroke-width="2.2" opacity="{glow_opacity}"
            class="ner-coherence-ring" filter="url(#coherenceGlow)"/>
    """)

    svg_parts.append(f"""
        <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}"
            fill="none" stroke="{coherence_ring["glow_color"]}"
            stroke-width="1.0" opacity="{coherence_ring["opacity"] * 0.8}"
            stroke-dasharray="4,2" stroke-linecap="round"/>
    """)

    for edge in geometry["edges"]:
        x1, y1 = to_svg(*edge["p1"])
        x2, y2 = to_svg(*edge["p2"])

        edge_color = edge["color"]
        edge_width = 1.4 + edge["tension"] * 2.2
        edge_opacity = edge["glow_intensity"]

        tension = edge["tension"]
        if tension > 0.5:
            svg_parts.append(f"""
                <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"
                    stroke="{edge_color}" stroke-width="{edge_width * 1.3:.2f}"
                    opacity="{edge_opacity * 0.4}" stroke-linecap="round"
                    filter="url(#edgeTension)"/>
            """)

        svg_parts.append(f"""
            <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"
                stroke="{edge_color}" stroke-width="{edge_width:.2f}"
                opacity="{edge_opacity}" stroke-linecap="round"
                stroke-linejoin="round"/>
        """)

    if divergence_geometry and drift > 0.15:
        for div_edge in divergence_geometry["edges"]:
            div_x1, div_y1 = to_svg(*div_edge["p1"])
            div_x2, div_y2 = to_svg(*div_edge["p2"])

            div_color = "rgba(239,68,68,0.4)"
            div_width = 0.8 + div_edge["tension"] * 1.0
            div_opacity = 0.2 + div_edge["glow_intensity"] * 0.15

            svg_parts.append(f"""
                <line x1="{div_x1:.1f}" y1="{div_y1:.1f}" x2="{div_x2:.1f}" y2="{div_y2:.1f}"
                    stroke="{div_color}" stroke-width="{div_width:.2f}"
                    opacity="{div_opacity}" stroke-linecap="round"
                    stroke-dasharray="2,3" stroke-linejoin="round"/>
            """)

    vertices = geometry["vertices"]
    vertex_labels = {
        "top": "Climate",
        "front_right": "Airflow",
        "front_left": "Irrigation",
        "back": "Plant",
    }

    subsystem_to_vertex = {
        "climate": "top",
        "airflow": "front_right",
        "irrigation": "front_left",
        "plant_response": "back",
    }

    for v_name, (vx, vy, vz) in vertices.items():
        vx_svg, vy_svg = to_svg(vx, vy, vz)

        mapped_subsystem = [s for s, v in subsystem_to_vertex.items() if v == v_name]
        subsys_key = mapped_subsystem[0] if mapped_subsystem else None

        subsys_drift = 0.0
        if subsys_key:
            for si in geometry["subsystem_influence"]:
                if si["domain"] == subsys_key:
                    subsys_drift = si["influence_magnitude"]
                    break

        is_critical = subsys_key == critical_subsystem_id
        v_color = "#3B82F6" if subsys_drift > 0.3 else "#93C5FD"
        v_radius = 8.0 + subsys_drift * 3.0
        v_opacity = 0.85 + subsys_drift * 0.15

        if is_critical:
            v_color = "#F97316" if drift > 0.4 else "#FB923C"
            v_radius = v_radius + 2.5
            v_opacity = min(1.0, v_opacity + 0.15)

        v_glow_radius = v_radius + (6.0 if is_critical else 3.0)

        svg_parts.append(f"""
            <circle cx="{vx_svg:.1f}" cy="{vy_svg:.1f}" r="{v_glow_radius}"
                fill="{v_color}" opacity="{(v_opacity * 0.6) if is_critical else (v_opacity * 0.4)}"
                filter="url(#coherenceGlow)"/>
        """)

        if is_critical:
            svg_parts.append(f"""
                <circle cx="{vx_svg:.1f}" cy="{vy_svg:.1f}" r="{v_glow_radius * 0.7}"
                    fill="{v_color}" opacity="{v_opacity * 0.3}"
                    filter="url(#coherenceGlow)"/>
            """)

        svg_parts.append(f"""
            <circle cx="{vx_svg:.1f}" cy="{vy_svg:.1f}" r="{v_radius}"
                fill="{v_color}" opacity="{v_opacity}"
                stroke="{v_color if is_critical else 'rgba(226,232,240,0.5)'}" stroke-width="{2.0 if is_critical else 1.4}"
                class="ner-system-vertex" data-vertex="{v_name}"
                data-subsystem="{subsys_key or 'none'}"/>
        """)

        label_text = vertex_labels.get(v_name, v_name)
        angle = math.atan2(vy_svg - center_y, vx_svg - center_x)
        label_dist = v_radius + 18 + subsys_drift * 8
        label_x = vx_svg + math.cos(angle) * label_dist
        label_y = vy_svg + math.sin(angle) * label_dist
        label_opacity = 0.6 + subsys_drift * 0.35

        svg_parts.append(f"""
            <text x="{label_x:.1f}" y="{label_y:.1f}"
                font-size="10" font-weight="700" fill="#E2E8F0"
                text-anchor="middle" alignment-baseline="middle"
                opacity="{label_opacity}">{label_text}</text>
        """)

    core = geometry["coherence_core"]
    core_x, core_y = center_x, center_y
    core_r = core["radius"] * scale
    core_glow_r = core_r + core["glow_spread"] * scale

    outer_glow_r = core_glow_r * 1.3
    svg_parts.append(f"""
        <circle cx="{core_x}" cy="{core_y}" r="{outer_glow_r}"
            fill="none" stroke="{core["color"]}" stroke-width="1.2"
            opacity="{core["pulse_intensity"] * 0.2}"
            filter="url(#coreRadiance)"/>
    """)

    svg_parts.append(f"""
        <circle cx="{core_x}" cy="{core_y}" r="{core_glow_r}"
            fill="{core["color"]}" opacity="{core["pulse_intensity"] * 0.4}"
            filter="url(#coreRadiance)"/>
    """)

    svg_parts.append(f"""
        <circle cx="{core_x}" cy="{core_y}" r="{core_glow_r * 0.7}"
            fill="{core["color"]}" opacity="{core["pulse_intensity"] * 0.5}"
            filter="url(#coreRadiance)"/>
    """)

    svg_parts.append(f"""
        <circle cx="{core_x}" cy="{core_y}" r="{core_r}"
            fill="{core["color"]}" opacity="{core["opacity"]}"
            class="ner-coherence-core"
            stroke="rgba(226,232,240,0.2)" stroke-width="0.8"/>
    """)

    if interactive:
        for subsys in geometry["subsystem_influence"]:
            sx, sy = subsys["position"]
            sx_svg = center_x + sx * scale
            sy_svg = center_y + sy * scale

            mag = subsys["influence_magnitude"]
            mag_radius = 6 + mag * 8
            mag_opacity = 0.2 + mag * 0.6
            glow_radius = mag_radius + 3 + mag * 4

            svg_parts.append(f"""
                <circle cx="{sx_svg:.1f}" cy="{sy_svg:.1f}" r="{glow_radius:.1f}"
                    fill="#3B82F6" opacity="{mag_opacity * 0.3}"
                    filter="url(#coherenceGlow)"/>
            """)

            svg_parts.append(f"""
                <circle cx="{sx_svg:.1f}" cy="{sy_svg:.1f}" r="{mag_radius:.1f}"
                    fill="#3B82F6" opacity="{mag_opacity}"
                    stroke="rgba(59,130,246,0.5)" stroke-width="1.2"
                    class="ner-subsystem-vertex" data-subsystem="{subsys["domain"]}"/>
            """)

            if mag > 0.15:
                tension_pull = mag * scale * 0.5
                pulling_x = center_x + (sx - sx * 0.3) * scale
                pulling_y = center_y + (sy - sy * 0.3) * scale

                svg_parts.append(f"""
                    <line x1="{sx_svg:.1f}" y1="{sy_svg:.1f}"
                        x2="{pulling_x:.1f}" y2="{pulling_y:.1f}"
                        stroke="#3B82F6" stroke-width="{1.0 + mag * 1.5:.2f}"
                        opacity="{0.2 + mag * 0.5}" stroke-linecap="round"
                        stroke-dasharray="2,3" filter="url(#edgeTension)"/>
                """)

    svg_parts.append("</svg>")

    return "\n".join(svg_parts)



