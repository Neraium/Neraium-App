"""Decision synthesizer — produces system JUDGMENT, not data status.

Outputs the locked five-field structure consumed by the UI:
  state, what, risk_level, action, consequence

Plus auxiliary fields (drivers, future_paths, metrics) shown as secondary.

Tone: declarative, decisive. The system understands itself; it does not
present data for the operator to interpret.
"""
from __future__ import annotations
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

from . import sii_state as ss


# ------------------------------------------------------------------
# Domain phrasing — abstract variable names into plain language
# ------------------------------------------------------------------
_DOMAIN = {
    "industrial":    "mechanical",
    "environmental": "environmental",
    "generic":       "system",
}


def _domain_word(template: str) -> str:
    return _DOMAIN.get(template, "system")


# ------------------------------------------------------------------
# Variable-name → plain-language translation (CRITICAL: never let a raw
# snake_case name reach operator-facing judgment text)
# ------------------------------------------------------------------
_VAR_PRETTY: Dict[str, str] = {
    # industrial
    "pressure_kpa":  "pressure",
    "temperature_c": "temperature",
    "vibration_g":   "vibration",
    "rpm":           "rotation speed",
    "torque_nm":     "torque",
    "flow_rate_lpm": "flow rate",
    # environmental
    "humidity_rh":   "humidity",
    "co2_ppm":       "CO\u2082 level",
    "airflow_cmh":   "airflow",
    "vpd_kpa":       "vapor pressure",
    "light_par":     "light intensity",
    # generic abstract signals
    "var_alpha":     "primary signal",
    "var_beta":      "secondary signal",
    "var_gamma":     "tertiary signal",
    "var_delta":     "quaternary signal",
    "var_epsilon":   "auxiliary signal",
}

# Trailing unit suffixes we strip when no explicit mapping exists
_UNIT_SUFFIXES = (
    "_kpa", "_c", "_g", "_ppm", "_cmh", "_lpm", "_rh", "_par", "_nm",
    "_pct", "_psi", "_bar", "_hz", "_v", "_a", "_w", "_kw", "_mv",
)


def _pretty_var(name: Optional[str]) -> str:
    """Return an operator-readable label for a raw variable name.

    Never returns the raw `snake_case` token — falls back to a humanised
    version (snake_case → words, unit suffix stripped) when no explicit
    mapping is registered.
    """
    if not name:
        return "the leading signal"
    key = str(name).strip().lower()
    if key in _VAR_PRETTY:
        return _VAR_PRETTY[key]
    base = key
    for suf in _UNIT_SUFFIXES:
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    base = base.replace("_", " ").strip()
    return base or "the leading signal"


def _stable_what(template: str) -> str:
    d = _domain_word(template)
    return f"{d.capitalize()} conditions stable with no divergence across variables."


def _watch_what(template: str, primary: str) -> str:
    d = _domain_word(template)
    return f"{d.capitalize()} coupling diverging from baseline — {primary} leading the drift."


def _alert_what(template: str, primary: str) -> str:
    d = _domain_word(template)
    return f"{d.capitalize()} coupling broken — {primary} no longer correlated with the rest of the system."


def _critical_what(template: str, primary: str) -> str:
    d = _domain_word(template)
    return f"{d.capitalize()} system approaching irreversible lock-in — {primary} has driven the system into a new regime."


def _warmup_what() -> str:
    return "Engine still establishing baseline — no judgment yet."


# ------------------------------------------------------------------
# Risk + urgency mapping (urgency is internal; risk_level is what the UI shows)
# ------------------------------------------------------------------
URGENCY_RISK   = {"NOMINAL": "LOW",     "WATCH": "MODERATE", "ALERT": "HIGH",     "CRITICAL": "CRITICAL"}
URGENCY_LEVEL  = {"NOMINAL": "low",     "WATCH": "medium",   "ALERT": "high",     "CRITICAL": "critical"}


# ------------------------------------------------------------------
# Variance-ratio attribution (data-driven driver detection)
# ------------------------------------------------------------------
def _drivers(system_id: str, top_k: int = 3) -> List[Tuple[str, float]]:
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


