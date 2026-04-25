"""Output assembly and schema packaging.

Responsibilities:
- Result template creation with defaults
- Schema compliance and field formatting
- Backward-compatible field mapping
- Safe defaults for warmup and degraded modes
- Pure assembly, no computation

Note: This layer handles all output formatting. It is deliberately
separated from detection logic so packaging changes don't affect core.
"""

from typing import Dict, Any


def create_warmup_payload(frame: Dict[str, object]) -> Dict[str, object]:
    """Create safe default payload during warmup (windows not yet full).

    Returns:
        Dictionary with required fields but unavailable metrics marked as such
    """
    return {
        "timestamp": frame.get("timestamp"),
        "site_id": frame.get("site_id"),
        "asset_id": frame.get("asset_id"),
        "state": "STABLE",
        "policy_state": "STABLE",
        "policy_watch": False,
        "policy_alert": False,
        "structural_drift_score": 0.0,
        "structural_drift_score_smoothed": 0.0,
        "drift_smooth": 0.0,
        "relational_stability_score": 1.0,
        "dynamic_signal_strength": 0.0,
        "system_phase": "STABLE",
        "transition_detected": False,
        "system_health": 100,
        "drift_alert": False,
        "regime_name": None,
        "regime_distance": None,
        "regime_drift": 0.0,
        "latest_drift": 0.0,
        "latest_drift_smoothed": 0.0,
        "watch_threshold": None,
        "alert_threshold": None,
        "latest_instability": 0.0,
        "relational_instability_score": 0.0,
        "temporal_distortion_score": 0.0,
        "localization_score": 0.0,
        "attribution": {"top_drivers": [], "driver_scores": {}},
        "causal_analysis": {
            "hypotheses": [],
            "top_hypothesis": None,
            "counterfactual": {
                "counterfactual_checks": [],
                "robustness": 0.0,
                "interpretation": "Causal analysis unavailable during warmup.",
            },
            "validation_plan": [],
            "recommended_sequence": [],
            "best_next_action": None,
            "status": {"available": False, "reason": "warmup"},
        },
        "dominant_driver": None,
        "explanation": "Warmup: awaiting sufficient window history.",
        "baseline_mode": None,
        "data_quality_summary": {},
        "active_sensor_count": 0,
        "missing_sensor_count": 0,
        "transition_pressure": 0.0,
        "transition_state": "NONE",
        "robustness": {},
        "sensitivity": {},
        "explanations": {},
        "multi_scale": {},
        "drift_noise": {},
        "geometry": {"available": False, "reason": "insufficient history"},
        "state_space_statistics": {"available": False, "reason": "insufficient history"},
        "state_graph": {"available": False, "reason": "insufficient history"},
        "geometry_explanations": {"available": False, "reason": "insufficient history"},
    }


def update_result_with_detections(
    result: Dict[str, Any],
    detections: Dict[str, Any],
) -> None:
    """Update result payload with computed detection metrics.

    Args:
        result: Result payload (will be mutated)
        detections: Detection results from orchestrator

    Returns:
        None (mutates result in place)
    """
    # Policy state from drift detector
    result["state"] = detections.get("alert_state", "STABLE")
    result["policy_state"] = detections.get("alert_state", "STABLE")
    result["policy_watch"] = detections.get("alert_state", "STABLE") == "WATCH"
    result["policy_alert"] = detections.get("alert_state", "STABLE") == "ALERT"
    result["drift_alert"] = detections.get("alert_state", "STABLE") == "ALERT"

    # Drift scores
    drift_score = float(detections.get("drift_score", 0.0))
    result["structural_drift_score"] = round(drift_score, 4)
    result["latest_drift"] = round(drift_score, 4)

    # Data quality
    dq_summary = detections.get("data_quality_summary", {})
    result["data_quality_summary"] = dq_summary
    result["active_sensor_count"] = int(dq_summary.get("valid_signal_count", 0))
    result["missing_sensor_count"] = int(dq_summary.get("missing_sensor_count", 0))

    # Relational metrics
    rel_metrics = detections.get("relational_metrics", {})
    result["relational_instability_score"] = round(
        float(rel_metrics.get("relational_drift", 0.0)), 4
    )

    # Temporal
    temp_metrics = detections.get("temporal_metrics", {})
    result["temporal_distortion_score"] = round(
        float(temp_metrics.get("temporal_consistency", 0.0)), 4
    )

    # Early warning
    warning = detections.get("early_warning", {})
    if isinstance(warning, dict):
        result["explanation"] = f"Variance signal: {warning.get('variance', 0.0):.3f}"

    # Valid signal count
    result["active_sensor_count"] = int(detections.get("valid_count", 0))


def round_numeric_fields(result: Dict[str, Any]) -> None:
    """Round numeric fields to maintain precision consistency.

    Args:
        result: Result payload (will be mutated)
    """
    # Core metrics: 4 decimals
    for key in [
        "structural_drift_score",
        "structural_drift_score_smoothed",
        "drift_smooth",
        "relational_stability_score",
        "dynamic_signal_strength",
        "latest_drift",
        "latest_drift_smoothed",
        "relational_instability_score",
        "temporal_distortion_score",
        "transition_pressure",
    ]:
        if key in result and isinstance(result[key], float):
            result[key] = round(result[key], 4)
