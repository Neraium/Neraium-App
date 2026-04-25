"""Decision narrative synthesizer.

Given a single SII unified state plus the system's recent variable history,
produce the four operator-language fields:

  - what: what is happening
  - why:  which variables are leading the drift (data-driven attribution
          via covariance change against the baseline window)
  - do:   what action will likely restore baseline
  - ignored: consequences of inaction

Generic — no domain assumptions. Variable names are surfaced verbatim;
the operator chooses the meaning.
"""
from __future__ import annotations
from typing import Dict, List, Any, Tuple
import numpy as np

from . import sii_state as ss


URGENCY_LEVEL = {"NOMINAL": "low", "WATCH": "medium", "ALERT": "high", "CRITICAL": "critical"}
URGENCY_RISK = {"NOMINAL": "LOW", "WATCH": "MODERATE", "ALERT": "HIGH", "CRITICAL": "CRITICAL"}


def _data_driven_drivers(system_id: str, top_k: int = 3) -> List[Tuple[str, float]]:
    """Compute per-variable drift contribution by comparing the standard
    deviation in the recent window vs the baseline window. The variable
    with the largest relative variance increase is the "leader" of the drift.

    Returns list of (variable_name, score) sorted desc.
    """
    rec = ss.get_system(system_id)
    if rec is None or len(rec.sensor_history) < 30:
        return []
    arr = np.array([[s.get(v, 0.0) for v in rec.variables] for s in rec.sensor_history])
    if arr.shape[0] < 24:
        return []
    baseline = arr[:24]
    recent = arr[-12:] if arr.shape[0] >= 12 else arr[-arr.shape[0]:]
    base_std = baseline.std(axis=0) + 1e-9
    recent_std = recent.std(axis=0)
    ratio = recent_std / base_std
    pairs = [(rec.variables[i], float(ratio[i])) for i in range(len(rec.variables))]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_k]


def _situation_summary(regime: str, urgency: str) -> str:
    if regime == "WARMUP":
        return "Engine warming up — collecting baseline before issuing decisions."
    if urgency == "NOMINAL":
        return "All variables coupled within nominal envelope."
    if urgency == "WATCH":
        return "Subsystem coupling diverging from baseline — early warning."
    if urgency == "ALERT" and regime == "UNSTABLE":
        return "Coupling broken — system in unstable regime."
    if urgency == "ALERT":
        return "Structural shift accelerating — intervention window narrowing."
    if urgency == "CRITICAL":
        return "Approaching irreversible structural lock-in."
    return f"System in {regime.lower()} regime."


