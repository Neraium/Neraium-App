"""State Timeline: Bottom-integrated state evolution visualization.

Shows the progression of system states over time:
- Baseline: Normal operation
- Drift: Rising structural drift but still stable
- Emerging: Instability beginning to form
- Persistent: Instability sustained over time
- Accelerated: Rapid change detected
- Critical: System failure threshold approaching

Visual language shared with system field:
- Smooth curves during stable periods
- Deformation shows drift progression
- Colors match system field palette
- Hover to preview past system states
- Subtle projected trajectory showing where system is heading
"""

from __future__ import annotations

from typing import Any
from html import escape


def render_state_timeline(
    states: list[dict[str, Any]],
    current_index: int | None = None,
    width: int = 1200,
    height: int = 140,
    no_action_projection: list[dict[str, Any]] | None = None,
) -> str:
    """Render the state timeline showing momentum, acceleration, and no-action trajectory.

    The timeline communicates:
    - Steepness = velocity of drift/recovery
    - Curvature = acceleration (drift speeding up/slowing down)
    - Spacing = temporal progression
    - Current projection = extrapolated trajectory with continued current behavior
    - No-action projection = what happens if system continues unchanged (divergence)

    Args:
        states: List of state dicts with keys:
            timestamp, state_label, coherence, drift, stability,
            is_admitted, emphasis
        current_index: Index of current position in timeline
        width: SVG width in pixels
        height: SVG height in pixels
        no_action_projection: Optional projected drift values if no intervention occurs

    Returns:
        SVG markup for the timeline
    """

    if not states:
        states = [
            {
                "timestamp": "—",
                "state_label": "No Data",
                "coherence": 0.5,
                "drift": 0.0,
                "stability": 0.5,
                "is_admitted": False,
                "emphasis": "low",
            }
        ]

    state_colors = {
        "baseline": "#6B7280",
        "drift": "#3B82F6",
        "emerging": "#F97316",
        "persistent": "#EF4444",
        "accelerated": "#DC2626",
        "critical": "#991B1B",
    }

    margin_left = 40
    margin_right = 80
    margin_top = 20
    margin_bottom = 40

    available_width = width - margin_left - margin_right
    available_height = height - margin_top - margin_bottom

    if len(states) < 2:
        x_spacing = available_width
    else:
        x_spacing = available_width / (len(states) - 1)

    svg_parts = []

    svg_parts.append(f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
        xmlns="http://www.w3.org/2000/svg" class="ner-state-timeline">
        <defs>
            <filter id="momentumGlow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="4" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
            <linearGradient id="momentumGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#6B7280" stop-opacity="0.6"/>
                <stop offset="35%" stop-color="#3B82F6" stop-opacity="0.8"/>
                <stop offset="70%" stop-color="#F97316" stop-opacity="0.9"/>
                <stop offset="100%" stop-color="#EF4444" stop-opacity="1"/>
            </linearGradient>
        </defs>
    """)

    svg_parts.append(f"""
        <rect width="{width}" height="{height}" fill="#020617" opacity="0"/>
    """)

    baseline_y = margin_top + available_height * 0.5

    points_x = []
    points_drift = []
    velocities = []

    for i, state in enumerate(states):
        x = margin_left + (i * x_spacing)
        points_x.append(x)

        drift = float(state.get("drift", 0.0))
        drift_y = baseline_y - (drift - 0.5) * available_height
        points_drift.append((x, drift_y, drift))

        if i > 0:
            prev_drift = float(states[i - 1].get("drift", 0.0))
            velocity = drift - prev_drift
            velocities.append(velocity)
        else:
            velocities.append(0.0)

    svg_parts.append(f"""
        <line x1="{margin_left}" y1="{baseline_y}" x2="{margin_left + available_width}" y2="{baseline_y}"
            stroke="rgba(148,163,184,0.15)" stroke-width="1" stroke-dasharray="2,2"/>
    """)

    if len(points_drift) > 1:
        path_d = f"M{points_drift[0][0]:.1f},{points_drift[0][1]:.1f}"
        for i in range(1, len(points_drift)):
            x_curr = points_drift[i][0]
            y_curr = points_drift[i][1]
            if i > 0:
                x_prev = points_drift[i - 1][0]
                y_prev = points_drift[i - 1][1]
                cx = (x_prev + x_curr) / 2
                cy_ctrl = y_prev + (y_curr - y_prev) * 0.5
                path_d += f" Q{cx:.1f},{cy_ctrl:.1f} {x_curr:.1f},{y_curr:.1f}"
            else:
                path_d += f" L{x_curr:.1f},{y_curr:.1f}"

        svg_parts.append(f"""
            <path d="{path_d}" fill="none" stroke="url(#momentumGradient)"
                stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"
                filter="url(#momentumGlow)"/>
        """)

        svg_parts.append(f"""
            <path d="{path_d}" fill="none" stroke="url(#momentumGradient)"
                stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
                opacity="0.4"/>
        """)

    for i, state in enumerate(states):
        x = points_x[i]
        y = points_drift[i][1]
        drift = points_drift[i][2]

        state_label = str(state.get("state_label", "unknown")).lower()
        state_color = state_colors.get(state_label, "#94A3B8")

        is_admitted = bool(state.get("is_admitted", False))
        emphasis = str(state.get("emphasis", "low")).lower()

        velocity = velocities[i] if i < len(velocities) else 0.0
        velocity_magnitude = abs(velocity)

        node_radius = 4.0 + velocity_magnitude * 3.0
        glow_spread = node_radius + 2.0 + velocity_magnitude * 2.0

        if velocity_magnitude > 0.1:
            svg_parts.append(f"""
                <circle cx="{x:.1f}" cy="{y:.1f}" r="{glow_spread}"
                    fill="{state_color}" opacity="{0.2 + velocity_magnitude * 0.3}"
                    filter="url(#momentumGlow)"/>
            """)

        svg_parts.append(f"""
            <circle cx="{x:.1f}" cy="{y:.1f}" r="{node_radius}"
                fill="{state_color}" opacity="0.9"
                stroke="rgba(226,232,240,{0.3 + velocity_magnitude * 0.5})"
                stroke-width="{1.0 + velocity_magnitude * 1.5:.2f}"/>
        """)

        if i == current_index:
            svg_parts.append(f"""
                <circle cx="{x:.1f}" cy="{y:.1f}" r="{node_radius + 5}"
                    fill="none" stroke="#22D3EE" stroke-width="2.5" opacity="0.85"
                    stroke-dasharray="5,3" filter="url(#momentumGlow)"/>
            """)

        if is_admitted:
            svg_parts.append(f"""
                <circle cx="{x:.1f}" cy="{y:.1f}" r="{node_radius - 1.5}"
                    fill="none" stroke="{state_color}" stroke-width="2" opacity="0.6"/>
            """)

        timestamp = str(state.get("timestamp", "")).split("T")[-1].split("Z")[0] if state.get("timestamp") else "—"
        svg_parts.append(f"""
            <text x="{x:.1f}" y="{margin_top + available_height + 22}" text-anchor="middle"
                font-size="9" fill="rgba(148,163,184,0.7)">{escape(timestamp)}</text>
        """)

    if len(points_drift) > 2:
        last_two_drifts = [points_drift[-2][2], points_drift[-1][2]]
        last_velocity = last_two_drifts[-1] - last_two_drifts[-2]
        last_x = points_drift[-1][0]
        last_y = points_drift[-1][1]

        proj_steps = 3
        for step in range(1, proj_steps + 1):
            proj_x = last_x + (x_spacing * step)
            if proj_x > margin_left + available_width:
                break

            proj_drift = float(states[-1].get("drift", 0.0)) + (last_velocity * step)
            proj_drift = max(0.0, min(1.0, proj_drift))
            proj_y = baseline_y - (proj_drift - 0.5) * available_height

            opacity = 0.4 - (step * 0.08)
            svg_parts.append(f"""
                <circle cx="{proj_x:.1f}" cy="{proj_y:.1f}" r="2.5"
                    fill="rgba(226,232,240,{opacity})" opacity="0.7"/>
            """)

        svg_parts.append(f"""
            <path d="M{last_x:.1f},{last_y:.1f} L{last_x + (x_spacing * proj_steps):.1f},{last_y + (last_velocity * proj_steps * available_height):.1f}"
                stroke="rgba(226,232,240,0.3)" stroke-width="1.2"
                stroke-dasharray="3,4" opacity="0.6"/>
        """)

        svg_parts.append(f"""
            <text x="{last_x + (x_spacing * proj_steps) + 10}" y="{last_y + (last_velocity * proj_steps * available_height) - 8}"
                font-size="8" fill="rgba(226,232,240,0.5)" opacity="0.6">projected</text>
        """)

    if no_action_projection and len(points_drift) > 1:
        last_x = points_drift[-1][0]
        last_y = points_drift[-1][1]

        proj_steps = min(3, len(no_action_projection))
        for step in range(proj_steps):
            if step >= len(no_action_projection):
                break

            proj_x = last_x + (x_spacing * (step + 1))
            if proj_x > margin_left + available_width:
                break

            proj_drift = float(no_action_projection[step].get("drift", 0.0))
            proj_drift = max(0.0, min(1.0, proj_drift))
            proj_y = baseline_y - (proj_drift - 0.5) * available_height

            opacity = 0.3 - (step * 0.07)
            color = "#EF4444" if proj_drift > 0.6 else "#F97316" if proj_drift > 0.4 else "#3B82F6"

            svg_parts.append(f"""
                <circle cx="{proj_x:.1f}" cy="{proj_y:.1f}" r="2.2"
                    fill="{color}" opacity="{opacity * 0.8}"/>
            """)

        if proj_steps > 0:
            end_x = last_x + (x_spacing * proj_steps)
            end_proj_drift = float(no_action_projection[-1].get("drift", 0.0))
            end_proj_y = baseline_y - (end_proj_drift - 0.5) * available_height

            svg_parts.append(f"""
                <path d="M{last_x:.1f},{last_y:.1f} L{end_x:.1f},{end_proj_y:.1f}"
                    stroke="rgba(239,68,68,0.35)" stroke-width="1.4"
                    stroke-dasharray="2,3" opacity="0.5"/>
            """)

            svg_parts.append(f"""
                <text x="{end_x + 8}" y="{end_proj_y - 10}"
                    font-size="7.5" fill="rgba(239,68,68,0.6)" opacity="0.6">no action</text>
            """)

    legend_y = margin_top + available_height + 35
    legend_items = [
        ("Baseline", "#6B7280"),
        ("Drift", "#3B82F6"),
        ("Emerging", "#F97316"),
        ("Critical", "#DC2626"),
    ]

    legend_x = margin_left
    for label, color in legend_items:
        svg_parts.append(f"""
            <circle cx="{legend_x}" cy="{legend_y}" r="3"
                fill="{color}"/>
        """)
        svg_parts.append(f"""
            <text x="{legend_x + 12}" y="{legend_y + 3}" font-size="9"
                fill="rgba(226,232,240,0.7)">{escape(label)}</text>
        """)
        legend_x += 110

    svg_parts.append("</svg>")

    return "\n".join(svg_parts)
