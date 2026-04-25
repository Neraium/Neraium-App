from __future__ import annotations

from html import escape
import math
from pathlib import Path
import time
from typing import Any

from ui.config import UIConfig
from ui.components.tetrahedral_viz import build_tetrahedral_plot_and_text
from ui.core_integration import build_system_state, evaluate_gate
from ui.demo_data import load_fd004_demo_records, load_greenhouse_demo_records
from ui.layouts.operations_view import build_operations_view
from ui.layouts.unified_app_shell import build_unified_app_shell
from ui.reasoning import build_reasoning_context
from ui.replay_timing import (
    ReplayPaceController,
    VerdictStabilizer,
    ReasoningStateTracker,
    SmoothUIFrameController,
    InterpolationHelper,
)
from ui.unified_shell_data import (
    build_facility_rooms_data,
    build_subsystems_data,
    build_timeline_states,
    build_intelligence_insights,
    get_critical_alerts,
    _compute_time_to_consequence,
    _compute_no_action_projection,
)


def load_builtin_demo_rows(use_synthetic: bool = True) -> list[dict[str, Any]]:
    """Return greenhouse replay sequence.

    Args:
        use_synthetic: If True, return synthetic demo (clear progression);
                      if False, return real replay from greenhouse_results_turbo.csv

    Returns:
        List of replay records with full UI contract fields
    """
    data_rows = load_greenhouse_demo_records(limit=180, use_synthetic=use_synthetic)
    if data_rows:
        return data_rows
    return [
        {
            "timestamp": "2026-04-10T00:00:00Z",
            "regime_name": "baseline",
            "system_health": "nominal",
            "confidence_score": 0.71,
            "structural_drift_score": 0.22,
            "relational_stability_score": 0.84,
            "coherence_score": 0.87,
            "snr_score": 1.65,
            "persistence_minutes": 0,
            "corroborating_signal_count": 0,
            "event_admitted": False,
            "transition_type": "STABLE",
            "evidence_summary": "Stable baseline: drift low, stability and coherence high.",
        },
        {
            "timestamp": "2026-04-10T00:05:00Z",
            "regime_name": "transition_watch",
            "system_health": "watch",
            "confidence_score": 0.68,
            "structural_drift_score": 0.58,
            "relational_stability_score": 0.44,
            "coherence_score": 0.56,
            "snr_score": 1.62,
            "persistence_minutes": 12,
            "corroborating_signal_count": 1,
            "event_admitted": False,
            "transition_type": "TRANSITION",
            "evidence_summary": "Rising drift with weak corroboration; transition signal is currently suppressed.",
        },
        {
            "timestamp": "2026-04-10T00:12:00Z",
            "regime_name": "reorganization_candidate",
            "system_health": "degraded",
            "confidence_score": 0.79,
            "structural_drift_score": 0.77,
            "relational_stability_score": 0.27,
            "coherence_score": 0.74,
            "snr_score": 2.1,
            "persistence_minutes": 44,
            "corroborating_signal_count": 3,
            "event_admitted": True,
            "transition_type": "REORGANIZATION",
            "evidence_summary": "Persistence and corroboration now qualify a coherent reorganization; transition admitted.",
        },
    ]


def _fallback_gate_decision() -> dict[str, Any]:
    return {
        "decision": "SUPPRESS",
        "doctrine_version": "unknown",
        "criteria_results": {},
        "refusal_reason": "No admitted telemetry row is available for evaluation.",
        "explanation": "Suppressed: no current admitted telemetry is available.",
        "observed_facts": ["No current record was provided to the UI integration layer."],
        "uncertainty_notes": ["Gate evaluation used conservative fallback behavior."],
        "candidate_assertion_allowed": False,
        "confidence_label": "low",
        "timestamp": None,
        "transition": {
            "type": "STABLE",
            "delta_drift": 0.0,
            "delta_stability": 0.0,
            "delta_coherence": 0.0,
        },
    }


def create_app_state(records=None):
    """
    Minimal integration-safe builder used by INTEGRATION_GUIDE.py.
    Accepts either:
    - a list of records
    - a single record dict
    - empty input (loads built-in demo rows)
    - unknown invalid input (falls back to suppressed gate decision)
    """
    if isinstance(records, list) and len(records) > 0:
        latest = records[-1]
        previous = records[-2] if len(records) > 1 else None
        rows = records
    elif isinstance(records, dict):
        latest = records
        previous = None
        rows = [records]
    elif records is None or records == []:
        rows = load_builtin_demo_rows()
        latest = rows[-1]
        previous = rows[-2] if len(rows) > 1 else None
    else:
        rows = []
        latest = {}
        previous = None

    replay_story = {
        "state_transitions": [str(row.get("regime_name") or row.get("state") or "unknown") for row in rows],
        "drift_trend": [
            float(row.get("structural_drift_score"))
            for row in rows
            if isinstance(row.get("structural_drift_score"), (int, float))
        ],
    }

    summary = {
        "timestamp": latest.get("timestamp"),
        "site_id": latest.get("site_id"),
        "asset_id": latest.get("asset_id"),
        "system_health": latest.get("system_health"),
        "confidence": latest.get("confidence_score"),
        "drift": latest.get("structural_drift_score"),
        "stability": latest.get("relational_stability_score"),
        "regime": latest.get("regime_name"),
        "replay_story": replay_story,
    }

    if rows:
        system_state = build_system_state(rows, config=UIConfig())
        gate_decision = evaluate_gate(latest, previous, system_state)
        if not isinstance(gate_decision, dict) or not gate_decision:
            gate_decision = _fallback_gate_decision()
        reasoning_context: dict[str, Any] = build_reasoning_context(system_state, rows, gate_decision=gate_decision)
        if not isinstance(reasoning_context, dict) or not reasoning_context:
            reasoning_context = {
                "current_state": summary,
                "gate_decision": {
                    "decision": gate_decision.get("decision") or "SUPPRESS",
                    "reason": gate_decision.get("reason") or gate_decision.get("refusal_reason"),
                },
                "recent_admitted_events": [],
                "operational_implication": "Demo fallback reasoning context.",
            }
    else:
        gate_decision = _fallback_gate_decision()
        reasoning_context = {
            "current_state": {
                "timestamp": None,
                "regime": None,
                "system_health": None,
                "confidence": None,
                "drift": None,
                "stability": None,
            },
            "gate_decision": {
                "decision": gate_decision.get("decision"),
                "reason": gate_decision.get("refusal_reason"),
                "doctrine_version": gate_decision.get("doctrine_version"),
                "confidence_label": gate_decision.get("confidence_label"),
            },
            "recent_admitted_events": [],
            "transition_point": None,
            "drift_summary": "No admitted drift evidence is available.",
            "stability_summary": "No admitted stability evidence is available.",
            "top_contributing_signals": None,
            "chart_replay_summary": None,
        }

    return {
        "summary": summary,
        "reasoning_context": reasoning_context,
        "gate_decision": gate_decision,
        "realtime": {
            "enabled": False,
        },
    }


def create_ui_model(data):
    return {
        "summary": data[-1] if isinstance(data, list) and data else (data if isinstance(data, dict) else {}),
        "realtime": {"enabled": False},
    }


