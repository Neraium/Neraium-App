"""Response builders — translate SIIEngineAdapter unified output into API shapes.

The new engine emits canonical regime + urgency directly. We map:
  urgency NOMINAL/WATCH/ALERT/CRITICAL -> operational_risk LOW/MODERATE/HIGH/CRITICAL
  regime  STABLE/TRANSITION/UNSTABLE/LOCK_IN/WARMUP -> situation_summary text

No more attribution / causal_chains / regime_distance — the new engine has a
narrower contract. The intelligence panel is rebuilt from instability_history
and regime_history.
"""
from __future__ import annotations
from typing import Dict, Any, List

from .serialise import sfloat, sf
from . import engine_service as es


# Map urgency -> operational_risk
URGENCY_RISK = {
    "NOMINAL":  "LOW",
    "WATCH":    "MODERATE",
    "ALERT":    "HIGH",
    "CRITICAL": "CRITICAL",
}

# Map urgency -> UI urgency level
URGENCY_LEVEL = {
    "NOMINAL":  "low",
    "WATCH":    "medium",
    "ALERT":    "high",
    "CRITICAL": "critical",
}

# Per (regime, urgency) situation-summary text (operator language)
def _situation_summary(regime: str, urgency: str) -> str:
    if regime == "WARMUP":
        return "System warming up — collecting baseline before issuing decisions."
    if regime == "STABLE" and urgency == "NOMINAL":
        return "All variables operating within nominal coupling."
    if regime == "STABLE":
        return "System nominal but minor instability detected — monitor closely."
    if regime == "TRANSITION" and urgency in ("NOMINAL", "WATCH"):
        return "Structural drift developing — early warning active."
    if regime == "TRANSITION":
        return "Structural shift in progress — system leaving baseline regime."
    if regime == "UNSTABLE" and urgency == "WATCH":
        return "Structural shift confirmed — correction still possible."
    if regime == "UNSTABLE" and urgency == "ALERT":
        return "Structural shift accelerating — intervention window narrowing."
    if regime == "UNSTABLE":
        return "Subsystem coupling degraded — operator action required."
    if regime == "LOCK_IN":
        return "System approaching irreversible structural lock-in."
    return f"System in {regime} regime ({urgency.lower()})."


def reconcile(r: dict) -> dict:
    """Map SII outputs to legacy reconciled fields used across endpoints."""
    regime = r.get("regime", r.get("interpreted_state", "STABLE"))
    urgency = r.get("urgency", "NOMINAL")
    operational_risk = URGENCY_RISK.get(urgency, "LOW")
    velocity = sfloat(r.get("drift_velocity"))
    pressure = sfloat(r.get("transition_pressure"))

    # Legacy detection_stage labels
    if regime == "WARMUP":
        detection_stage = "WARMUP"
    elif urgency == "NOMINAL":
        detection_stage = "NOMINAL"
    elif urgency == "WATCH":
        detection_stage = "EARLY_WARNING"
    elif urgency == "ALERT":
        detection_stage = "ALERT"
    elif urgency == "CRITICAL":
        detection_stage = "LOCK_IN"
    else:
        detection_stage = urgency

    return {
        "policy_state": URGENCY_RISK.get(urgency, "LOW"),
        "regime": regime,
        "engine_risk": urgency,
        "operational_risk": operational_risk,
        "detection_stage": detection_stage,
        "situation_summary": _situation_summary(regime, urgency),
        "drift_velocity": velocity,
        "drift_velocity_high": velocity > 0.01,
        "reversibility": "LOCKED_IN" if regime == "LOCK_IN" else "REVERSIBLE",
        "transition_pressure": pressure,
    }


def build_system_state(r: dict) -> dict:
    rec = reconcile(r)
    return {
        "state": r.get("state"),                 # legacy STABLE/WATCH/ALERT
        "interpreted_state": r.get("regime"),    # canonical regime
        "regime": r.get("regime"),
        "urgency": r.get("urgency"),
        "phase": r.get("phase", "stable"),
        "risk_level": rec["operational_risk"],
        "engine_risk_level": r.get("urgency"),
        "operational_risk": rec["operational_risk"],
        "situation_summary": rec["situation_summary"],
        "detection_stage": rec["detection_stage"],
        "confidence_score": sfloat(r.get("confidence_score")),
        "regime_name": r.get("regime_name") or r.get("regime"),
        "regime_distance": r.get("regime_distance"),
        "engine_ready": r.get("engine_ready", False),
        "transition_state": r.get("transition_state", "NONE"),
        "transition_pressure": sfloat(r.get("transition_pressure")),
        "operator_message": r.get("operator_message", ""),
        "signal_emitted": r.get("signal_emitted", False),
        "timestamp": r.get("timestamp"),
        "asset_id": r.get("_asset_id") or r.get("asset_id"),
    }


