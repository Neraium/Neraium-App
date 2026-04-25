"""Subsystem Influence Panel: Left-side floating panel.

Shows the influence contributions of each subsystem on overall system state.
Each entry displays:
- Subsystem/room name
- Current condition (metric value)
- Behavioral state (what's happening)
- Drift contribution % (how much drift is this subsystem causing)
- Confidence % (how confident in this measurement)
- Brief explanation
- Micro-state indicator (visual spark showing activity level)

These visually connect to the tetrahedron vertices and serve as
exploratory entry points into system behavior.
"""

from __future__ import annotations

from typing import Any
from html import escape


def _render_subsystem_entry(
    subsystem_id: str,
    subsystem_name: str,
    condition: str,
    behavioral_state: str,
    drift_contribution_pct: float,
    confidence_pct: float,
    explanation: str,
    micro_activity: float,
) -> str:
    """Render a single subsystem influence entry.

    Args:
        subsystem_id: Unique subsystem ID
        subsystem_name: Display name
        condition: Current condition description
        behavioral_state: What's happening (e.g., "Stabilizing", "Recovering", "Drifting")
        drift_contribution_pct: Percentage of drift from this subsystem
        confidence_pct: Confidence in the assessment
        explanation: Brief explanation of current behavior
        micro_activity: Activity level 0-1 (higher = more active/changing)

    Returns:
        HTML markup for the entry
    """

    activity_color = "#22C55E" if micro_activity < 0.3 else "#3B82F6" if micro_activity < 0.6 else "#F97316"

    strain_indicator = ""
    if drift_contribution_pct > 40:
        strain_opacity = min(0.6, (drift_contribution_pct - 40) / 20)
        strain_indicator = f"""
        <div class="ner-subsystem-strain" style="opacity: {strain_opacity};">
            <span class="ner-strain-marker">⚡</span>
            <span class="ner-strain-label">Residual strain detected</span>
        </div>
        """

    html = f"""
    <div class="ner-subsystem-entry" data-subsystem="{escape(subsystem_id)}" data-strain-level="{min(100, drift_contribution_pct)}">
        <div class="ner-subsystem-header">
            <div class="ner-subsystem-name">{escape(subsystem_name)}</div>
            <div class="ner-micro-activity" style="background-color: {activity_color}; opacity: {0.4 + micro_activity * 0.6}"></div>
        </div>

        <div class="ner-subsystem-condition">
            <span class="ner-condition-label">Condition</span>
            <span class="ner-condition-value">{escape(condition)}</span>
        </div>

        <div class="ner-subsystem-state">
            <span class="ner-state-label">State</span>
            <span class="ner-state-value">{escape(behavioral_state)}</span>
        </div>

        {strain_indicator}

        <div class="ner-subsystem-metrics">
            <div class="ner-metric-row">
                <span class="ner-metric-label">Drift Contribution</span>
                <span class="ner-metric-value">{drift_contribution_pct:.0f}%</span>
            </div>
            <div class="ner-metric-bar">
                <div class="ner-metric-fill" style="width: {min(drift_contribution_pct, 100)}%;"></div>
            </div>

            <div class="ner-metric-row" style="margin-top: 8px;">
                <span class="ner-metric-label">Confidence</span>
                <span class="ner-metric-value">{confidence_pct:.0f}%</span>
            </div>
            <div class="ner-metric-bar">
                <div class="ner-metric-fill" style="width: {min(confidence_pct, 100)}%; background-color: #3B82F6;"></div>
            </div>
        </div>

        <div class="ner-subsystem-explanation">
            {escape(explanation)}
        </div>
    </div>
    """
    return html


def render_subsystem_influence_panel(
    subsystems: list[dict[str, Any]],
) -> str:
    """Render the subsystem influence panel.

    Args:
        subsystems: List of subsystem dicts with keys:
            subsystem_id, subsystem_name, condition, behavioral_state,
            drift_contribution_pct, confidence_pct, explanation, micro_activity

    Returns:
        HTML markup for the influence panel
    """

    entries = [
        _render_subsystem_entry(
            subsystem.get("subsystem_id", f"subsys_{i}"),
            subsystem.get("subsystem_name", f"Subsystem {i+1}"),
            subsystem.get("condition", "Normal"),
            subsystem.get("behavioral_state", "Stable"),
            float(subsystem.get("drift_contribution_pct", 0.0)),
            float(subsystem.get("confidence_pct", 75.0)),
            subsystem.get("explanation", "No additional notes."),
            float(subsystem.get("micro_activity", 0.2)),
        )
        for i, subsystem in enumerate(subsystems)
    ]

    html = f"""
    <div class="ner-subsystem-influence-panel">
        <div class="ner-panel-header">
            <h3 class="ner-panel-title">Subsystem Influence</h3>
            <span class="ner-panel-subtitle">Contributing factors to system behavior</span>
        </div>

        <div class="ner-subsystem-list">
            {"".join(entries)}
        </div>

        <div class="ner-panel-footer">
            <span class="ner-footer-note">Click any subsystem to focus analysis on its dynamics</span>
        </div>
    </div>
    """
    return html
