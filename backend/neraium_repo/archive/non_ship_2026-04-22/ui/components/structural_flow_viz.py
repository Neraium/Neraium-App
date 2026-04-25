from __future__ import annotations

from typing import Any

from ui.core_integration import SystemState
from ui.utils import clamp, l2_norm


def _with_alpha(hex_color: str, alpha: float) -> str:
    """Render color as rgba string for soft trail gradients."""
    color = hex_color.lstrip("#")
    if len(color) != 6:
        return f"rgba(125, 142, 255, {clamp(alpha, 0.0, 1.0):.3f})"
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {clamp(alpha, 0.0, 1.0):.3f})"


def _event_point_style(
    point: dict[str, Any],
    *,
    event_type: str,
    recency_ratio: float,
) -> dict[str, Any]:
    """Apply event-specific visual treatment while keeping path geometry unchanged."""
    if event_type == "admitted":
        return {
            **point,
            "event_type": "admitted",
            "color": _with_alpha("#73FFE1", 0.78 + recency_ratio * 0.22),
            "rim_color": _with_alpha("#D3FFF5", 0.74 + recency_ratio * 0.2),
            "glow": round(0.72 + recency_ratio * 0.34, 3),
            "opacity": round(0.92 + recency_ratio * 0.08, 3),
            "radius": round(4.6 + recency_ratio * 3.8, 3),
            "pulse": round(0.18 + recency_ratio * 0.24, 3),
            "blend_mode": "screen",
        }
    return {
        **point,
        "event_type": "suppressed",
        "color": _with_alpha("#9F8D86", 0.1 + recency_ratio * 0.14),
        "rim_color": _with_alpha("#B89C93", 0.14 + recency_ratio * 0.15),
        "glow": round(0.04 + recency_ratio * 0.09, 3),
        "opacity": round(0.12 + recency_ratio * 0.15, 3),
        "radius": round(2.0 + recency_ratio * 1.25, 3),
        "pulse": round(0.0 + recency_ratio * 0.03, 3),
        "blur": round(0.12 + recency_ratio * 0.16, 3),
        "diffusion_halo": _with_alpha("#D47A5F", 0.08 + recency_ratio * 0.08),
        "edge_sharpness": round(0.24 + recency_ratio * 0.16, 3),
        "saturation": round(0.42 + recency_ratio * 0.16, 3),
        "admissibility": "denied_reality",
        "blend_mode": "multiply",
    }