def _render_gate_decision_html(gate_card: dict[str, Any]) -> str:
    """Render the verdict/gate decision card with maximum visual authority.

    Uses:
    - Pure white text (#FFFFFF) on dark backgrounds
    - Large, bold fonts for decisive readability
    - Sharp color states: green (stable), orange (transition), red (risk), purple (void)
    - No soft overlays or gradients
    """
    authority_level = str(gate_card.get("authority_level") or "VOID").upper()
    style = {
        "SUPPRESSED": {"accent": "#F97316", "badge": "#F97316"},
        "ADMITTED": {"accent": "#22C55E", "badge": "#22C55E"},
        "VOID": {"accent": "#A78BFA", "badge": "#A78BFA"},
    }.get(authority_level, {"accent": "#3B82F6", "badge": "#3B82F6"})

    label = escape(str(gate_card.get("label") or authority_level))
    authority_statement = escape(str(gate_card.get("authority_statement") or ""))
    supporting_line = escape(str(gate_card.get("supporting_line") or ""))

    # Use system state confidence score as single source of truth
    raw_confidence_score = gate_card.get("system_confidence_score", gate_card.get("confidence_score"))
    if raw_confidence_score is None:
        # Fallback to gate's confidence label if score not available
        confidence = escape(str(gate_card.get("confidence") or "LOW"))
    else:
        # Convert score to label
        try:
            conf_val = float(raw_confidence_score)
            if conf_val >= 0.70:
                confidence = "HIGH"
            elif conf_val >= 0.50:
                confidence = "MODERATE"
            else:
                confidence = "LOW"
        except (TypeError, ValueError):
            confidence = "LOW"

    transition_type = escape(str(gate_card.get("transition_type") or "STABLE"))
    risk_direction = escape(str(gate_card.get("risk_direction") or "UNCERTAIN"))
    ts_meta = str(gate_card.get("timestamp_display") or "").replace("Change evaluated at: ", "").strip()
    ts_display = escape(ts_meta) if ts_meta else "â€”"
    doctrine_version = escape(str(gate_card.get("doctrine_version") or "â€”"))
    system_insights = gate_card.get("system_insights") if isinstance(gate_card.get("system_insights"), dict) else {}

    def _chip(label_text: str, value: str, accent_color: str) -> str:
        """Render a higher-contrast information chip."""
        return (
            f'<span class="ner-chip" style="--chip-accent:{accent_color};">'
            f'<span class="ner-chip-label">{escape(label_text)}</span>'
            f'<span class="ner-chip-value">{escape(value)}</span>'
            f"</span>"
        )

    accent = style["accent"]
    dominant_state = escape(str(system_insights.get("system_state") or "Unknown"))
    dominant_state_html = (
        '<div style="margin:14px 0 10px 0;padding:12px 14px;border:1px solid rgba(255,255,255,0.2);'
        'border-radius:8px;background:rgba(15,23,42,0.75);display:flex;justify-content:space-between;align-items:center;">'
        '<span style="font-size:11px;letter-spacing:0.08em;color:#94a3b8;font-weight:700;text-transform:uppercase;">System State</span>'
        f'<span style="font-size:20px;font-weight:800;color:#f8fafc;letter-spacing:0.02em;">{dominant_state}</span>'
        '</div>'
    )

    insight_section = ""
    metrics = system_insights.get("metrics") if isinstance(system_insights.get("metrics"), list) else []
    if system_insights:
        rows = []
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            trend = metric.get("trend") if isinstance(metric.get("trend"), dict) else {}
            arrow = escape(str(trend.get("arrow") or "â†’"))
            trend_label = escape(str(trend.get("label") or "Stable"))
            mlabel = escape(str(metric.get("label") or "Metric"))
            mvalue = escape(str(metric.get("value") or "0"))
            rows.append(
                '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;'
                'border-bottom:1px solid rgba(148,163,184,0.14);">'
                f'<span style="color:#cbd5e1;font-size:12px;">{mlabel}</span>'
                f'<span style="color:#f8fafc;font-size:12px;font-weight:700;">{arrow} {mvalue} Â· {trend_label}</span>'
                '</div>'
            )
        phase_context = escape(str(system_insights.get("phase_context") or "â€”"))
        timestamp_display = escape(str(system_insights.get("timestamp_display") or "â€”"))
        insight_text = escape(str(system_insights.get("insight_text") or "â€”"))
        decision_line = escape(str(system_insights.get("decision") or "Decision: Accepted"))
        transition_line = escape(str(system_insights.get("state_transition") or "State Transition: Confirmed"))
        insight_section = (
            '<div style="margin-top:10px;padding:12px;border:1px solid rgba(148,163,184,0.22);'
            'border-radius:8px;background:rgba(2,6,23,0.65);">'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#dbeafe;font-weight:600;">'
            f'<span>{decision_line}</span><span>{transition_line}</span></div>'
            f'<div style="margin-top:8px;font-size:12px;color:#94a3b8;">Phase Context: '
            f'<span style="color:#e2e8f0;font-weight:600;">{phase_context}</span></div>'
            f'<div style="margin-top:8px;">{"".join(rows)}</div>'
            f'<div style="margin-top:8px;font-size:12px;color:#94a3b8;">Last Evaluated: '
            f'<span style="color:#e2e8f0;font-weight:600;">{timestamp_display}</span></div>'
            f'<div style="margin-top:8px;padding:8px;border-left:3px solid {accent};'
            f'background:rgba(30,41,59,0.45);font-size:12px;color:#e2e8f0;">'
            f'<strong>System Insight:</strong> {insight_text}</div>'
            '</div>'
        )

    return f"""
<div class="ner-panel ner-verdict-card" style="--verdict-accent:{accent};">
  <div class="ner-verdict-main">{label}</div>
  <div class="ner-verdict-subtitle">{authority_statement}</div>
  <div class="ner-verdict-supporting">{supporting_line}</div>
  {dominant_state_html}
  <div class="ner-chip-row">
    {_chip("Confidence", confidence, accent)}
    {_chip("State Transition", "Confirmed", accent)}
    {_chip("Risk", risk_direction, accent)}
  </div>
  {insight_section}
  <div class="ner-meta-row">
    <span>{ts_display}</span>
    <span>Engine {doctrine_version}</span>
  </div>
</div>
""".strip()


def _render_system_geometry_html(system_zone: dict[str, Any]) -> str:
    """Render directional system-state triangle with trend interpretation."""
    content = system_zone.get("content") if isinstance(system_zone, dict) else {}
    if not isinstance(content, dict):
        content = {}

    metrics = content.get("metrics", {}) if isinstance(content.get("metrics"), dict) else {}
    triangle_state = content.get("triangle_state", {}) if isinstance(content.get("triangle_state"), dict) else {}
    interpretation = content.get("interpretation", {}) if isinstance(content.get("interpretation"), dict) else {}
    global_state = str(content.get("global_state") or "Stable")

    drift_intensity = float(metrics.get("drift_intensity", 0.0))
    stability = float(metrics.get("stability", 1.0))
    coherence = float(metrics.get("structure_coherence", 0.0))
    confidence = float(metrics.get("confidence", 0.0))
    drift_delta = float(metrics.get("drift_delta", 0.0))
    stability_delta = float(metrics.get("stability_delta", 0.0))
    coherence_delta = float(metrics.get("coherence_delta", 0.0))

    labels = triangle_state.get("labels", {}) if isinstance(triangle_state.get("labels"), dict) else {}
    current = triangle_state.get("current_point", {}) if isinstance(triangle_state.get("current_point"), dict) else {}
    previous = triangle_state.get("previous_point", {}) if isinstance(triangle_state.get("previous_point"), dict) else {}
    warp = triangle_state.get("geometry_warp", {}) if isinstance(triangle_state.get("geometry_warp"), dict) else {}
    current_x = float(current.get("x", 0.5))
    current_y = float(current.get("y", 0.5))
    previous_x = float(previous.get("x", current_x))
    previous_y = float(previous.get("y", current_y))

    def _drift_color(value: float) -> str:
        if value < 0.28:
            return "#38BDF8"
        if value < 0.52:
            return "#A78BFA"
        if value < 0.72:
            return "#FB923C"
        return "#EF4444"

    drift_color = _drift_color(drift_intensity)
    state_styles = {
        "Baseline": ("#22C55E", "rgba(34,197,94,0.22)"),
        "Stable": ("#38BDF8", "rgba(56,189,248,0.2)"),
        "Drifting": ("#FB923C", "rgba(251,146,60,0.22)"),
        "Alert": ("#EF4444", "rgba(239,68,68,0.24)"),
    }
    state_accent, state_bg = state_styles.get(global_state, ("#38BDF8", "rgba(56,189,248,0.2)"))
    drift_glow = 0.22 + (drift_intensity * 0.5)

    W, H = 860, 390
    cx = lambda x: round(x * W, 2)
    cy = lambda y: round(y * H, 2)
    drift_pull = float(warp.get("drift_pull", 0.0))
    coherence_collapse = float(warp.get("coherence_collapse", 0.0))
    top = (0.5 + drift_pull * 0.6, 0.14 + coherence_collapse * 0.3)
    left = (0.18 - coherence_collapse, 0.84 + coherence_collapse * 0.5)
    right = (0.82 + drift_pull, 0.84 + coherence_collapse * 0.45)

    parts: list[str] = []
    parts.append(
        '<defs>'
        '<marker id="trendArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 Z" fill="{drift_color}" opacity="0.9"/>'
        '</marker>'
        '<linearGradient id="triStroke" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="rgba(148,163,184,0.65)"/>'
        '<stop offset="100%" stop-color="rgba(148,163,184,0.3)"/>'
        '</linearGradient>'
        f'<filter id="driftGlow"><feGaussianBlur stdDeviation="{2.8 + drift_intensity * 3.5:.2f}" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '</defs>'
    )

    parts.append('<rect x="28" y="24" width="560" height="340" rx="12" fill="rgba(2,6,23,0.88)" stroke="rgba(148,163,184,0.2)"/>')
    parts.append(
        f'<polygon points="{cx(top[0])},{cy(top[1])} {cx(left[0])},{cy(left[1])} {cx(right[0])},{cy(right[1])}" '
        f'fill="rgba(15,23,42,0.74)" stroke="url(#triStroke)" stroke-width="2.2"/>'
    )

    parts.append(
        f'<polyline points="{cx(previous_x)},{cy(previous_y)} {cx((previous_x + current_x) / 2)},{cy((previous_y + current_y) / 2)} {cx(current_x)},{cy(current_y)}" '
        'fill="none" stroke="rgba(148,163,184,0.38)" stroke-width="3.2" stroke-dasharray="4,5"/>'
    )
    parts.append(
        f'<line x1="{cx(previous_x)}" y1="{cy(previous_y)}" x2="{cx(current_x)}" y2="{cy(current_y)}" '
        f'stroke="{drift_color}" stroke-width="2.2" marker-end="url(#trendArrow)" opacity="0.85"/>'
    )
    parts.append(
        f'<circle cx="{cx(previous_x)}" cy="{cy(previous_y)}" r="9" fill="rgba(148,163,184,0.2)" stroke="rgba(148,163,184,0.55)" stroke-width="1.5"/>'
    )
    parts.append(
        f'<circle cx="{cx(current_x)}" cy="{cy(current_y)}" r="{10 + drift_intensity * 6:.1f}" fill="{drift_color}" opacity="{0.28 + drift_glow:.3f}" filter="url(#driftGlow)"/>'
    )
    parts.append(
        f'<circle cx="{cx(current_x)}" cy="{cy(current_y)}" r="8.2" fill="{drift_color}" stroke="#E2E8F0" stroke-width="2"/>'
    )

    parts.append(f'<text x="{cx(top[0])}" y="{cy(top[1]) - 12}" text-anchor="middle" fill="#CFE3FF" font-size="12" font-weight="700">{escape(str(labels.get("top", "Stability")))}</text>')
    parts.append(f'<text x="{cx(left[0]) - 8}" y="{cy(left[1]) + 20}" text-anchor="end" fill="#CFE3FF" font-size="12" font-weight="700">{escape(str(labels.get("left", "Coherence")))}</text>')
    parts.append(f'<text x="{cx(right[0]) + 8}" y="{cy(right[1]) + 20}" text-anchor="start" fill="{drift_color}" font-size="12" font-weight="800">{escape(str(labels.get("right", "Drift")))}</text>')
    parts.append(
        f'<circle cx="{cx(0.5)}" cy="{cy(0.58)}" r="24" fill="{state_bg}" stroke="{state_accent}" stroke-width="1.2"/>'
        f'<text x="{cx(0.5)}" y="{cy(0.58) - 2}" text-anchor="middle" fill="#E2E8F0" font-size="9" font-weight="700">{escape(str(labels.get("center", "System State")))}</text>'
        f'<text x="{cx(0.5)}" y="{cy(0.58) + 12}" text-anchor="middle" fill="{state_accent}" font-size="12" font-weight="800">{escape(global_state.upper())}</text>'
    )
    parts.append(f'<text x="{cx(previous_x) - 10}" y="{cy(previous_y) - 10}" fill="rgba(148,163,184,0.86)" font-size="10">prev</text>')
    parts.append(f'<text x="{cx(current_x) + 10}" y="{cy(current_y) - 10}" fill="{drift_color}" font-size="10" font-weight="700">now</text>')

    svg_body = "\n".join(parts)
    svg_html = f'<svg class="ner-system-canvas ner-system-canvas--triangle" viewBox="0 0 {W} {H}" width="100%">\n{svg_body}\n</svg>'

    trend_rows = (
        f'<li>{escape(str(interpretation.get("stability") or "Stability: unavailable"))}</li>'
        f'<li>{escape(str(interpretation.get("drift") or "Drift: unavailable"))}</li>'
        f'<li>{escape(str(interpretation.get("coherence") or "Coherence: unavailable"))}</li>'
        f'<li>{escape(str(interpretation.get("state") or f"State: {global_state}"))}</li>'
    )
    interpretation_html = (
        '<div class="ner-system-interpretation">'
        '<h4>Interpretation</h4>'
        f'<ul>{trend_rows}</ul>'
        '<div class="ner-delta-row">'
        f'<span>Î”Drift {drift_delta:+.3f}</span>'
        f'<span>Î”Stability {stability_delta:+.3f}</span>'
        f'<span>Î”Coherence {coherence_delta:+.3f}</span>'
        '</div>'
        '</div>'
    )

    indicator_html = (
        f'<div class="ner-global-state-indicator" style="--state-accent:{state_accent};--state-bg:{state_bg};">'
        '<span class="ner-global-state-label">Overall System State</span>'
        f'<strong>{escape(global_state)}</strong>'
        f'<small>Confidence {confidence:.2f} â€¢ Drift {drift_intensity:.2%} â€¢ Coherence {coherence:.2%}</small>'
        '</div>'
    )

    header_html = (
        '<div class="ner-panel-head">'
        '<div>'
        '<span class="ner-eyebrow">System State Triangle</span>'
        '<span>Directional evolution across stability, coherence, and drift with trend context.</span>'
        '</div>'
        '</div>'
    )

    return (
        f'<div class="ner-panel ner-system-panel">'
        f'{header_html}'
        f'{indicator_html}'
        f'<div class="ner-system-main-row">{svg_html}{interpretation_html}</div>'
        f'</div>'
    )