def build_decision(system_id: str) -> Dict[str, Any]:
    last = ss.latest_state(system_id)
    rec = ss.get_system(system_id)
    if last is None or rec is None:
        return {"available": False}

    regime = last["regime"]
    urgency = last["urgency"]
    risk = URGENCY_RISK.get(urgency, "LOW")
    level = URGENCY_LEVEL.get(urgency, "low")
    velocity = float(last["drift_velocity"])
    instability = float(last["instability_score"])
    drift = float(last["structural_drift"])
    pressure = float(last["transition_pressure"])
    confidence = float(last["confidence"])

    drivers = _data_driven_drivers(system_id, top_k=3)
    primary = drivers[0][0] if drivers else (rec.variables[0] if rec.variables else "primary variable")
    secondary = drivers[1][0] if len(drivers) > 1 else (rec.variables[1] if len(rec.variables) > 1 else "baseline")
    coupling_desc = ", ".join(d[0] for d in drivers) if drivers else "monitored variables"

    # WHAT
    if regime == "WARMUP":
        what = "Engine is collecting baseline. No decisions issued yet."
    elif urgency == "NOMINAL":
        what = f"All {len(rec.variables)} variables coupled normally. {coupling_desc} stable."
    elif urgency == "WATCH":
        what = f"{coupling_desc.capitalize()} diverging from baseline coupling. Early instability."
    elif urgency == "ALERT" and regime == "UNSTABLE":
        what = f"{coupling_desc.capitalize()} have decoupled — system has entered an unstable regime."
    elif urgency == "ALERT":
        what = f"Critical drift in {coupling_desc} — coupling structure is breaking down."
    elif urgency == "CRITICAL":
        what = f"System approaching lock-in. {coupling_desc.capitalize()} no longer recoverable through normal correction."
    else:
        what = _situation_summary(regime, urgency)

    # WHY (data-driven attribution)
    if not drivers:
        why = "Baseline still forming — driver attribution requires more frames."
    else:
        leader_name, leader_ratio = drivers[0]
        if leader_ratio > 1.3:
            why = (f"{leader_name} variance has expanded {leader_ratio:.1f}× vs baseline. "
                   + (f"{drivers[1][0]} variance ({drivers[1][1]:.1f}×) is following. " if len(drivers) > 1 else "")
                   + "Coupling structure is breaking down.")
        else:
            why = f"Variance roughly stable ({leader_ratio:.2f}× baseline). Drift is structural rather than amplitude-driven."

    # DO
    if regime == "WARMUP":
        do = "Wait for baseline window to fill"
        expected = "System will transition to STABLE once baseline is locked."
        timeframe = "automatic"
    elif urgency == "NOMINAL":
        do = "Continue normal operations — monitor"
        expected = "System maintains nominal coupling."
        timeframe = "ongoing"
    elif urgency == "WATCH":
        do = f"Reduce {primary} variability and stabilise {secondary} coupling"
        expected = "Coupling normalises within ~10 cycles if corrected early."
        timeframe = "5–10 cycles"
    elif urgency == "ALERT":
        do = f"Stabilise {primary} and recalibrate against {secondary} baseline"
        expected = "Coupling can still be restored — intervention now keeps system reversible."
        timeframe = "5–15 cycles"
    elif urgency == "CRITICAL":
        do = f"Manual recalibration of {primary}/{secondary} required — automatic recovery unlikely"
        expected = "System will settle into a degraded baseline without intervention."
        timeframe = "manual intervention"
    else:
        do = "Review subsystem coupling"
        expected = "—"
        timeframe = "—"

    # IF IGNORED
    if regime == "WARMUP" or urgency == "NOMINAL":
        if_ignored = "No immediate risk."
    elif urgency == "WATCH":
        if_ignored = f"Drift will accelerate. {primary} variance will propagate to {secondary}."
    elif urgency == "ALERT":
        if_ignored = f"Intervention window closes. Continued drift in {primary} risks permanent regime shift."
    elif urgency == "CRITICAL":
        if_ignored = f"System locks into degraded regime. {primary} settles into a new structural baseline."
    else:
        if_ignored = "Instability propagates across all monitored variables."

    # FUTURE PATHS — recovery / degradation / failure
    paths = _future_paths(regime, urgency, drift, velocity, len(rec.variables), primary, secondary, expected)

    return {
        "available": True,
        "system_id": system_id,
        "regime": regime,
        "urgency": urgency,
        "urgency_level": level,
        "operational_risk": risk,
        "what": what,
        "why": why,
        "do": do,
        "expected_effect": expected,
        "action_timeframe": timeframe,
        "if_ignored": if_ignored,
        "drivers": [{"variable": d[0], "variance_ratio": d[1]} for d in drivers],
        "metrics": {
            "instability_score": instability,
            "structural_drift": drift,
            "drift_velocity": velocity,
            "transition_pressure": pressure,
            "confidence": confidence,
        },
        "future_paths": paths,
        "situation_summary": _situation_summary(regime, urgency),
    }


def _future_paths(regime: str, urgency: str, drift: float, velocity: float,
                  n_vars: int, primary: str, secondary: str, expected_effect: str) -> Dict[str, Any]:
    if urgency == "NOMINAL" or regime == "WARMUP":
        return {
            "recovery": {"label": "Nominal", "eta": "current", "action": "All variables operating within normal coupling.",
                         "expected_outcome": "System maintains baseline.", "probability": "current state"},
            "degradation": None,
            "failure": None,
        }
    deg_eta = f"~{int(drift / max(velocity, 1e-3))} cycles" if velocity > 1e-3 else "gradual"
    fail_eta = f"~{int(2 * drift / max(velocity, 1e-3))} cycles" if velocity > 1e-3 else "uncertain"
    return {
        "recovery": {
            "label": "Recovery",
            "eta": "5–15 cycles with corrective action" if regime != "LOCK_IN" else "manual recalibration only",
            "action": f"Reduce {primary} variability, restore coupling with {secondary}.",
            "expected_outcome": expected_effect,
            "probability": "achievable" if regime in ("STABLE", "TRANSITION") else "difficult" if regime == "UNSTABLE" else "low",
        },
        "degradation": {
            "label": "Degradation",
            "eta": deg_eta,
            "action": f"{primary} variance continues compounding; {secondary} loses coupling.",
            "expected_outcome": f"All {n_vars} variables progressively decouple.",
            "probability": "likely without action",
        },
        "failure": {
            "label": "Failure",
            "eta": fail_eta,
            "action": f"Cascading decoupling across all {n_vars} variables.",
            "expected_outcome": "Complete regime failure. System enters uncharted operating territory.",
            "probability": "possible if degradation path is not interrupted",
        },
    }