def render_structural_flow_viz(
    state: SystemState,
    gate_decision: dict[str, Any] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    """Replay-driven system trajectory chart model."""
    tail = [{"x": p.x, "y": p.y, "t": p.t} for p in state.trajectory_history]
    velocity_mag = l2_norm(state.velocity)
    trail_count = max(len(tail), 1)

    fading_tail = [
        {
            **point,
            "opacity": round(0.09 + (idx + 1) / trail_count * 0.86, 4),
            "glow": round(0.11 + (idx + 1) / trail_count * 0.72, 4),
            "radius": round(1.9 + (idx + 1) / trail_count * 4.9, 3),
            "color": _with_alpha("#738FFF", 0.07 + (idx + 1) / trail_count * 0.54),
        }
        for idx, point in enumerate(tail)
    ]

    vector_tip = {
        "x": clamp(state.position.x + state.velocity[0] * 2.4, 0.0, 1.0),
        "y": clamp(state.position.y + state.velocity[1] * 2.4, 0.0, 1.0),
    }
    regime_phase = "coherence"
    if state.drift_intensity >= 0.7:
        regime_phase = "divergence"
    elif state.drift_intensity >= 0.4:
        regime_phase = "transition"

    decision = (gate_decision or {}).get("decision")
    decision_upper = str(decision or "").upper()
    suppressed_scene = decision_upper == "SUPPRESS"
    admit_points = [point for point in tail if decision == "ADMIT"]
    suppress_points = [point for point in tail if decision == "SUPPRESS"]
    void_points = [point for point in tail if decision == "ADMISSIBILITY_VOID"]
    rows = records or []
    replay_series = []
    for idx, row in enumerate(rows):
        try:
            signal_value = float(row.get("dynamic_signal_strength", row.get("structural_drift_score", 0.0)))
        except (TypeError, ValueError):
            signal_value = 0.0
        try:
            drift_value = float(row.get("structural_drift_score", signal_value))
        except (TypeError, ValueError):
            drift_value = signal_value
        try:
            stability_value = float(row.get("relational_stability_score", 1.0 - drift_value))
        except (TypeError, ValueError):
            stability_value = 1.0 - drift_value
        replay_series.append(
            {
                "index": idx,
                "timestamp": row.get("timestamp"),
                "signal": clamp(signal_value, 0.0, 1.0),
                "drift": clamp(drift_value, 0.0, 1.0),
                "stability": clamp(stability_value, 0.0, 1.0),
                "phase": str(row.get("system_phase") or row.get("transition_type") or row.get("regime_name") or "unknown"),
                "event_admitted": bool(row.get("event_admitted")),
            }
        )
    indexed_tail = list(enumerate(tail))

    stable_points = [point for idx, point in indexed_tail if idx < len(rows) and str(rows[idx].get("transition_type", "STABLE")).upper() == "STABLE"]
    transition_points = [
        point for idx, point in indexed_tail if idx < len(rows) and str(rows[idx].get("transition_type", "")).upper() == "TRANSITION"
    ]
    reorganization_points = [
        point for idx, point in indexed_tail if idx < len(rows) and str(rows[idx].get("transition_type", "")).upper() == "REORGANIZATION"
    ]
    admitted_event_pairs = [(idx, point) for idx, point in indexed_tail if idx < len(rows) and bool(rows[idx].get("event_admitted"))]
    if str(decision or "SUPPRESS").upper() == "SUPPRESS" and rows and tail:
        admitted_event_pairs = [(idx, point) for idx, point in admitted_event_pairs if idx != len(tail) - 1]
    admitted_event_points = [point for _, point in admitted_event_pairs]
    suppressed_event_points = [
        point for idx, point in indexed_tail if idx < len(rows) and rows[idx].get("event_admitted") is False
    ]
    admitted_styled_points = [
        _event_point_style(point, event_type="admitted", recency_ratio=(idx + 1) / max(len(admitted_event_points), 1))
        for idx, point in enumerate(admitted_event_points)
    ]
    suppressed_styled_points = [
        _event_point_style(point, event_type="suppressed", recency_ratio=(idx + 1) / max(len(suppressed_event_points), 1))
        for idx, point in enumerate(suppressed_event_points)
    ]

    return {
        "surface": "system_navigation_field",
        "canvas": {
            "style": "dark_spatial",
            "frame": "frameless",
            "axes": "hidden",
            "grid": "off",
            "chrome": "none",
            "background": {
                "base": "#040713",
                "radial_tint": ["#11183A", "#0A1230", "#05070F"],
                "vignette": 0.5,
                "noise": 0.028,
            },
            "depth_layers": {
                "near_field": {"tone": _with_alpha("#1A2556", 0.34), "contrast": 0.88},
                "far_field": {"tone": _with_alpha("#080C1A", 0.72), "contrast": 0.64},
            },
            "gate_scene_tone": {
                "mode": "suppressed_withheld" if suppressed_scene else "clear",
                "global_desaturation": 0.08 if suppressed_scene else 0.0,
                "warm_amber_overlay": {
                    "color": _with_alpha("#B87443", 0.08 if suppressed_scene else 0.0),
                    "blend": "soft_light",
                },
                "global_glow_scale": 0.9 if suppressed_scene else 1.0,
                "readability_guard": "preserve_trajectory_and_current_position",
            },
        },
        "trajectory": {
            "type": "continuous_tail",
            "path": tail,
            "fading_tail": fading_tail,
            "gradient_trail": {
                "from": _with_alpha("#5CCAFF", 0.18),
                "via": _with_alpha("#7F87FF", 0.34),
                "to": _with_alpha("#B35EFF", 0.62),
            },
            "path_contrast": {"stroke_alpha": 0.82, "trail_alpha": 0.58},
            "interpolation": {
                "enabled": True,
                "style": "catmull_rom",
                "substeps": 3,
                "smoothing": round(clamp(0.45 + velocity_mag, 0.45, 0.92), 3),
            },
        },
        "replay_series": replay_series,
        "current_position": {
            "x": state.position.x,
            "y": state.position.y,
            "t": state.position.t,
            "highlight": "focus_node",
            "halo_radius": round(clamp(0.052 + velocity_mag * 0.14, 0.052, 0.19), 4),
            "glow": round(clamp(0.68 + state.drift_intensity * 0.32, 0.68, 1.0), 3),
            "core_radius": round(clamp(0.012 + velocity_mag * 0.025, 0.012, 0.038), 4),
            "priority_lighting": "over_event_layers",
            "clarity_protection": "gate_scene_tone_exempt",
            "phase": regime_phase,
            "dominance": "primary_focus",
        },
        "velocity_vector": {
            "origin": {"x": state.position.x, "y": state.position.y},
            "tip": vector_tip,
            "dx": state.velocity[0],
            "dy": state.velocity[1],
            "magnitude": round(velocity_mag, 6),
            "arrow": {"style": "soft", "glow": 0.68, "head_size": "small", "opacity": 0.74},
        },
        "projected_forward_region": {
            "kind": "cone",
            "samples": [{"x": p.x, "y": p.y, "t": p.t} for p in state.projected_cone],
            "opacity": round(clamp(0.15 + velocity_mag * 1.4, 0.15, 0.7), 3),
            "blur": round(clamp(0.35 + state.drift_intensity * 0.4, 0.35, 0.82), 3),
        },
        "stability_region_hints": {
            "bands": state.stability_regions,
            "stable_tone": _with_alpha("#73B9FF", 0.12),
            "transition_tone": _with_alpha("#9E88FF", 0.22),
            "divergence_tone": _with_alpha("#FF9770", 0.26),
            "field_distinction": "stable_low_energy_transition_active_reorganization_hot",
        },
        "gate_coupling": {
            "decision": decision,
            "admit_highlights": {
                "points": admit_points,
                "style": "highlight",
                "color": _with_alpha("#62FFB3", 0.85),
            },
            "suppress_regions": {
                "points": suppress_points,
                "style": "fade",
                "color": _with_alpha("#FF8B8B", 0.55),
            },
            "void_regions": {
                "points": void_points,
                "style": "uncertain",
                "color": _with_alpha("#BBA1FF", 0.65),
            },
        },
        "phase_layers": {
            "stable_baseline": stable_points,
            "stable_baseline_style": {
                "color": _with_alpha("#6E7D9D", 0.2),
                "glow": 0.08,
                "radius": 1.8,
                "energy": "calm",
            },
            "transition": transition_points,
            "transition_style": {
                "color": _with_alpha("#8F87FF", 0.32),
                "glow": 0.34,
                "radius": 2.6,
                "energy": "mobilizing",
            },
            "reorganization": reorganization_points,
            "reorganization_style": {
                "color": _with_alpha("#FF9E78", 0.4),
                "glow": 0.48,
                "radius": 3.1,
                "energy": "transformative",
            },
            "admitted_events": admitted_styled_points,
            "suppressed_events": suppressed_styled_points,
            "event_visual_encoding": {
                "continuity_anchor": "trajectory.path",
                "path_vs_event_separation": {
                    "trajectory_blend": "additive_soft",
                    "event_blend": "screen_for_admit_multiply_for_suppress",
                },
                "admitted": {
                    "color": "#73FFE1",
                    "glow_range": [0.72, 1.06],
                    "opacity_range": [0.92, 1.0],
                    "radius_range": [4.6, 8.4],
                    "semantic_weight": "consequential",
                },
                "suppressed": {
                    "color": "#9F8D86",
                    "glow_range": [0.05, 0.15],
                    "opacity_range": [0.14, 0.3],
                    "radius_range": [2.0, 3.25],
                    "semantic_weight": "deemphasized",
                    "admissibility_state": "observed_not_admitted",
                    "uncertainty_treatment": {
                        "blur": "soft",
                        "diffusion_halo": "faint_amber",
                        "edge_sharpness": "low",
                    },
                },
            },
        },
    }