# ------------------------------------------------------------------
# Public builder
# ------------------------------------------------------------------
def build_decision(system_id: str) -> Dict[str, Any]:
    last = ss.latest_state(system_id)
    rec = ss.get_system(system_id)
    if last is None or rec is None:
        return {"available": False}

    regime = last["regime"]
    urgency = last["urgency"]
    risk_level = URGENCY_RISK.get(urgency, "LOW")
    level = URGENCY_LEVEL.get(urgency, "low")

    velocity = float(last["drift_velocity"])
    instability = float(last["instability_score"])
    drift = float(last["structural_drift"])
    pressure = float(last["transition_pressure"])
    confidence = float(last["confidence"])

    drivers = _drivers(system_id, top_k=3)
    primary_raw = drivers[0][0] if drivers else None
    primary = _pretty_var(primary_raw)

    template = rec.template
    domain = _domain_word(template)

    # ---------------------- WHAT (plain-language summary) ----------------------
    if regime == "WARMUP":
        what = _warmup_what()
    elif urgency == "NOMINAL":
        what = _stable_what(template)
    elif urgency == "WATCH":
        what = _watch_what(template, primary)
    elif urgency == "ALERT" and regime != "LOCK_IN":
        what = _alert_what(template, primary)
    elif urgency == "CRITICAL" or regime == "LOCK_IN":
        what = _critical_what(template, primary)
    else:
        what = _stable_what(template)

    # ---------------------- ACTION (declarative) ----------------------
    if regime == "WARMUP":
        action = "No intervention required \u2014 engine is establishing baseline"
        expected = "Decisions resume automatically once the baseline window is locked."
        timeframe = "automatic"
    elif urgency == "NOMINAL":
        action = "No intervention required \u2014 system stable"
        expected = "System will continue holding baseline coupling."
        timeframe = "ongoing"
    elif urgency == "WATCH":
        action = f"Stabilise {primary} before drift propagates"
        expected = "Coupling restored within ~10 cycles when corrected at this stage."
        timeframe = "5\u201310 cycles"
    elif urgency == "ALERT":
        action = f"Intervene on {primary} immediately \u2014 recalibrate against baseline"
        expected = "Recovery is still possible. Window closes within 10\u201320 cycles."
        timeframe = "5\u201315 cycles"
    elif urgency == "CRITICAL":
        action = f"Manual recalibration required \u2014 automatic recovery has been ruled out for {primary}"
        expected = "System will not self-recover. Operator action is the only path back to baseline."
        timeframe = "manual intervention"
    else:
        action = "Review system coupling"
        expected = "\u2014"
        timeframe = "\u2014"

    # ---------------------- CONSEQUENCE (decisive) ----------------------
    if regime == "WARMUP" or urgency == "NOMINAL":
        consequence = "No risk \u2014 system remains within its operating envelope."
    elif urgency == "WATCH":
        consequence = (f"Drift will compound. {primary.capitalize()} variance will propagate to coupled "
                       f"variables and force the system into ALERT.")
    elif urgency == "ALERT":
        consequence = (f"Intervention window closes. The system will lock into a degraded regime where "
                       f"{primary} is permanently decoupled from baseline.")
    elif urgency == "CRITICAL":
        consequence = ("The system has already crossed into structural lock-in. Without manual recalibration "
                       "it will settle into a permanently degraded operating point.")
    else:
        consequence = "Instability will propagate across all monitored variables."

    # ---------------------- WHY (kept for the secondary panel) ----------------------
    if not drivers:
        why = "Baseline still forming \u2014 driver attribution requires more cycles."
    else:
        leader_name, leader_ratio = drivers[0]
        leader_pretty = _pretty_var(leader_name)
        if leader_ratio > 1.3:
            tail = ""
            if len(drivers) > 1 and drivers[1][1] > 1.15:
                tail = f" {_pretty_var(drivers[1][0]).capitalize()} is following ({drivers[1][1]:.1f}\u00d7 variance)."
            why = (f"{leader_pretty.capitalize()} variance has expanded {leader_ratio:.1f}\u00d7 vs baseline." + tail
                   + f" {domain.capitalize()} coupling structure is breaking down.")
        else:
            why = (f"Variance broadly stable across {domain} variables ({leader_ratio:.2f}\u00d7 baseline). "
                   "Drift is structural rather than amplitude-driven.")

    # ---------------------- URGENCY summary (subtext for risk field) ----------------------
    if urgency == "NOMINAL" or regime == "WARMUP":
        urgency_window = "No window — system is calm."
    elif urgency == "WATCH":
        urgency_window = f"Drift developing. Velocity {velocity:.4f}/cycle."
    elif urgency == "ALERT":
        urgency_window = f"Active. Velocity {velocity:.4f}/cycle (accelerating)."
    elif urgency == "CRITICAL":
        urgency_window = "Window closed. Manual recovery only."
    else:
        urgency_window = ""

    paths = _future_paths(regime, urgency, drift, velocity, len(rec.variables), primary, drivers, expected, domain)

    return {
        "available": True,
        "system_id": system_id,
        # 5-field structured judgment
        "state": regime,                        # canonical SII regime
        "what": what,                           # plain-language summary
        "risk_level": risk_level,               # LOW / MODERATE / HIGH / CRITICAL
        "action": action,                       # declarative imperative
        "consequence": consequence,             # decisive consequence
        # 5-field aux (kept for backwards-compat: do/if_ignored mirror action/consequence)
        "do": action,
        "if_ignored": consequence,
        "expected_effect": expected,
        "action_timeframe": timeframe,
        "urgency": urgency,
        "urgency_level": level,
        "urgency_window": urgency_window,
        "operational_risk": risk_level,
        "regime": regime,
        "why": why,
        "drivers": [{"variable": d[0], "variance_ratio": d[1]} for d in drivers],
        "metrics": {
            "instability_score": instability,
            "structural_drift": drift,
            "drift_velocity": velocity,
            "transition_pressure": pressure,
            "confidence": confidence,
            "lead_time_cycles": last.get("lead_time_cycles"),
        },
        "future_paths": paths,
    }


