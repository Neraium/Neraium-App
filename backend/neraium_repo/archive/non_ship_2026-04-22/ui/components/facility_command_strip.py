"""Facility Command Strip: Top control surface for facility operations.

Replaces the traditional navigation bar with an operational control surface.
Shows room status, phase information, and facility-wide metrics.

Each room module displays:
- Room name
- Current phase (veg, flower, recovery, etc.)
- System state (nominal, watch, degraded, critical)
- Confidence %
- Last change timing
- Subtle live pulse indicator

Facility-level context:
- Overall facility coherence
- Rooms requiring attention (count)
- Live data timestamp
- Feed latency
"""

from __future__ import annotations

from typing import Any
from html import escape


def _render_room_module(
    room_id: str,
    room_name: str,
    phase: str,
    state: str,
    confidence: float,
    changed_minutes_ago: int | None = None,
) -> str:
    """Render a single room status module.

    Args:
        room_id: Unique room identifier
        room_name: Display name for room
        phase: Current phase (veg, flower, recovery, etc.)
        state: System state (nominal, watch, degraded, critical)
        confidence: Confidence score (0-1)
        changed_minutes_ago: Minutes since last state change

    Returns:
        HTML markup for room module
    """

    state_colors = {
        "nominal": "#22C55E",
        "watch": "#3B82F6",
        "degraded": "#F97316",
        "critical": "#EF4444",
    }
    state_color = state_colors.get(state, "#94A3B8")

    confidence_pct = int(confidence * 100)

    change_text = ""
    if changed_minutes_ago is not None:
        if changed_minutes_ago == 0:
            change_text = "just now"
        elif changed_minutes_ago < 60:
            change_text = f"{changed_minutes_ago}m ago"
        else:
            hours = changed_minutes_ago // 60
            change_text = f"{hours}h ago"

    pulse_class = "ner-pulse-active" if state in ("watch", "degraded", "critical") else "ner-pulse-calm"

    html = f"""
    <div class="ner-room-module" data-room-id="{escape(room_id)}" data-state="{escape(state)}">
        <div class="ner-room-header">
            <span class="ner-room-name">{escape(room_name)}</span>
            <div class="ner-room-pulse {pulse_class}"></div>
        </div>

        <div class="ner-room-info">
            <div class="ner-info-pair">
                <span class="ner-label">Phase</span>
                <span class="ner-value">{escape(phase.upper())}</span>
            </div>
            <div class="ner-info-pair">
                <span class="ner-label">State</span>
                <span class="ner-value" style="color: {state_color}; font-weight: 700;">
                    {escape(state.upper())}
                </span>
            </div>
        </div>

        <div class="ner-room-metrics">
            <div class="ner-confidence-bar">
                <div class="ner-confidence-fill" style="width: {confidence_pct}%;">
                    <span class="ner-confidence-label">{confidence_pct}%</span>
                </div>
            </div>
            {f'<span class="ner-change-timestamp">{change_text}</span>' if change_text else ''}
        </div>
    </div>
    """
    return html


def render_facility_command_strip(
    rooms: list[dict[str, Any]],
    facility_coherence: float,
    rooms_needing_attention: int,
    timestamp: str | None = None,
    feed_latency_ms: int | None = None,
) -> str:
    """Render the facility command strip.

    Args:
        rooms: List of room status dicts with keys:
            room_id, room_name, phase, state, confidence, changed_minutes_ago
        facility_coherence: Overall facility coherence (0-1)
        rooms_needing_attention: Count of rooms requiring immediate attention
        timestamp: ISO timestamp of last update
        feed_latency_ms: Latency of telemetry feed in milliseconds

    Returns:
        HTML markup for the command strip
    """

    facility_coherence_pct = int(facility_coherence * 100)

    timestamp_display = timestamp.split("T")[-1].split("Z")[0] if timestamp else "—"

    latency_display = ""
    if feed_latency_ms is not None:
        if feed_latency_ms < 1000:
            latency_display = f"{feed_latency_ms}ms"
        else:
            latency_display = f"{feed_latency_ms / 1000:.1f}s"

    room_modules = [
        _render_room_module(
            room.get("room_id", f"room_{i}"),
            room.get("room_name", f"Room {i+1}"),
            room.get("phase", "unknown"),
            room.get("state", "nominal"),
            float(room.get("confidence", 0.7)),
            room.get("changed_minutes_ago"),
        )
        for i, room in enumerate(rooms)
    ]

    attention_badge = ""
    if rooms_needing_attention > 0:
        attention_color = "#F97316" if rooms_needing_attention < 3 else "#EF4444"
        attention_badge = f"""
        <div class="ner-attention-badge" style="background-color: {attention_color};">
            <span class="ner-badge-value">{rooms_needing_attention}</span>
            <span class="ner-badge-label">Attention</span>
        </div>
        """

    html = f"""
    <div class="ner-facility-command-strip">
        <div class="ner-strip-header">
            <div class="ner-facility-meta">
                <div class="ner-meta-item">
                    <span class="ner-meta-label">Facility Coherence</span>
                    <span class="ner-meta-value" style="color: #22C55E; font-weight: 700;">
                        {facility_coherence_pct}%
                    </span>
                </div>
                {attention_badge}
                <div class="ner-meta-item">
                    <span class="ner-meta-label">Live Timestamp</span>
                    <span class="ner-meta-value">{escape(timestamp_display)}</span>
                </div>
                {f'<div class="ner-meta-item"><span class="ner-meta-label">Feed Latency</span><span class="ner-meta-value">{escape(latency_display)}</span></div>' if latency_display else ''}
            </div>
        </div>

        <div class="ner-strip-rooms">
            {"".join(room_modules)}
        </div>
    </div>
    """
    return html
