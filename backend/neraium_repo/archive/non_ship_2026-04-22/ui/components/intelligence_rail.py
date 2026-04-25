"""Intelligence Rail: Right-side floating panel with operator intelligence.

High-signal, machine-assisted reasoning about system state.
Sections:
- Current State: What the system is right now
- Onset: When did the current condition start
- Coherence: Overall system integration status
- Primary Driver: What's causing the observed behavior
- Operator Focus: What to pay attention to
- Path Outlook: Where is the system heading

Tone: Machine-assisted reasoning, not generic labels.
Examples of good insight:
- "Structural drift detected before threshold breach"
- "Coherence weakening across climate recovery and plant-layer response"
- "Recovery profile deviating from baseline"
- "Instability forming but still recoverable"
- "Current path remains recoverable if airflow normalizes within next cycle window"
"""

from __future__ import annotations

from typing import Any
from html import escape


def _render_intelligence_section(
    title: str,
    content: str,
    emphasis: str = "normal",
) -> str:
    """Render a single intelligence section.

    Args:
        title: Section title
        content: Main content (plain text)
        emphasis: "normal", "elevated", or "critical"

    Returns:
        HTML markup for the section
    """

    emphasis_colors = {
        "normal": {"bg": "rgba(15,23,42,0.4)", "border": "rgba(148,163,184,0.2)"},
        "elevated": {"bg": "rgba(59,130,246,0.08)", "border": "rgba(59,130,246,0.3)"},
        "critical": {"bg": "rgba(239,68,68,0.08)", "border": "rgba(239,68,68,0.3)"},
    }
    colors = emphasis_colors.get(emphasis, emphasis_colors["normal"])

    html = f"""
    <div class="ner-intelligence-section" data-emphasis="{escape(emphasis)}">
        <div class="ner-section-header" style="border-color: {colors["border"]};">
            <h4 class="ner-section-title">{escape(title)}</h4>
        </div>
        <div class="ner-section-content" style="background-color: {colors["bg"]};">
            <p class="ner-section-text">{escape(content)}</p>
        </div>
    </div>
    """
    return html


def render_intelligence_rail(
    current_state: str,
    onset_description: str,
    coherence_assessment: str,
    primary_driver: str,
    operator_focus: str,
    path_outlook: str,
    critical_alerts: list[str] | None = None,
    coherence_score: float = 0.75,
    no_action_consequence: str = "",
    recoverability_context: str = "",
) -> str:
    """Render the intelligence rail with counterfactual awareness and recoverability context.

    Args:
        current_state: Description of current system state
        onset_description: When and how current condition started
        coherence_assessment: Assessment of system coherence/integration
        primary_driver: What's the primary cause of current behavior
        operator_focus: What should the operator focus on
        path_outlook: Where is the system heading / what's the trajectory
        critical_alerts: Optional list of critical items to highlight
        coherence_score: System coherence (0-1) for reactive styling
        no_action_consequence: What happens if no intervention occurs
        recoverability_context: Context on system recoverability window

    Returns:
        HTML markup for the intelligence rail
    """

    sections = [
        ("Current State", current_state, "normal"),
        ("Onset", onset_description, "normal"),
        ("Coherence", coherence_assessment, "normal"),
        ("Primary Driver", primary_driver, "normal"),
        ("Operator Focus", operator_focus, "elevated"),
        ("Path Outlook", path_outlook, "normal"),
    ]

    if recoverability_context:
        emphasis = "critical" if "closing" in recoverability_context.lower() or "immediately" in recoverability_context.lower() else "elevated"
        sections.append(("Recoverability", recoverability_context, emphasis))

    if no_action_consequence:
        sections.append(("No-Action Consequence", no_action_consequence, "elevated"))

    emphasis_level = "normal"
    if critical_alerts:
        emphasis_level = "critical"
    elif coherence_score < 0.4:
        emphasis_level = "critical"
    elif coherence_score < 0.6:
        emphasis_level = "elevated"

    coherence_level_attr = "critical" if coherence_score < 0.4 else "low" if coherence_score < 0.6 else "normal"

    sections_html = "\n".join(
        _render_intelligence_section(title, content, emphasis)
        for title, content, emphasis in sections
    )

    alerts_html = ""
    if critical_alerts:
        alerts_items = "\n".join(
            f'<li class="ner-alert-item">{escape(alert)}</li>'
            for alert in critical_alerts
        )
        alerts_html = f"""
        <div class="ner-critical-alerts">
            <div class="ner-alerts-header">⚠️ Critical Items</div>
            <ul class="ner-alerts-list">
                {alerts_items}
            </ul>
        </div>
        """

    html = f"""
    <div class="ner-intelligence-rail" data-coherence-level="{coherence_level_attr}" data-emphasis="{emphasis_level}">
        <div class="ner-rail-header">
            <h3 class="ner-rail-title">Operator Intelligence</h3>
            <span class="ner-rail-subtitle">Machine-assisted reasoning</span>
        </div>

        {alerts_html}

        <div class="ner-rail-sections">
            {sections_html}
        </div>

        <div class="ner-rail-footer">
            <span class="ner-footer-note">All assessments reflect current telemetry</span>
        </div>
    </div>
    """
    return html