def build_metrics(r: dict) -> dict:
    return {
        "structural_drift_score": sfloat(r.get("structural_drift_score")),
        "instability_score": sfloat(r.get("instability_score")),
        "relational_instability_score": sfloat(r.get("instability_score")),  # legacy alias
        "transition_pressure": sfloat(r.get("transition_pressure")),
        "drift_velocity": sfloat(r.get("drift_velocity")),
        "confidence_score": sfloat(r.get("confidence_score")),
        "gradient_norm": sfloat(r.get("gradient_norm")),
        "recovery_alignment": sfloat(r.get("recovery_alignment")),
        "latest_instability": sfloat(r.get("instability_score")),
        "system_health": int(round(max(0.0, 1.0 - sfloat(r.get("instability_score"))) * 100)),
        "regime": r.get("regime"),
        "urgency": r.get("urgency"),
        "timestamp": r.get("timestamp"),
        "asset_id": r.get("_asset_id") or r.get("asset_id"),
    }


def build_intelligence(r: dict) -> dict:
    """Intelligence panel content rebuilt from SIIEngine outputs.

    The new engine doesn't expose causal chains or attribution — we surface
    what's available: regime/urgency history and the detection context.
    """
    rec = reconcile(r)
    inst_hist = r.get("instability_history") or []
    regime_hist = r.get("regime_history") or []
    velocity_hist = r.get("velocity_history") or []
    explanation = (
        f"Engine regime: {r.get('regime')}. Urgency: {r.get('urgency')}. "
        f"Instability {sfloat(r.get('instability_score')):.3f} over the last "
        f"{len(inst_hist)} cycles."
    )
    return {
        "explanation": explanation,
        "situation_summary": rec["situation_summary"],
        "operational_risk": rec["operational_risk"],
        "detection_stage": rec["detection_stage"],
        "regime": r.get("regime"),
        "urgency": r.get("urgency"),
        "instability_history": inst_hist,
        "regime_history": regime_hist,
        "velocity_history": velocity_hist,
        "lead_time_cycles": r.get("lead_time_cycles"),
        "first_detection_cycle": r.get("first_detection_cycle"),
        "detection_confidence": sfloat(r.get("detection_confidence")),
        "reversibility_classification": rec["reversibility"],
        "timestamp": r.get("timestamp"),
        "asset_id": r.get("_asset_id") or r.get("asset_id"),
    }


def build_rooms(r: dict) -> dict:
    """SensorsTab — show monitored sensor names. SIIEngine doesn't compute
    per-sensor attribution, so driver_score is omitted (frontend gracefully
    falls back to 0)."""
    sensors = r.get("sensor_relationships", []) or []
    rooms = [{"sensor_id": name, "driver_score": 0.0, "is_top_driver": False} for name in sensors]
    return {
        "sensor_count": len(sensors),
        "active_sensor_count": r.get("active_sensor_count", len(sensors)),
        "missing_sensor_count": 0,
        "sensors": rooms,
        "data_quality": {},
        "asset_id": r.get("_asset_id") or r.get("asset_id"),
    }


def build_future_path_map(asset_id: str) -> dict:
    """Future-path map derived from regime + urgency + drift velocity."""
    results = es.get_results(asset_id)
    if not results:
        return {"available": False, "reason": "No results yet"}
    last = results[-1]
    rec = reconcile(last)
    return {
        "available": True,
        "current_state": {
            "regime_name": last.get("regime"),
            "health_band": (last.get("urgency") or "NOMINAL").lower(),
            "confidence": sfloat(last.get("confidence_score")),
            "structural_drift": sfloat(last.get("structural_drift_score")),
            "instability": sfloat(last.get("instability_score")),
        },
        "trajectory_label": rec["detection_stage"],
        "reversibility_classification": rec["reversibility"],
        "asset_id": asset_id,
    }


