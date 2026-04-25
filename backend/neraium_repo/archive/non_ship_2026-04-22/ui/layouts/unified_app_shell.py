"""Unified App Shell: System-first architecture.

The complete operational surface unified as one connected canvas:

AppShell
â”œâ”€ TopStatusBar (Facility Command Strip)
â”œâ”€ MainCanvas (central focus)
â”‚  â”œâ”€ SystemField (dominant, interactive tetrahedron with coherence core)
â”‚  â””â”€ OverlayLayer
â”‚     â”œâ”€ SubsystemInfluence (left, floating)
â”‚     â””â”€ IntelligenceRail (right, floating)
â””â”€ StateTimeline (bottom, integrated)

NO boxed layout.
NO panel-based dashboard.
Everything = one connected operating surface.
"""

from __future__ import annotations

from typing import Any

from ui.components import (
    render_system_field_svg,
    render_facility_command_strip,
    render_subsystem_influence_panel,
    render_intelligence_rail,
    render_state_timeline,
)
from ui.core_integration import SystemState
from ui.unified_shell_data import _compute_subsystem_criticality


def build_unified_app_shell(
    state: SystemState,
    *,
    rooms: list[dict[str, Any]] | None = None,
    subsystems: list[dict[str, Any]] | None = None,
    states_timeline: list[dict[str, Any]] | None = None,
    facility_coherence: float = 0.75,
    rooms_needing_attention: int = 0,
    timestamp: str | None = None,
    feed_latency_ms: int | None = None,
    current_state_insight: str = "System operating nominally",
    onset_insight: str = "Current state established 2h ago",
    coherence_insight: str = "Climate and irrigation well-integrated",
    primary_driver_insight: str = "Stable environmental equilibrium",
    operator_focus_insight: str = "Monitor irrigation timing in next cycle",
    path_outlook_insight: str = "Current trajectory stable through end of phase",
    critical_alerts: list[str] | None = None,
    records: list[dict[str, Any]] | None = None,
    no_action_projection: list[dict[str, Any]] | None = None,
    no_action_consequence_insight: str = "",
    recoverability_insight: str = "",
) -> dict[str, str]:
    """Build the unified app shell.

    Args:
        state: Current SystemState
        rooms: List of room status dicts
        subsystems: List of subsystem contribution dicts
        states_timeline: List of historical state dicts
        facility_coherence: Overall facility coherence score
        rooms_needing_attention: Count of rooms requiring attention
        timestamp: Last update timestamp
        feed_latency_ms: Feed latency in milliseconds
        current_state_insight: Current state description
        onset_insight: When/how current state began
        coherence_insight: System coherence assessment
        primary_driver_insight: What's driving current behavior
        operator_focus_insight: What operator should focus on
        path_outlook_insight: Projected system trajectory
        critical_alerts: Critical items to highlight

    Returns:
        Dictionary with HTML components:
            top_bar, system_field, left_panel, right_panel, bottom_timeline
    """

    rooms = rooms or []
    subsystems = subsystems or []
    states_timeline = states_timeline or []
    critical_alerts = critical_alerts or []

    coherence = getattr(state, "coherence", 0.75)
    drift = state.drift_intensity if state else 0.2
    stability = getattr(state, "stability", 0.8)

    system_state = "stable"
    if drift > 0.6:
        system_state = "critical"
    elif drift > 0.4:
        system_state = "instability"
    elif drift > 0.2:
        system_state = "drift"

    critical_subsystem, _ = _compute_subsystem_criticality(records)

    top_bar_html = render_facility_command_strip(
        rooms=rooms,
        facility_coherence=facility_coherence,
        rooms_needing_attention=rooms_needing_attention,
        timestamp=timestamp,
        feed_latency_ms=feed_latency_ms,
    )

    system_field_html = render_system_field_svg(
        coherence=coherence,
        drift=drift,
        stability=stability,
        state=system_state,
        width=1000,
        height=700,
        interactive=True,
        critical_subsystem_id=critical_subsystem,
        records=records,
        no_action_projection=no_action_projection,
    )

    left_panel_html = render_subsystem_influence_panel(
        subsystems=subsystems,
    )

    right_panel_html = render_intelligence_rail(
        current_state=current_state_insight,
        onset_description=onset_insight,
        coherence_assessment=coherence_insight,
        primary_driver=primary_driver_insight,
        operator_focus=operator_focus_insight,
        path_outlook=path_outlook_insight,
        critical_alerts=critical_alerts if critical_alerts else None,
        coherence_score=coherence,
        no_action_consequence=no_action_consequence_insight,
        recoverability_context=recoverability_insight,
    )

    bottom_timeline_html = render_state_timeline(
        states=states_timeline,
        current_index=len(states_timeline) - 1 if states_timeline else None,
        width=1400,
        height=140,
        no_action_projection=no_action_projection,
    )

    return {
        "top_bar": top_bar_html,
        "system_field": system_field_html,
        "left_panel": left_panel_html,
        "right_panel": right_panel_html,
        "bottom_timeline": bottom_timeline_html,
    }