# ------------------------------------------------------------------
# Future paths — declarative, domain-aware
# ------------------------------------------------------------------
def _future_paths(regime: str, urgency: str, drift: float, velocity: float,
                  n_vars: int, primary, drivers, expected_effect: str, domain: str) -> Dict[str, Any]:
    if urgency == "NOMINAL" or regime == "WARMUP":
        return {
            "recovery": {
                "label": "Hold", "eta": "current",
                "action": f"{domain.capitalize()} system continues holding baseline coupling.",
                "expected_outcome": "No action required — system remains stable.",
                "probability": "current state",
            },
            "degradation": None,
            "failure": None,
        }
    deg_eta  = f"~{int(drift / max(velocity, 1e-3))} cycles" if velocity > 1e-3 else "gradual"
    fail_eta = f"~{int(2 * drift / max(velocity, 1e-3))} cycles" if velocity > 1e-3 else "uncertain"
    primary_ref = primary or "the leading signal"
    return {
        "recovery": {
            "label": "Recovery",
            "eta": "5–15 cycles with corrective action" if regime != "LOCK_IN" else "manual recalibration only",
            "action": f"Intervene on {primary_ref}. Coupling re-establishes within the window.",
            "expected_outcome": expected_effect,
            "probability": "achievable" if regime in ("STABLE", "TRANSITION") else "difficult" if regime == "UNSTABLE" else "low",
        },
        "degradation": {
            "label": "Degradation",
            "eta": deg_eta,
            "action": f"{primary_ref.capitalize()} keeps drifting. Coupled variables compensate, then decouple.",
            "expected_outcome": f"All {n_vars} {domain} variables progressively lose coupling.",
            "probability": "likely without action",
        },
        "failure": {
            "label": "Failure",
            "eta": fail_eta,
            "action": f"Cascading decoupling across all {n_vars} {domain} variables.",
            "expected_outcome": "Complete regime failure. System enters uncharted operating territory.",
            "probability": "possible if degradation path is not interrupted",
        },
    }