def build_operator_decision(r: dict) -> dict:
    """Synthesise the operator-language decision strip from SIIEngine fields."""
    asset_id = r.get("_asset_id") or r.get("asset_id")
    sensors = r.get("sensor_relationships", []) or []
    coupling_desc = ", ".join(sensors[:3]) if sensors else "monitored variables"
    primary_var = sensors[0] if sensors else "primary variable"
    secondary_var = sensors[1] if len(sensors) > 1 else "baseline"

    rec = reconcile(r)
    regime = r.get("regime", "STABLE")
    urgency = r.get("urgency", "NOMINAL")
    velocity = rec["drift_velocity"]
    velocity_text = f" (drift velocity: {velocity:.4f}/cycle" + (", accelerating)" if rec["drift_velocity_high"] else ")")
    op_risk = rec["operational_risk"]
    urgency_level = URGENCY_LEVEL.get(urgency, "low")
    reversibility = rec["reversibility"]
    drift = sfloat(r.get("structural_drift_score"))
    instability = sfloat(r.get("instability_score"))
    pressure = rec["transition_pressure"]

    # Compute legacy lead_time_cycles from results history
    results = es.get_results(asset_id)
    watch_frame, alert_frame = None, None
    for res in results:
        if watch_frame is None and res.get("urgency") == "WATCH":
            watch_frame = res.get("_index")
        if alert_frame is None and res.get("urgency") == "ALERT":
            alert_frame = res.get("_index")
    lead_time_cycles = (alert_frame - watch_frame) if (alert_frame is not None and watch_frame is not None) else r.get("lead_time_cycles")

    # NOW
    if regime == "WARMUP":
        now = "Engine is warming up — collecting baseline. Monitoring before any decision."
    elif urgency == "NOMINAL":
        now = f"All {len(sensors) or 'monitored'} variables coupled normally. {coupling_desc.capitalize()} stable."
    elif urgency == "WATCH":
        now = f"{coupling_desc.capitalize()} coupling diverging from baseline. Early warning active."
    elif urgency == "ALERT" and regime == "UNSTABLE":
        now = f"{coupling_desc.capitalize()} have decoupled — system is in unstable regime."
    elif urgency == "ALERT":
        now = f"Critical drift in {coupling_desc} — coupling is breaking down."
    elif urgency == "CRITICAL":
        now = f"System approaching lock-in — {coupling_desc} no longer recoverable through normal correction."
    else:
        now = f"System in {regime} regime."

    # URGENCY window
    if urgency == "NOMINAL":
        urgency_window = rec["situation_summary"]
    elif urgency == "WATCH":
        urgency_window = f"alert projected in ~{lead_time_cycles or '5-10'} cycles at current drift velocity{velocity_text}" if lead_time_cycles else f"structural drift developing — early warning active{velocity_text}"
    elif urgency == "ALERT":
        urgency_window = f"structural shift accelerating — intervention window narrowing{velocity_text}"
    elif urgency == "CRITICAL":
        urgency_window = f"system approaching irreversible structural lock-in{velocity_text}"
    else:
        urgency_window = rec["situation_summary"]

    # DO THIS
    if regime == "WARMUP":
        do_this = "Wait for baseline to complete"
        expected_effect = "Engine will transition to STABLE once baseline window is filled."
        action_timeframe = f"~{es.asset_readiness(asset_id).get('baseline_window', 50)} cycles"
    elif urgency == "NOMINAL":
        do_this = "Continue normal operations"
        expected_effect = "System maintains nominal coupling."
        action_timeframe = "ongoing"
    elif urgency == "WATCH":
        do_this = f"Reduce {primary_var} variability and stabilise {secondary_var} coupling"
        expected_effect = f"Coupling between {coupling_desc} should normalise within 5-10 cycles if corrected."
        action_timeframe = "5-10 cycles"
    elif urgency == "ALERT" and reversibility == "REVERSIBLE":
        do_this = f"Reduce {primary_var} volatility to restore coupling with {secondary_var}"
        expected_effect = "Coupling should normalise within 5-10 cycles if corrected. Regime shift is still reversible."
        action_timeframe = "5-10 cycles"
    elif urgency in ("ALERT", "CRITICAL"):
        do_this = f"Stabilise {primary_var} and recalibrate {secondary_var} baseline"
        expected_effect = "Manual recalibration needed — current trajectory is locked, automatic recovery unlikely."
        action_timeframe = "requires manual intervention"
    else:
        do_this = "Review subsystem coupling"
        expected_effect = "—"
        action_timeframe = "—"

    # IF IGNORED
    if urgency == "NOMINAL" or regime == "WARMUP":
        if_ignored = "No risk — all variables coupled normally."
    elif urgency == "WATCH":
        if_ignored = f"Drift will accelerate — {primary_var} instability will propagate to {secondary_var}."
    elif urgency == "ALERT" and reversibility == "REVERSIBLE":
        if_ignored = f"Intervention window is closing — continued drift in {primary_var} risks permanent regime shift."
    elif urgency in ("ALERT", "CRITICAL"):
        if_ignored = f"System will lock into degraded regime — {primary_var} will settle into a new structural baseline."
    else:
        if_ignored = "Instability will propagate across all monitored variables."

    perception = f"{len(sensors) or '?'} variables monitored · instability={instability:.2f} · drift={drift:.2f}"
    interpretation = now
    urgency_desc = f"{urgency_level.upper()} — {urgency_window}"
    outcome = (
        "System remains in normal operating envelope." if urgency == "NOMINAL"
        else f"Corrective action can restore baseline coupling. {expected_effect}" if reversibility == "REVERSIBLE"
        else f"Without intervention, system will settle into degraded structural regime. {expected_effect}"
    )

    # Future paths
    recovery: Dict[str, Any] = None
    degradation: Dict[str, Any] = None
    failure: Dict[str, Any] = None
    if urgency in ("WATCH", "ALERT", "CRITICAL"):
        recovery_eta = "5-10 cycles with corrective action" if reversibility == "REVERSIBLE" else "requires manual recalibration"
        recovery = {
            "label": "Recovery", "eta": recovery_eta,
            "action": f"Reduce {primary_var} variability and restore coupling with {secondary_var}.",
            "expected_outcome": expected_effect,
            "probability": "achievable" if reversibility == "REVERSIBLE" and pressure < 0.6 else "difficult" if reversibility == "REVERSIBLE" else "low",
        }
        deg_eta = f"~{int(drift / max(velocity, 0.001))} cycles at current velocity" if velocity > 0.001 else "gradual"
        degradation = {
            "label": "Degradation", "eta": deg_eta,
            "action": f"{primary_var.capitalize()} continues diverging — connected variables compensate then decouple.",
            "expected_outcome": f"All {len(sensors) or 'monitored'} variables will progressively lose structural coupling.",
            "probability": "likely without action",
        }
        failure = {
            "label": "Failure",
            "eta": f"~{int(drift / max(velocity, 0.001)) * 2} cycles or triggered by external disruption" if velocity > 0.001 else "uncertain",
            "action": f"Cascading decoupling across all {len(sensors) or 'monitored'} variables.",
            "expected_outcome": "Complete structural regime failure. System enters uncharted operating territory.",
            "probability": "possible if degradation path is not interrupted",
        }
    elif urgency == "NOMINAL":
        recovery = {"label": "Nominal", "eta": "current",
                    "action": "All variables operating within normal coupling.",
                    "expected_outcome": "System maintains baseline.", "probability": "current state"}

    return {
        "now": now,
        "urgency": {"level": urgency_level, "window": urgency_window, "description": urgency_desc},
        "do_this": do_this,
        "expected_effect": expected_effect,
        "action_timeframe": action_timeframe,
        "if_ignored": if_ignored,
        "decision_chain": {
            "perception": perception,
            "interpretation": interpretation,
            "urgency": urgency_desc,
            "action": f"{do_this}. Expected: {expected_effect}",
            "outcome": outcome,
        },
        "future_paths": {"recovery": recovery, "degradation": degradation, "failure": failure},
        "model_outputs": {
            "lead_time_cycles": lead_time_cycles,
            "drift_velocity": round(velocity, 6),
            "drift_velocity_increasing": rec["drift_velocity_high"],
            "detection_stage": rec["detection_stage"],
            "operational_risk": rec["operational_risk"],
            "situation_summary": rec["situation_summary"],
            "structural_drift_score": round(drift, 4),
            "instability_score": round(instability, 4),
            "transition_pressure": round(pressure, 4),
            "regime": regime,
            "urgency": urgency,
        },
        "propagation_path": [],
        "state": r.get("state"),
        "regime": regime,
        "risk_level": rec["operational_risk"],
        "engine_risk_level": urgency,
        "reversibility": reversibility,
        "signal_emitted": r.get("signal_emitted", False),
    }