def _render_system_context_html(system_zone: dict[str, Any]) -> str:
    content = system_zone.get("content") if isinstance(system_zone, dict) else {}
    timeline_data = system_zone.get("timeline_strip") if isinstance(system_zone, dict) else {}
    if not isinstance(content, dict):
        content = {}
    if not isinstance(timeline_data, dict):
        timeline_data = {}

    def _f(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _cl(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    replay_series = content.get("replay_series") if isinstance(content.get("replay_series"), list) else []
    trajectory = content.get("trajectory") if isinstance(content.get("trajectory"), dict) else {}
    path = trajectory.get("path") if isinstance(trajectory.get("path"), list) else []
    points_source = replay_series if replay_series else [{"index": idx, "signal": _f(p.get("x"), 0.0), "phase": "unknown"} for idx, p in enumerate(path) if isinstance(p, dict)]

    chart_points: list[dict[str, Any]] = []
    for idx, point in enumerate(points_source):
        if not isinstance(point, dict):
            continue
        drift_value = _cl(_f(point.get("drift"), _f(point.get("signal"), _f(point.get("y"), 0.0))), 0.0, 1.0)
        stability_value = _cl(_f(point.get("stability"), 1.0 - drift_value), 0.0, 1.0)
        chart_points.append(
            {
                "index": idx,
                "drift": drift_value,
                "stability": stability_value,
                "signal": _cl(_f(point.get("signal"), drift_value), 0.0, 1.0),
                "phase": str(point.get("phase") or "unknown").upper(),
                "timestamp": str(point.get("timestamp") or ""),
                "event_admitted": bool(point.get("event_admitted")),
            }
        )

    point_count = len(chart_points)
    if point_count == 0:
        chart_points = [{"index": 0, "drift": 0.0, "stability": 1.0, "signal": 0.0, "phase": "UNKNOWN", "timestamp": "", "event_admitted": False}]
        point_count = 1

    transition_frame: int | None = None
    for point in chart_points:
        phase = str(point.get("phase") or "").upper()
        if phase in {"TRANSITION", "REORGANIZATION"} or bool(point.get("event_admitted")):
            transition_frame = int(point.get("index", 0))
            break
    if transition_frame is None and point_count >= 3:
        for point in chart_points:
            if _f(point.get("drift")) >= _f(point.get("stability")):
                transition_frame = int(point.get("index", 0))
                break

    axis_mode = "cycles_to_transition" if transition_frame is not None else "lifecycle_progress_pct"
    center_transition = bool(content.get("center_transition_axis"))

    for point in chart_points:
        idx = int(point.get("index", 0))
        if transition_frame is not None:
            x_value = float(transition_frame - idx)
            if center_transition:
                x_value = float(idx - transition_frame)
            point["x_value"] = x_value
            point["x_label"] = f"{int(round(x_value)):+d}" if x_value != 0 else "0"
        else:
            x_value = (idx / max(point_count - 1, 1)) * 100.0
            point["x_value"] = x_value
            point["x_label"] = f"{x_value:.0f}%"

    for idx, point in enumerate(chart_points):
        if idx == 0:
            slope = 0.0
        else:
            prev_drift = _f(chart_points[idx - 1].get("drift"), 0.0)
            slope = _f(point.get("drift"), 0.0) - prev_drift
        point["drift_slope"] = slope
        point["abs_slope"] = abs(slope)

    x_values = [_f(p.get("x_value"), 0.0) for p in chart_points]
    y_values = [_f(p.get("drift"), 0.0) for p in chart_points] + [_f(p.get("stability"), 0.0) for p in chart_points] + [_f(p.get("drift_slope"), 0.0) for p in chart_points]
    y_min = min(y_values) if y_values else 0.0
    y_max = max(y_values) if y_values else 1.0
    y_span = max(y_max - y_min, 0.08)
    y_pad = min(max(y_span * 0.12, 0.02), 0.16)
    y_domain_min = y_min - y_pad
    y_domain_max = y_max + y_pad

    min_chart_width = 1400
    px_per_frame = 8
    W = max(min_chart_width, point_count * px_per_frame)
    H = 360
    PX, PY = 92, 48
    IW = max(W - 2 * PX, 1)
    IH = max(H - 2 * PY, 1)

    x_min = min(x_values) if x_values else 0.0
    x_max = max(x_values) if x_values else 1.0
    x_span = max(x_max - x_min, 1e-9)

    def sx(x: float) -> float:
        return round(PX + ((x - x_min) / x_span) * IW, 2)

    def sy(y: float) -> float:
        return round(PY + IH - ((_cl(y, y_domain_min, y_domain_max) - y_domain_min) / max(y_domain_max - y_domain_min, 1e-9)) * IH, 2)

    def _series_points(key: str) -> str:
        return " ".join(f"{sx(_f(p.get('x_value'), 0.0))},{sy(_f(p.get(key), 0.0))}" for p in chart_points)

    transition_x = sx(0.0) if axis_mode == "cycles_to_transition" else None
    current = chart_points[-1]
    current_x = sx(_f(current.get("x_value"), 0.0))
    current_y_drift = sy(_f(current.get("drift"), 0.0))

    max_abs_slope = max((_f(p.get("abs_slope"), 0.0) for p in chart_points), default=1.0)
    max_abs_slope = max(max_abs_slope, 1e-6)

    parts: list[str] = []
    parts.append(
        '<defs>'
        '<linearGradient id="gridFade" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="rgba(148,163,184,0.26)"/>'
        '<stop offset="100%" stop-color="rgba(148,163,184,0.09)"/>'
        '</linearGradient>'
        '<linearGradient id="driftStroke" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#64748B" stop-opacity="0.36"/>'
        '<stop offset="60%" stop-color="#38BDF8" stop-opacity="0.86"/>'
        '<stop offset="100%" stop-color="#06B6D4" stop-opacity="1"/>'
        '</linearGradient>'
        '<linearGradient id="stabilityStroke" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#94A3B8" stop-opacity="0.3"/>'
        '<stop offset="70%" stop-color="#22C55E" stop-opacity="0.74"/>'
        '<stop offset="100%" stop-color="#86EFAC" stop-opacity="0.88"/>'
        '</linearGradient>'
        '<filter id="transitionGlow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="6" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>'
    )

    y_tick_count = 5
    y_ticks = [y_domain_min + (i / y_tick_count) * (y_domain_max - y_domain_min) for i in range(y_tick_count + 1)]
    for y_tick in y_ticks:
        y_pos = sy(y_tick)
        parts.append(f'<line x1="{PX}" y1="{y_pos}" x2="{PX + IW}" y2="{y_pos}" stroke="url(#gridFade)" stroke-width="1"/>')
        parts.append(f'<text x="{PX - 12}" y="{y_pos + 4}" text-anchor="end" fill="rgba(226,232,240,0.95)" font-size="11">{y_tick:.2f}</text>')

    x_ticks: list[float] = []
    if axis_mode == "cycles_to_transition":
        if transition_frame is not None:
            start_cycle = int(round(max(x_values)))
            end_cycle = int(round(min(x_values)))
            step = max(int(round((start_cycle - end_cycle) / 6.0)), 1)
            x_ticks = [float(v) for v in range(start_cycle, end_cycle - 1, -step)]
            if 0.0 not in x_ticks:
                x_ticks.append(0.0)
            x_ticks = sorted(set(x_ticks), reverse=True)
    else:
        x_ticks = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]

    for x_tick in x_ticks:
        x_pos = sx(x_tick)
        parts.append(f'<line x1="{x_pos}" y1="{PY}" x2="{x_pos}" y2="{PY + IH}" stroke="rgba(148,163,184,0.18)" stroke-width="1" stroke-dasharray="2,4"/>')
        label = f"{int(round(x_tick))}" if axis_mode == "cycles_to_transition" else f"{int(round(x_tick))}%"
        parts.append(f'<text x="{x_pos}" y="{PY + IH + 18}" text-anchor="middle" fill="rgba(226,232,240,0.82)" font-size="11">{label}</text>')

    parts.append(f'<line x1="{PX}" y1="{PY + IH}" x2="{PX + IW}" y2="{PY + IH}" stroke="rgba(226,232,240,0.5)" stroke-width="1.5"/>')
    parts.append(f'<line x1="{PX}" y1="{PY}" x2="{PX}" y2="{PY + IH}" stroke="rgba(226,232,240,0.5)" stroke-width="1.5"/>')

    parts.append(
        f'<text x="{PX + IW - 4}" y="{PY + IH + 36}" text-anchor="end" fill="rgba(226,232,240,0.98)" font-size="12" font-weight="700">'
        f'{"Cycles Until Structural Transition" if axis_mode == "cycles_to_transition" else "Lifecycle Progression (%)"}'
        '</text>'
    )
    parts.append(f'<text x="{PX - 10}" y="{PY - 12}" text-anchor="start" fill="rgba(226,232,240,0.96)" font-size="12" font-weight="700">Structural Signal Level</text>')

    # Divergence fill between stability and drift.
    divergence_d = []
    for idx, point in enumerate(chart_points):
        x_pos = sx(_f(point.get("x_value"), 0.0))
        y_drift = sy(_f(point.get("drift"), 0.0))
        if idx == 0:
            divergence_d.append(f"M{x_pos},{y_drift}")
        else:
            divergence_d.append(f"L{x_pos},{y_drift}")
    for point in reversed(chart_points):
        x_pos = sx(_f(point.get("x_value"), 0.0))
        y_stability = sy(_f(point.get("stability"), 0.0))
        divergence_d.append(f"L{x_pos},{y_stability}")
    divergence_d.append("Z")
    parts.append(
        f'<path d="{" ".join(divergence_d)}" fill="rgba(56,189,248,0.16)" stroke="rgba(56,189,248,0.22)" stroke-width="1"/>'
    )

    # Main lines.
    parts.append(f'<polyline points="{_series_points("stability")}" fill="none" stroke="url(#stabilityStroke)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<polyline points="{_series_points("drift")}" fill="none" stroke="url(#driftStroke)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>')

    # Drift slope trail with progressive intensity near instability.
    for idx in range(1, len(chart_points)):
        prev = chart_points[idx - 1]
        curr = chart_points[idx]
        x0 = sx(_f(prev.get("x_value"), 0.0))
        y0 = sy(_f(prev.get("drift_slope"), 0.0))
        x1 = sx(_f(curr.get("x_value"), 0.0))
        y1 = sy(_f(curr.get("drift_slope"), 0.0))
        recency = idx / max(len(chart_points) - 1, 1)
        slope_intensity = _cl(_f(curr.get("abs_slope"), 0.0) / max_abs_slope, 0.0, 1.0)
        opacity = 0.08 + 0.46 * recency + 0.34 * slope_intensity
        width = 1.0 + 2.2 * slope_intensity
        parts.append(
            f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="rgba(251,146,60,{opacity:.3f})" stroke-width="{width:.2f}" '
            f'stroke-linecap="round"/>'
        )

    # Progressive emphasis dots: older muted, newer bright.
    for idx, point in enumerate(chart_points):
        recency = idx / max(len(chart_points) - 1, 1)
        drift = _f(point.get("drift"), 0.0)
        instability = 1.0 - _f(point.get("stability"), 1.0)
        highlight = _cl((drift + instability) * 0.5, 0.0, 1.0)
        opacity = 0.14 + recency * 0.64
        radius = 1.8 + recency * 2.6 + highlight * 1.6
        parts.append(
            f'<circle cx="{sx(_f(point.get("x_value"), 0.0))}" cy="{sy(drift)}" r="{radius:.2f}" fill="rgba(6,182,212,{opacity:.3f})"/>'
        )

    if transition_x is not None:
        parts.append(
            f'<line x1="{transition_x}" y1="{PY}" x2="{transition_x}" y2="{PY + IH}" stroke="#F97316" stroke-width="3.5" '
            f'opacity="0.92" filter="url(#transitionGlow)"/>'
        )
        marker_point = next((p for p in chart_points if abs(_f(p.get("x_value"), 9999.0)) < 1e-6), chart_points[min(max(transition_frame or 0, 0), len(chart_points) - 1)])
        marker_y = sy(_f(marker_point.get("drift"), 0.0))
        parts.append(f'<circle cx="{transition_x}" cy="{marker_y}" r="11" fill="rgba(249,115,22,0.28)" stroke="rgba(251,191,36,0.85)" stroke-width="2.5" filter="url(#transitionGlow)"/>')
        parts.append(f'<circle cx="{transition_x}" cy="{marker_y}" r="4.2" fill="#FDBA74"/>')
        parts.append(
            f'<text x="{transition_x + 10}" y="{max(PY + 18, marker_y - 14)}" fill="#FDBA74" font-size="12" font-weight="800">Transition Point</text>'
        )
        parts.append(
            f'<text x="{transition_x + 10}" y="{max(PY + 34, marker_y + 4)}" fill="rgba(253,186,116,0.85)" font-size="11">Structural Break Detected</text>'
        )

    # Current frame anchor.
    parts.append(f'<line x1="{current_x}" y1="{PY}" x2="{current_x}" y2="{PY + IH}" stroke="#22D3EE" stroke-width="2.6" opacity="0.9" stroke-dasharray="5,3"/>')
    parts.append(f'<circle cx="{current_x}" cy="{current_y_drift}" r="7.8" fill="#22D3EE" stroke="#E2E8F0" stroke-width="2.6"/>')
    parts.append(f'<text x="{min(current_x + 12, W - 18)}" y="{max(current_y_drift - 10, PY + 16)}" fill="#E0F2FE" font-size="12" font-weight="800">Current Frame</text>')

    # Optional subtle projected path after current point.
    if point_count >= 4:
        tail = chart_points[-4:]
        if len(tail) >= 2:
            slope = _f(tail[-1].get("drift"), 0.0) - _f(tail[-2].get("drift"), 0.0)
            proj1_x = _f(chart_points[-1].get("x_value"), 0.0) - 2.0 if axis_mode == "cycles_to_transition" else min(100.0, _f(chart_points[-1].get("x_value"), 0.0) + 8.0)
            proj2_x = proj1_x - 2.0 if axis_mode == "cycles_to_transition" else min(100.0, proj1_x + 8.0)
            base_drift = _f(chart_points[-1].get("drift"), 0.0)
            proj1_y = _cl(base_drift + slope * 0.8, y_domain_min, y_domain_max)
            proj2_y = _cl(proj1_y + slope * 0.8, y_domain_min, y_domain_max)
            proj_pts = f"{current_x},{current_y_drift} {sx(proj1_x)},{sy(proj1_y)} {sx(proj2_x)},{sy(proj2_y)}"
            parts.append(
                f'<polyline points="{proj_pts}" fill="none" stroke="rgba(148,163,184,0.45)" stroke-width="1.8" stroke-dasharray="6,5"/>'
            )
            parts.append(
                f'<text x="{sx(proj1_x) + 8}" y="{sy(proj1_y) - 8}" fill="rgba(148,163,184,0.72)" font-size="10">Available future states</text>'
            )

    svg_body = "\n".join(parts)
    svg_html = (
        f'<div class="ner-timeline-scroll-region" data-current-frame="{int(current.get("index", 0))}">'
        f'<svg class="ner-system-canvas ner-system-canvas--timeline" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n{svg_body}\n</svg>'
        f'</div>'
    )

    legend_html = (
        '<div class="ner-chart-legend">'
        '<span><i style="background:#22C55E"></i>Relational Stability</span>'
        '<span><i style="background:#06B6D4"></i>Structural Drift</span>'
        '<span><i style="background:#FB923C"></i>Drift Acceleration</span>'
        '<span><i style="background:rgba(56,189,248,0.35)"></i>Divergence Envelope</span>'
        '</div>'
    )

    sequence = timeline_data.get("sequence") if isinstance(timeline_data.get("sequence"), list) else []
    stage_palette = {
        "admitted": "#22C55E",
        "suppressed": "#F97316",
        "transition": "#3B82F6",
        "baseline": "#6B7280",
        "void": "#A78BFA",
    }
    timeline_html = ""
    if sequence:
        items: list[str] = []
        for i, step in enumerate(sequence):
            if not isinstance(step, dict):
                continue
            label = str(step.get("label") or step.get("stage") or "?")
            stage = str(step.get("stage") or "baseline").lower()
            color = stage_palette.get(stage, "#4B5563")
            connector = (
                '<div style="flex:1;height:1px;background:rgba(255,255,255,0.07);margin:0 3px;align-self:center;"></div>'
                if i < len(sequence) - 1
                else ""
            )
            items.append(
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:3px;">'
                f'<div style="width:8px;height:8px;border-radius:50%;background:{color};box-shadow:0 0 8px {color}66;"></div>'
                f'<span style="font-size:9px;font-weight:700;letter-spacing:0.05em;color:{color};text-transform:uppercase;">'
                f'{escape(label)}</span></div>{connector}'
            )
        timeline_html = (
            f'<div class="ner-timeline-strip">'
            f'<span class="ner-timeline-label">Phase replay</span>'
            f'{"".join(items)}</div>'
        )

    header_html = (
        '<div class="ner-panel-head">'
        '<div style="display:flex;flex-direction:column;gap:2px;">'
        '<span class="ner-eyebrow">Replay telemetry</span>'
        f'<span style="font-size:12px;color:#7c8ba8;">Structural evolution across {point_count} frames Â· divergence and breakpoints emphasized</span>'
        '</div>'
        '</div>'
    )

    current_drift = _f(current.get("drift"), 0.0)
    current_stability = _f(current.get("stability"), 1.0)
    phase_label = escape(str(current.get("phase") or "UNKNOWN").upper())
    context_row = (
        '<div class="ner-system-context-grid">'
        f'<div><span class="ner-context-label">Current Drift</span><span class="ner-context-value">{current_drift:.3f}</span></div>'
        f'<div><span class="ner-context-label">Current Stability</span><span class="ner-context-value">{current_stability:.3f}</span></div>'
        f'<div><span class="ner-context-label">Divergence</span><span class="ner-context-value">{abs(current_drift - current_stability):.3f}</span></div>'
        f'<div><span class="ner-context-label">Lifecycle Position</span><span class="ner-context-value">{int(current.get("index", 0))} / {max(point_count - 1, 0)}</span></div>'
        '</div>'
    )

    axis_context = (
        f'<div class="ner-axis-context">'
        f'<span>Axis Mode: {"Cycles Until Structural Transition" if axis_mode == "cycles_to_transition" else "Lifecycle Progression (%)"}</span>'
        f'<span>{"Transition anchor at 0" if axis_mode == "cycles_to_transition" else "No transition frame detected; using progression view"}</span>'
        f'<span>Tooltip semantics: Drift = structural pressure, Stability = relational integrity, Acceleration = change velocity</span>'
        f'</div>'
    )

    return (
        f'<div class="ner-panel ner-system-panel">'
        f'{header_html}{context_row}{axis_context}{legend_html}{svg_html}{timeline_html}</div>'
    )


def _render_reasoning_html(reasoning_panel: dict[str, Any]) -> str:
    """Render reasoning panel with improved clarity and readability.

    Collapses by default. Shows 3 clear lines when expanded: Observed, Assessment, Implication.
    Uses larger fonts and better spacing for better readability.
    """
    panel = reasoning_panel if isinstance(reasoning_panel, dict) else {}
    facts = panel.get("observed_facts")
    if not isinstance(facts, list):
        facts = []
    inference = panel.get("inference") if isinstance(panel.get("inference"), dict) else {}
    sections = inference.get("sections") if isinstance(inference.get("sections"), dict) else {}

    raw_grounded = sections.get("Inference") or inference.get("final_response") or inference.get("answer")
    if isinstance(raw_grounded, list):
        grounded_text = " ".join(str(i) for i in raw_grounded if i is not None).strip()
    else:
        grounded_text = str(raw_grounded or "").strip()

    insufficient = sections.get("Insufficient Evidence") or []
    if isinstance(insufficient, list) and insufficient:
        insufficient_text = " ".join(str(i) for i in insufficient if i is not None).strip()
    else:
        insufficient_text = ""

    escape(str(panel.get("operational_implication") or "No implication available."))

    observed = escape(str(facts[0])) if facts else "No observed signal."
    assessment_source = grounded_text or insufficient_text or "No assessment available."
    implication_source = escape(str(panel.get("operational_implication") or "No implication available."))

    # Full lines, no truncation - ensure they're readable
    observed_line = observed
    assessment_line = escape(assessment_source)
    implication_line = implication_source

    core_lines = (
        f'<div class="ner-core-lines">'
        f'<div class="ner-core-line">'
        f'<span>Observed Signal</span>'
        f'<strong>{observed_line}</strong>'
        f'</div>'
        f'<div class="ner-core-line">'
        f'<span>Assessment</span>'
        f'<strong>{assessment_line}</strong>'
        f'</div>'
        f'<div class="ner-core-line">'
        f'<span>Operational Implication</span>'
        f'<strong>{implication_line}</strong>'
        f'</div>'
        f'</div>'
    )

    details_items = "".join(f"<li style='font-size:13px;line-height:1.6;color:#cbd5e1;'>{escape(str(f))}</li>" for f in facts[1:] if f)
    details_html = (
        f'<details class="ner-more-detail">'
        f'<summary>View Full Analysis</summary>'
        f'<div class="ner-reason-copy">{escape(grounded_text or insufficient_text or "")}</div>'
        f'<ul>{details_items}</ul>'
        f"</details>"
    )

    # Collapse reasoning panel by default
    return (
        f'<details class="ner-collapsible-panel">'
        f'<summary style="cursor:pointer;font-weight:600;color:#e2e8f0;font-size:13px;padding:12px;margin:-12px;display:flex;align-items:center;gap:8px;">'
        f'<span style="display:inline-block;width:12px;height:12px;border:1.5px solid #94a3b8;border-radius:2px;"></span>'
        f'Show Reasoning'
        f'</summary>'
        f'<div style="padding:12px 0;border-top:1px solid rgba(255,255,255,0.08);">'
        f'<div class="ner-panel">'
        f'<div class="ner-eyebrow">Analytical Reasoning</div>'
        f'{core_lines}{details_html}'
        f'</div>'
        f'</div>'
        f'</details>'
    )


def _render_record_html(record_panel: dict[str, Any]) -> str:
    """Render evidence/record panel with improved spacing and scanability. Collapses by default."""
    panel = record_panel if isinstance(record_panel, dict) else {}
    entries = panel.get("entries")
    if not isinstance(entries, list):
        entries = []

    decision_styles = {
        "ADMIT": {
            "bg": "rgba(34,197,94,0.15)",
            "border": "rgba(34,197,94,0.3)",
            "badge_bg": "#22C55E",
            "badge_text": "#FFFFFF",
            "badge_border": "#22C55E",
            "ts_color": "#22C55E",
        },
        "SUPPRESS": {
            "bg": "rgba(249,115,22,0.15)",
            "border": "rgba(249,115,22,0.3)",
            "badge_bg": "#F97316",
            "badge_text": "#FFFFFF",
            "badge_border": "#F97316",
            "ts_color": "#F97316",
        },
        "VOID": {
            "bg": "rgba(167,139,250,0.15)",
            "border": "rgba(167,139,250,0.3)",
            "badge_bg": "#A78BFA",
            "badge_text": "#FFFFFF",
            "badge_border": "#A78BFA",
            "ts_color": "#A78BFA",
        },
    }
    default_style = {
        "bg": "rgba(107,114,128,0.15)",
        "border": "rgba(107,114,128,0.3)",
        "badge_bg": "#6B7280",
        "badge_text": "#FFFFFF",
        "badge_border": "#6B7280",
        "ts_color": "#9CA3AF",
    }

    transition_colors = {
        "REORGANIZATION": "#EF4444",
        "TRANSITION": "#F97316",
        "STABLE": "#22C55E",
        "RECOVERY": "#10B981",
    }

    def _entry_card(entry: dict[str, Any]) -> str:
        raw_decision = str(entry.get("gate_decision") or "SUPPRESS").upper()
        decision_text = {"ADMIT": "CONFIRMED", "SUPPRESS": "OBSERVED", "VOID": "VOIDED"}.get(raw_decision, "OBSERVED")
        st = decision_styles.get(raw_decision, default_style)
        ts = escape(str(entry.get("timestamp") or "n/a"))
        summary = escape(str(entry.get("summary") or "No summary."))
        raw_transition = str(entry.get("transition_type") or "STABLE").upper()
        transition_color = transition_colors.get(raw_transition, "#4B5563")

        return (
            f'<div class="ner-record-card">'
            f'<div>'
            f'<span style="font-variant-numeric:tabular-nums;">{ts}</span>'
            f'<span style="background-color:{st["badge_bg"]};color:{st["badge_text"]};border:1px solid {st["badge_border"]};">{decision_text}</span>'
            f'<span style="color:{transition_color};border:1px solid {transition_color}40;">{escape(raw_transition)}</span>'
            f'</div>'
            f'<div>{summary}</div>'
            f'</div>'
        )

    if entries:
        cards_html = "".join(_entry_card(e) for e in entries if isinstance(e, dict))
    else:
        cards_html = (
            '<div style="margin-top:12px;padding:12px 14px;font-size:13px;color:var(--text-tertiary);'
            'background:rgba(255,255,255,0.03);border-radius:4px;border-left:2px solid var(--text-muted);">'
            'No evidence entries recorded yet.</div>'
        )

    # Collapse evidence panel by default
    return (
        f'<details class="ner-collapsible-panel">'
        f'<summary style="cursor:pointer;font-weight:600;color:#e2e8f0;font-size:13px;padding:12px;margin:-12px;display:flex;align-items:center;gap:8px;">'
        f'<span style="display:inline-block;width:12px;height:12px;border:1.5px solid #94a3b8;border-radius:2px;"></span>'
        f'Show Evidence'
        f'</summary>'
        f'<div style="padding:12px 0;border-top:1px solid rgba(255,255,255,0.08);">'
        f'<div class="ner-panel">'
        f'<div class="ner-eyebrow">Evidence Record</div>'
        f'<div>{cards_html}</div>'
        f'</div>'
        f'</div>'
        f'</details>'
    )


def _load_unified_shell(
    system_state: SystemState,
    records: list[dict[str, Any]] | None = None,
    gate_decision: dict[str, Any] | None = None,
) -> tuple[str, str, str, str, str]:
    """Load the unified app shell with all integrated components.

    Args:
        system_state: Current SystemState
        records: Historical records
        gate_decision: Gate decision

    Returns:
        Tuple of (top_bar, system_field, left_panel, right_panel, bottom_timeline)
    """
    latest = records[-1] if records else {}
    timestamp = str(latest.get("timestamp", "")).replace("Z", "") if records else None

    facility_coherence = getattr(system_state, "coherence", 0.75) if system_state else 0.75
    rooms = build_facility_rooms_data(system_state, records)
    subsystems = build_subsystems_data(system_state, records)
    states_timeline = build_timeline_states(records)
    time_to_consequence = _compute_time_to_consequence(records)
    no_action_projection = _compute_no_action_projection(records)
    insights = build_intelligence_insights(system_state, records, gate_decision, time_to_consequence, no_action_projection)
    critical_alerts = get_critical_alerts(system_state, gate_decision)

    rooms_needing_attention = sum(1 for r in rooms if r.get("state") in ("watch", "degraded", "critical"))

    shell = build_unified_app_shell(
        state=system_state,
        rooms=rooms,
        subsystems=subsystems,
        states_timeline=states_timeline,
        facility_coherence=facility_coherence,
        rooms_needing_attention=rooms_needing_attention,
        timestamp=timestamp,
        feed_latency_ms=None,
        current_state_insight=insights.get("current_state", ""),
        onset_insight=insights.get("onset", ""),
        coherence_insight=insights.get("coherence", ""),
        primary_driver_insight=insights.get("primary_driver", ""),
        operator_focus_insight=insights.get("operator_focus", ""),
        path_outlook_insight=insights.get("path_outlook", ""),
        critical_alerts=critical_alerts if critical_alerts else None,
        records=records,
        no_action_projection=no_action_projection,
        no_action_consequence_insight=insights.get("no_action_consequence", ""),
        recoverability_insight=insights.get("recoverability", ""),
    )

    return (
        shell["top_bar"],
        shell["system_field"],
        shell["left_panel"],
        shell["right_panel"],
        shell["bottom_timeline"],
    )



def _render_verdict_surface_html(gate_card: dict[str, Any], system_zone: dict[str, Any]) -> str:
    """Merge verdict card and system geometry into one visually connected surface."""
    gate_html = _render_gate_decision_html(gate_card)
    system_html = _render_system_geometry_html(system_zone)
    return f'<div class="ner-verdict-surface">{gate_html}{system_html}</div>'


def _compute_replay_events(rows: list[dict[str, Any]], baseline_frames: int = 30) -> dict[str, Any]:
    """Compute baseline completion, drift detection, and alert trigger frames from replay logic."""
    if not rows:
        return {"baseline_complete": None, "drift_detected": None, "alert_triggered": None}

    baseline_idx = min(max(baseline_frames - 1, 0), len(rows) - 1)
    baseline_slice = rows[: baseline_idx + 1]
    drift_values = [float(r.get("structural_drift_score") or 0.0) for r in baseline_slice]
    mean = sum(drift_values) / max(len(drift_values), 1)
    variance = sum((v - mean) ** 2 for v in drift_values) / max(len(drift_values), 1)
    std = variance**0.5
    drift_threshold = mean + (2.0 * std)

    drift_detected: int | None = None
    for i, row in enumerate(rows):
        transition = str(row.get("transition_type") or "").upper()
        drift = float(row.get("structural_drift_score") or 0.0)
        if i >= baseline_idx and (transition in {"TRANSITION", "REORGANIZATION"} or drift >= drift_threshold):
            drift_detected = i
            break

    alert_triggered = next((i for i, row in enumerate(rows) if bool(row.get("event_admitted"))), None)
    return {
        "baseline_complete": baseline_idx,
        "drift_detected": drift_detected,
        "alert_triggered": alert_triggered,
        "drift_threshold": drift_threshold,
    }


def _build_frame_states(rows: list[dict[str, Any]], baseline_frames: int = 30) -> list[dict[str, Any]]:
    """Create a single synchronized frame-state contract for each replay timestep."""
    if not rows:
        return []

    events = _compute_replay_events(rows, baseline_frames=baseline_frames)
    baseline_complete_idx = events.get("baseline_complete")
    drift_detected_idx = events.get("drift_detected")
    alert_triggered_idx = events.get("alert_triggered")

    frame_states: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        structural_drift = max(0.0, min(1.0, float(row.get("structural_drift_score") or 0.0)))
        relational_stability = max(0.0, min(1.0, float(row.get("relational_stability_score") or 0.0)))
        relational_instability = max(0.0, min(1.0, 1.0 - relational_stability))
        coherence = max(0.0, min(1.0, float(row.get("coherence_score") or (1.0 - (structural_drift * 0.72)))))
        confidence = max(0.0, min(1.0, float(row.get("confidence_score") or 0.0)))

        if baseline_complete_idx is not None and i <= baseline_complete_idx:
            state = "baseline"
        elif alert_triggered_idx is not None and i >= alert_triggered_idx:
            state = "alert"
        elif drift_detected_idx is not None and i >= drift_detected_idx:
            state = "drifting"
        else:
            state = "stable"

        previous_drift = structural_drift if i == 0 else frame_states[i - 1]["structural_drift"]
        drift_delta = structural_drift - previous_drift
        trend = "up" if drift_delta > 0.01 else "down" if drift_delta < -0.01 else "flat"

        frame_states.append(
            {
                "frame": i + 1,
                "timestamp": row.get("timestamp"),
                "structural_drift": structural_drift,
                "relational_instability": relational_instability,
                "coherence": coherence,
                "stability": relational_stability,
                "confidence": confidence,
                "state": state,
                "trend": trend,
                "baseline_complete": bool(baseline_complete_idx is not None and i >= baseline_complete_idx),
                "drift_detected": bool(drift_detected_idx is not None and i >= drift_detected_idx),
                "alert_triggered": bool(alert_triggered_idx is not None and i >= alert_triggered_idx),
            }
        )
    return frame_states


def _explanation_for_state(state: str) -> str:
    mapping = {
        "baseline": "System learning baseline behavior",
        "stable": "System remains within learned structure",
        "drifting": "Deviation increasing relative to baseline",
        "alert": "System has exceeded acceptable structural bounds",
    }
    return mapping.get(state, mapping["stable"])


def _build_clean_ticks(y_min: float, y_max: float, max_ticks: int = 6) -> list[float]:
    """Build rounded y-axis ticks for tight domains."""
    if y_max <= y_min:
        return [round(y_min, 3), round(y_max + 1.0, 3)]
    steps = [1, 2, 2.5, 5, 10]
    span = y_max - y_min
    target = max(span / max(max_ticks - 1, 1), 1e-6)
    magnitude = 10 ** math.floor(math.log10(target))
    raw = target / magnitude
    chosen = next((s for s in steps if s >= raw), steps[-1]) * magnitude
    start = math.floor(y_min / chosen) * chosen
    end = math.ceil(y_max / chosen) * chosen
    tick_count = int(round((end - start) / chosen)) + 1
    while tick_count > max_ticks:
        chosen *= 2
        start = math.floor(y_min / chosen) * chosen
        end = math.ceil(y_max / chosen) * chosen
        tick_count = int(round((end - start) / chosen)) + 1
    return [round(start + i * chosen, 6) for i in range(tick_count)]


def _render_replay_monitor(
    rows: list[dict[str, Any]],
    frame_states: list[dict[str, Any]],
    frame_index: int,
    *,
    auto_follow: bool = True,
    normalized_scale: bool = False,
) -> tuple[str, str, str]:
    """Render top status bar, replay chart panel, and right-side insight panel."""
    if not rows:
        empty = '<div class="ner-panel">No replay rows available.</div>'
        return empty, empty, empty

    idx = max(1, min(len(rows), int(frame_index)))
    current = rows[idx - 1]
    current_frame_state = frame_states[idx - 1]
    events = _compute_replay_events(rows, baseline_frames=30)
    baseline_complete = events.get("baseline_complete")
    drift_detected = events.get("drift_detected")
    alert_triggered = events.get("alert_triggered")

    drift_series = [float(r.get("structural_drift_score") or 0.0) for r in rows]
    instability_series = [max(0.0, 1.0 - float(r.get("relational_stability_score") or 0.0)) for r in rows]
    active_drift = float(current_frame_state["structural_drift"])
    active_instability = float(current_frame_state["relational_instability"])
    confidence = float(current_frame_state["confidence"])
    state_label = str(current_frame_state["state"]).title()
    trend_label = {"up": "Up", "down": "Down", "flat": "Flat"}.get(str(current_frame_state["trend"]), "Flat")
    phase = str(current.get("transition_type") or current.get("system_phase") or "stable").replace("_", " ").title()
    explanation = _explanation_for_state(str(current_frame_state["state"]))

    # Moving viewport
    window = 100
    if auto_follow and len(rows) > window:
        half = window // 2
        start = max(0, min(len(rows) - window, (idx - 1) - half))
        end = min(len(rows) - 1, start + window - 1)
    else:
        start, end = 0, len(rows) - 1

    vis_drift = drift_series[start : end + 1]
    vis_instability = instability_series[start : end + 1]
    baseline_end = baseline_complete if baseline_complete is not None else 0
    baseline_slice_end = min(baseline_end + 1, len(rows))
    baseline_drift = drift_series[:baseline_slice_end] or [0.0]
    baseline_instability = instability_series[:baseline_slice_end] or [0.0]
    baseline_all = baseline_drift + baseline_instability
    baseline_low = min(baseline_all)
    baseline_high = max(baseline_all)
    baseline_mean = sum(baseline_all) / max(len(baseline_all), 1)

    all_vis = vis_drift + vis_instability
    if normalized_scale:
        y_min, y_max = 0.0, 100.0
        y_ticks = [0, 20, 40, 60, 80, 100]
    else:
        data_min = min(all_vis + [baseline_low]) if all_vis else baseline_low
        data_max = max(all_vis + [baseline_high]) if all_vis else baseline_high
        span = max(data_max - data_min, 0.05)
        pad = max(span * 0.2, 0.02)
        y_min, y_max = data_min - pad, data_max + pad
        y_ticks = _build_clean_ticks(y_min, y_max, max_ticks=6)
        y_min, y_max = y_ticks[0], y_ticks[-1]

    W, H = 980, 430
    PX, PY = 70, 46
    IW, IH = W - 2 * PX, H - 2 * PY

    def sx(i: int) -> float:
        denom = max(end - start, 1)
        return round(PX + ((i - start) / denom) * IW, 2)

    def sy(v: float) -> float:
        val = v * 100.0 if normalized_scale else v
        return round(PY + IH - ((val - y_min) / max(y_max - y_min, 1e-9)) * IH, 2)

    parts = ['<defs><filter id="activeGlow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>']

    # Phase shading
    if start <= baseline_end:
        bx0, bx1 = sx(start), sx(min(end, baseline_end))
        parts.append(f'<rect x="{bx0}" y="{PY}" width="{max(bx1-bx0,1)}" height="{IH}" fill="rgba(59,130,246,0.09)"/>')
    if drift_detected is not None and drift_detected <= end:
        dx0 = sx(max(start, drift_detected))
        dx1 = sx(end)
        parts.append(f'<rect x="{dx0}" y="{PY}" width="{max(dx1-dx0,1)}" height="{IH}" fill="rgba(249,115,22,0.06)"/>')
    if alert_triggered is not None and alert_triggered <= end:
        ax0 = sx(max(start, alert_triggered))
        ax1 = sx(end)
        parts.append(f'<rect x="{ax0}" y="{PY}" width="{max(ax1-ax0,1)}" height="{IH}" fill="rgba(239,68,68,0.06)"/>')

    baseline_band_lo = baseline_low * 100.0 if normalized_scale else baseline_low
    baseline_band_hi = baseline_high * 100.0 if normalized_scale else baseline_high
    baseline_mid = baseline_mean * 100.0 if normalized_scale else baseline_mean
    band_top = sy(baseline_band_hi)
    band_bottom = sy(baseline_band_lo)
    parts.append(
        f'<rect x="{PX}" y="{min(band_top, band_bottom)}" width="{IW}" height="{max(abs(band_bottom-band_top),1)}" '
        'fill="rgba(148,163,184,0.10)"/>'
    )
    parts.append(f'<line x1="{PX}" y1="{sy(baseline_mid)}" x2="{PX+IW}" y2="{sy(baseline_mid)}" stroke="rgba(148,163,184,0.5)" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="{PX+8}" y="{max(PY+14, sy(baseline_mid)-6)}" fill="rgba(203,213,225,0.9)" font-size="11">Baseline range</text>')

    for yv in y_ticks:
        y = sy(yv)
        parts.append(f'<line x1="{PX}" y1="{y}" x2="{PX+IW}" y2="{y}" stroke="rgba(148,163,184,0.18)" stroke-width="1"/>')
        label = f"{yv:.0f}" if normalized_scale else (f"{yv:.2f}" if abs(yv) < 1 else f"{yv:.1f}")
        parts.append(f'<text x="{PX-10}" y="{y+4}" text-anchor="end" fill="rgba(203,213,225,0.9)" font-size="11">{label}</text>')

    for t in range(start, end + 1, max((end - start) // 6, 1)):
        x = sx(t)
        parts.append(f'<line x1="{x}" y1="{PY}" x2="{x}" y2="{PY+IH}" stroke="rgba(148,163,184,0.14)" stroke-dasharray="3,4"/>')
        parts.append(f'<text x="{x}" y="{PY+IH+18}" text-anchor="middle" fill="rgba(203,213,225,0.9)" font-size="11">{t+1}</text>')

    drift_pts = " ".join(f"{sx(i)},{sy(drift_series[i])}" for i in range(start, end + 1))
    inst_pts = " ".join(f"{sx(i)},{sy(instability_series[i])}" for i in range(start, end + 1))
    parts.append(f'<polyline points="{inst_pts}" fill="none" stroke="#22C55E" stroke-width="2.4"/>')
    parts.append(f'<polyline points="{drift_pts}" fill="none" stroke="#06B6D4" stroke-width="3"/>')

    def marker(frame: int | None, label: str, color: str) -> None:
        if frame is None or frame < start or frame > end:
            return
        x = sx(frame)
        parts.append(f'<line x1="{x}" y1="{PY}" x2="{x}" y2="{PY+IH}" stroke="{color}" stroke-width="2" stroke-dasharray="5,4"/>')
        parts.append(f'<text x="{x+6}" y="{PY+16}" fill="{color}" font-size="11" font-weight="700">{escape(label)}</text>')

    marker(baseline_complete, "Baseline Complete", "#60A5FA")
    marker(drift_detected, "Drift Detected", "#FB923C")
    marker(alert_triggered, "Alert Triggered", "#F87171")

    active_idx = idx - 1
    active_x = sx(active_idx)
    parts.append(f'<line x1="{active_x}" y1="{PY}" x2="{active_x}" y2="{PY+IH}" stroke="#E2E8F0" stroke-width="2.4" filter="url(#activeGlow)"/>')
    parts.append(f'<circle cx="{active_x}" cy="{sy(active_drift)}" r="6.5" fill="#06B6D4" stroke="#E2E8F0" stroke-width="2"/>')
    parts.append(f'<circle cx="{active_x}" cy="{sy(active_instability)}" r="6.5" fill="#22C55E" stroke="#E2E8F0" stroke-width="2"/>')

    summary = (
        f"System learned baseline over first 30 frames. Drift first detected at frame "
        f"{(drift_detected + 1) if drift_detected is not None else 'N/A'}. "
        f"Alert triggered at frame {(alert_triggered + 1) if alert_triggered is not None else 'N/A'}."
    )
    if state_label == "Alert":
        system_insight = "System Insight: Deviation is increasing and now beyond baseline safety bounds."
    elif state_label == "Drifting":
        system_insight = "System Insight: Drift is increasing but remains below confirmed alert threshold."
    elif state_label == "Baseline":
        system_insight = "System Insight: System remains within baseline structure while calibration completes."
    else:
        system_insight = "System Insight: System remains within baseline structure with stable drift behavior."

    chart_html = (
        '<div class="ner-panel ner-replay-chart-panel">'
        f'<div class="ner-replay-insight">{escape(system_insight)}</div>'
        f'<div class="ner-replay-summary">{escape(summary)}</div>'
        '<svg class="ner-system-canvas" viewBox="0 0 980 430" width="980" height="430">'
        + "".join(parts)
        + "</svg>"
        '<div class="ner-chart-legend"><span><i style="background:#06B6D4"></i>Structural Drift</span>'
        '<span><i style="background:#22C55E"></i>Relational Instability</span>'
        f'<span class="ner-live-value">Structural Drift: <strong>{active_drift*100.0:.1f}%</strong></span>'
        f'<span class="ner-live-value">Relational Instability: <strong>{active_instability*100.0:.1f}%</strong></span>'
        '</div></div>'
    )

    insight_html = (
        '<div class="ner-panel ner-insight-panel">'
        '<div class="ner-eyebrow">Replay Insight</div>'
        f'<div class="ner-insight-state">{escape(state_label)}</div>'
        f'<div class="ner-insight-grid"><span>Structural Drift</span><strong>{active_drift:.3f}</strong>'
        f'<span>Relational Instability</span><strong>{active_instability:.3f}</strong>'
        f'<span>Timestamp</span><strong>{escape(str(current_frame_state.get("timestamp") or "â€”"))}</strong>'
        f'<span>Confidence</span><strong>{confidence:.2f}</strong>'
        f'<span>Trend</span><strong>{escape(trend_label)}</strong>'
        f'<span>Phase</span><strong>{escape(phase)}</strong></div>'
        f'<p class="ner-insight-note">{escape(explanation)}</p></div>'
    )

    status_html = (
        '<div class="ner-status-bar">'
        '<div class="ner-status-left"><span class="ner-wordmark">NERAIUM</span><span class="ner-status-sub">Live System Replay</span></div>'
        f'<div class="ner-status-center">{escape(str(current.get("asset_id") or "Unknown Asset"))} Â· Frame {idx} / {len(rows)}</div>'
        f'<div class="ner-status-right"><span class="ner-pill ner-pill-state">{escape(state_label)}</span>'
        f'<span class="ner-pill">Confidence {confidence:.2f}</span></div></div>'
    )
    return status_html, chart_html, insight_html


def create_gradio_app():
    try:
        import gradio as gr
    except ImportError:
        raise RuntimeError("Gradio is not installed")

    # Use FD004 real prognostics demo by default
    demo_rows = load_fd004_demo_records(limit=250, unit_id="unit_001")
    if not demo_rows:
        # Fallback to synthetic greenhouse demo if FD004 data unavailable
        demo_rows = load_builtin_demo_rows(use_synthetic=True)
    total_steps = max(len(demo_rows), 1)
    frame_states = _build_frame_states(demo_rows, baseline_frames=30)
    playback_state = {"playing": False, "current_mode": "fd004"}

    # Replay stabilization for verdict and reasoning
    verdict_stabilizer = VerdictStabilizer(hysteresis_threshold=0.08)
    reasoning_tracker = ReasoningStateTracker(change_threshold=0.06)
    pace_controller = ReplayPaceController()
    frame_controller = SmoothUIFrameController(target_ui_hz=5.5)  # ~180ms per UI update

    def _rows_until(frame_index: int) -> list[dict[str, Any]]:
        idx = max(1, min(total_steps, int(frame_index)))
        return demo_rows[:idx]

    def has_significant_state_change(frame_index: int, previous_frame_index: int) -> bool:
        """Check if there's a significant state change between frames.

        Ensures we capture important transitions even if timing doesn't align.
        Important changes: verdict flip, health status change, major metric shifts.
        """
        if previous_frame_index is None or frame_index <= previous_frame_index:
            return True

        current_rows = _rows_until(frame_index)
        previous_rows = _rows_until(previous_frame_index)

        if not current_rows or not previous_rows:
            return True

        curr = current_rows[-1] if current_rows else {}
        prev = previous_rows[-1] if previous_rows else {}

        # Check verdict decision change
        if curr.get("event_admitted") != prev.get("event_admitted"):
            return True

        # Check system health change
        if curr.get("system_health") != prev.get("system_health"):
            return True

        # Check transition type change
        if curr.get("transition_type") != prev.get("transition_type"):
            return True

        # Check for large metric shifts
        drift_delta = abs(_safe_float(curr.get("structural_drift_score")) - _safe_float(prev.get("structural_drift_score")))
        if drift_delta > 0.15:
            return True

        stability_delta = abs(_safe_float(curr.get("relational_stability_score")) - _safe_float(prev.get("relational_stability_score")))
        if stability_delta > 0.15:
            return True

        return False

    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Safely convert value to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def load_operations_surface(frame_index: int, speed_multiplier: float = 0.6, auto_follow: bool = True, normalized_scale: bool = False, apply_stability: bool = False):
        active_rows = _rows_until(frame_index)
        active_idx = max(1, min(total_steps, int(frame_index)))
        active_frame_state = frame_states[active_idx - 1] if frame_states else {}
        previous_frame_state = frame_states[active_idx - 2] if active_idx > 1 and frame_states else None
        app_state = create_app_state(active_rows)
        system_state = build_system_state(active_rows, config=UIConfig())
        latest = active_rows[-1] if active_rows else {}
        previous = active_rows[-2] if len(active_rows) > 1 else None

        gate_decision = app_state.get("gate_decision") if isinstance(app_state.get("gate_decision"), dict) else {}
        if not gate_decision:
            gate_decision = evaluate_gate(latest, previous, system_state)

        # Apply verdict stability during replay to prevent flipping
        if apply_stability and isinstance(gate_decision, dict):
            drift_intensity = system_state.drift_intensity if system_state else 0.0
            gate_decision = verdict_stabilizer.apply_stability(
                gate_decision,
                signal_strength=drift_intensity,
            )

        reasoning_context = app_state.get("reasoning_context") if isinstance(app_state.get("reasoning_context"), dict) else {}
        if not reasoning_context:
            reasoning_context = build_reasoning_context(system_state, active_rows, gate_decision=gate_decision)

        surface = build_operations_view(
            system_state,
            records=active_rows,
            reasoning_context=reasoning_context,
            gate_decision=gate_decision,
            frame_state=active_frame_state,
            previous_frame_state=previous_frame_state,
            current_frame=frame_index,
            total_frames=total_steps,
        )
        gate_content = surface["zones"]["gate"]["content"]
        gate_card = gate_content if isinstance(gate_content, dict) else {}
        # Inject system state confidence as single source of truth
        gate_card["system_confidence_score"] = system_state.confidence
        status_html, chart_html, insight_html = _render_replay_monitor(
            demo_rows,
            frame_states,
            frame_index,
            auto_follow=auto_follow,
            normalized_scale=normalized_scale,
        )
        reasoning_html = _render_reasoning_html(surface["zones"]["reasoning"]["content"])
        record_html = _render_record_html(surface["zones"]["record"]["content"])
        tetra_plot, tetra_text = build_tetrahedral_plot_and_text(latest, active_rows)

        top_bar, system_field, left_panel, right_panel, bottom_timeline = _load_unified_shell(
            system_state, active_rows, gate_decision
        )

        return (
            status_html,
            chart_html,
            insight_html,
            reasoning_html,
            record_html,
            tetra_plot,
            tetra_text,
            top_bar,
            system_field,
            left_panel,
            right_panel,
            bottom_timeline,
        )

    def load_unified_shell_surface(frame_index: int):
        """Load only the unified shell components for the frame."""
        active_rows = _rows_until(frame_index)
        system_state = build_system_state(active_rows, config=UIConfig())
        latest = active_rows[-1] if active_rows else {}
        previous = active_rows[-2] if len(active_rows) > 1 else None

        gate_decision = evaluate_gate(latest, previous, system_state)

        top_bar, system_field, left_panel, right_panel, bottom_timeline = _load_unified_shell(
            system_state, active_rows, gate_decision
        )

        return top_bar, system_field, left_panel, right_panel, bottom_timeline

    def pause_playback() -> None:
        playback_state["playing"] = False

    def reset_playback() -> tuple[int, str, str, str, str, str, Any, str]:
        pause_playback()
        # Reset stabilizers when resetting playback
        verdict_stabilizer.reset()
        reasoning_tracker.reset()
        results = load_operations_surface(1, apply_stability=False)
        return 1, results[0], results[1], results[2], results[3], results[4], results[5], results[6]

    def autoplay(start_frame: int, speed_multiplier: float):
        """Smooth playback with frame skipping for polished UI feel.

        Backend processes all frames at full speed, but UI only redraws
        at 5-6 Hz to avoid the "frame loading" slideshow effect.

        Also renders frames with significant state changes to ensure important
        transitions (verdict flips, health status changes) are captured.
        """
        playback_state["playing"] = True
        pace_controller.speed_multiplier = float(speed_multiplier or 1.0)
        frame_controller.reset()

        frame = max(1, int(start_frame))
        # Start each autoplay run with a fresh stabilizer state so seeks/scrubs
        # do not leak prior hysteresis into the new playback segment.
        verdict_stabilizer.reset()

        # Track previously yielded frame to avoid duplicate renders and for change detection
        last_yielded_frame = None
        last_rendered_frame = None
        elapsed_time = 0.0

        while frame <= total_steps and playback_state["playing"]:
            # Calculate adaptive delay based on phase
            step_delay = pace_controller.get_step_delay(frame - 1, demo_rows)
            elapsed_time += step_delay

            # Render frame if:
            # 1. Enough time has passed (smooth UI cadence), OR
            # 2. Significant state change detected (important transitions), OR
            # 3. Final frame (always show ending)
            should_render_by_time = frame_controller.should_render_frame(elapsed_time)
            should_render_by_change = has_significant_state_change(frame, last_rendered_frame)
            should_render_final = frame == total_steps

            if should_render_by_time or should_render_by_change or should_render_final:
                # Only yield if this is a new frame (not a duplicate)
                if last_yielded_frame != frame:
                    yield (frame, *load_operations_surface(frame, speed_multiplier, True, False, apply_stability=True))
                    last_yielded_frame = frame
                    last_rendered_frame = frame

            frame += 1

            # Sleep with calculated adaptive delay to maintain backend frame rate
            time.sleep(step_delay)

        playback_state["playing"] = False

    default_step = min(30, total_steps)
    results = load_operations_surface(default_step, apply_stability=False)
    initial_status = results[0]
    initial_chart = results[1]
    initial_insight = results[2]
    initial_reasoning = results[3]
    initial_record = results[4]
    initial_tetra_plot = results[5]
    initial_tetra_text = results[6]
    initial_top_bar = results[7] if len(results) > 7 else ""
    initial_system_field = results[8] if len(results) > 8 else ""
    initial_left_panel = results[9] if len(results) > 9 else ""
    initial_right_panel = results[10] if len(results) > 10 else ""
    initial_bottom_timeline = results[11] if len(results) > 11 else ""

    css_path = Path(__file__).parent / "themes" / "neraium_dark.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    with gr.Blocks(css=css, theme=gr.themes.Base(), elem_classes=["ner-app"]) as app:
        with gr.Group(elem_classes=["ner-unified-app-shell"]):
            top_bar = gr.HTML(value=initial_top_bar, elem_classes=["ner-facility-command-strip"])

            with gr.Row(elem_classes=["ner-main-canvas"]):
                left_panel = gr.HTML(value=initial_left_panel, elem_classes=["ner-side-panel"])
                with gr.Column(elem_classes=["ner-system-field-container"]):
                    system_field = gr.HTML(value=initial_system_field, elem_classes=["ner-system-field"])
                right_panel = gr.HTML(value=initial_right_panel, elem_classes=["ner-side-panel"])

            bottom_timeline = gr.HTML(value=initial_bottom_timeline, elem_classes=["ner-state-timeline-container"])

        with gr.Group():
            status = gr.HTML(value=initial_status)
        with gr.Row(elem_classes=["ner-main-content-row"]):
            chart = gr.HTML(value=initial_chart, scale=3)
            insight = gr.HTML(value=initial_insight, scale=1)

        with gr.Row(elem_classes=["ner-controls-row"]):
            play_btn = gr.Button("Play", size="sm", scale=1)
            pause_btn = gr.Button("Pause", size="sm", scale=1)
            restart_btn = gr.Button("Restart", size="sm", scale=1)
            speed = gr.Slider(minimum=0.1, maximum=1.5, step=0.1, value=0.6, label="Speed", scale=2)
            frame_step = gr.Slider(minimum=1, maximum=total_steps, step=1, value=default_step, label="Scrub", scale=5)
            auto_follow = gr.Checkbox(value=True, label="Auto-follow")
            normalized_scale = gr.Checkbox(value=False, label="0-100 scale")

        reasoning = gr.HTML(value=initial_reasoning)
        record = gr.HTML(value=initial_record)
        with gr.Row(elem_classes=["ner-tetra-row"]):
            tetra_plot = gr.Plot(value=initial_tetra_plot, label="Structural State (Tetrahedral)")
            tetra_details = gr.Markdown(value=initial_tetra_text)

        def _on_frame_change(frame_idx, sp, af, ns):
            """Handle frame change and update both classic and unified views."""
            results = load_operations_surface(frame_idx, sp, af, ns)
            return (
                results[0], results[1], results[2], results[3], results[4], results[5], results[6],
                results[7], results[8], results[9], results[10], results[11],
            )

        frame_step.change(
            fn=_on_frame_change,
            inputs=[frame_step, speed, auto_follow, normalized_scale],
            outputs=[status, chart, insight, reasoning, record, tetra_plot, tetra_details,
                    top_bar, system_field, left_panel, right_panel, bottom_timeline],
        )
        auto_follow.change(
            fn=_on_frame_change,
            inputs=[frame_step, speed, auto_follow, normalized_scale],
            outputs=[status, chart, insight, reasoning, record, tetra_plot, tetra_details,
                    top_bar, system_field, left_panel, right_panel, bottom_timeline],
        )
        normalized_scale.change(
            fn=_on_frame_change,
            inputs=[frame_step, speed, auto_follow, normalized_scale],
            outputs=[status, chart, insight, reasoning, record, tetra_plot, tetra_details,
                    top_bar, system_field, left_panel, right_panel, bottom_timeline],
        )

        def _autoplay_wrapper(start_frame, speed_mult):
            """Wrapper for autoplay that updates unified shell."""
            for yield_result in autoplay(start_frame, speed_mult):
                frame, s, c, i, r, re, p, t = yield_result
                ub, sf, lp, rp, bt = load_unified_shell_surface(frame)
                yield frame, s, c, i, r, re, p, t, ub, sf, lp, rp, bt

        play_btn.click(
            fn=_autoplay_wrapper,
            inputs=[frame_step, speed],
            outputs=[frame_step, status, chart, insight, reasoning, record, tetra_plot, tetra_details,
                    top_bar, system_field, left_panel, right_panel, bottom_timeline],
        )
        pause_btn.click(fn=pause_playback)

        def _reset_wrapper():
            """Wrapper for reset that updates unified shell."""
            results = reset_playback()
            frame = results[0]
            ub, sf, lp, rp, bt = load_unified_shell_surface(frame)
            return frame, results[1], results[2], results[3], results[4], results[5], results[6], results[7], ub, sf, lp, rp, bt

        restart_btn.click(fn=_reset_wrapper, outputs=[frame_step, status, chart, insight, reasoning, record, tetra_plot, tetra_details,
                                                      top_bar, system_field, left_panel, right_panel, bottom_timeline])

    return app


