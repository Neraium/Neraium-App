"""Decision synthesizer — produces system JUDGMENT, not data status.

The judgment is *state-driven*: the canonical SII regime
(STABLE / TRANSITION / UNSTABLE / LOCK_IN) is the single visible state
and it dictates EVERY operator-facing string. Urgency (NOMINAL / WATCH /
ALERT / CRITICAL) is no longer surfaced — it is merged back into the
state vocabulary so the operator never sees mixed/duplicate labels.

Tone: declarative, decisive. The system understands itself; it does not
present data for the operator to interpret.
"""
from __future__ import annotations
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

from . import sii_state as ss


# ------------------------------------------------------------------
# Domain phrasing — used only for fallbacks where a state-aligned
# phrase is needed without a specific driver.
# ------------------------------------------------------------------
_DOMAIN = {
    "industrial":    "mechanical",
    "environmental": "environmental",
    "generic":       "system",
}


def _domain_word(template: str) -> str:
    return _DOMAIN.get(template, "system")


def _subject(template: str) -> str:
    """The grammatical subject for sentences about this template's system.

    Returns a clean noun phrase that avoids "System system" / "System
    system operating" duplication when the domain itself is "system".
    """
    d = _domain_word(template)
    return "System" if d == "system" else f"{d.capitalize()} system"


def _card_summary(template: str, state: str) -> str:
    """Short contextual line for the System Grid card. ADDS information
    (the system's domain + state in one breath) instead of repeating the
    full top-panel sentence."""
    subj = _subject(template)
    if state == "STABLE":
        return f"{subj} stable"
    if state == "TRANSITION":
        return f"{subj} transitioning"
    if state == "UNSTABLE":
        return f"{subj} unstable"
    if state == "LOCK_IN":
        return f"{subj} locked in"
    return f"{subj} stable"


# ------------------------------------------------------------------
# Variable-name → plain-language label (used in the Variables panel
# tooltip + as a fallback when no semantic phrase is registered).
# ------------------------------------------------------------------
_VAR_PRETTY: Dict[str, str] = {
    "pressure_kpa":  "pressure",
    "temperature_c": "temperature",
    "vibration_g":   "vibration",
    "rpm":           "rotation speed",
    "torque_nm":     "torque",
    "flow_rate_lpm": "flow rate",
    "humidity_rh":   "humidity",
    "co2_ppm":       "CO\u2082 level",
    "airflow_cmh":   "airflow",
    "vpd_kpa":       "vapor pressure",
    "light_par":     "light intensity",
    "var_alpha":     "primary signal",
    "var_beta":      "secondary signal",
    "var_gamma":     "tertiary signal",
    "var_delta":     "quaternary signal",
    "var_epsilon":   "auxiliary signal",
}

_UNIT_SUFFIXES = (
    "_kpa", "_c", "_g", "_ppm", "_cmh", "_lpm", "_rh", "_par", "_nm",
    "_pct", "_psi", "_bar", "_hz", "_v", "_a", "_w", "_kw", "_mv",
)


def _pretty_var(name: Optional[str]) -> str:
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
    return base.replace("_", " ").strip() or "the leading signal"


# ------------------------------------------------------------------
# Semantic driver phrases — replace raw `<var> ×<ratio>` chips.
# Phrases are state-aware so wording always aligns with the regime.
# ------------------------------------------------------------------
def _driver_phrase(name: str, regime: str) -> str:
    """Return a state-aligned, operator-readable phrase for one driver.

    Wording is gated by `regime` so a STABLE system never reads "imbalance
    increasing" and an UNSTABLE one never reads "drift detected".
    """
    key = (name or "").strip().lower()
    # Per-variable templates: (stable_phrase, transition_phrase,
    # unstable_phrase, lockin_phrase). STABLE phrases are kept positive
    # so they fit the "no instability language" rule.
    library: Dict[str, Tuple[str, str, str, str]] = {
        "flow_rate_lpm": (
            "Flow holding within bounds",
            "Flow imbalance increasing",
            "Flow imbalance escalating",
            "Flow regime collapsed",
        ),
        "rpm": (
            "Rotation steady",
            "Rotational instability detected",
            "Rotational instability sustained",
            "Rotational regime broken",
        ),
        "vibration_g": (
            "Vibration steady",
            "Vibration intensifying",
            "Vibration escalating",
            "Vibration locked at degraded level",
        ),
        "torque_nm": (
            "Torque steady",
            "Torque variance expanding",
            "Torque decoupled from baseline",
            "Torque regime collapsed",
        ),
        "pressure_kpa": (
            "Pressure steady",
            "Pressure deviation rising",
            "Pressure decoupled from baseline",
            "Pressure regime broken",
        ),
        "temperature_c": (
            "Temperature steady",
            "Thermal drift detected",
            "Thermal regime breaking down",
            "Thermal regime collapsed",
        ),
        "humidity_rh": (
            "Humidity steady",
            "Humidity drift detected",
            "Humidity regime breaking down",
            "Humidity regime collapsed",
        ),
        "co2_ppm": (
            "CO\u2082 steady",
            "CO\u2082 buildup detected",
            "CO\u2082 buildup escalating",
            "CO\u2082 regime broken",
        ),
        "airflow_cmh": (
            "Airflow steady",
            "Airflow imbalance detected",
            "Airflow imbalance escalating",
            "Airflow regime collapsed",
        ),
        "vpd_kpa": (
            "Vapor pressure steady",
            "Vapor pressure drift detected",
            "Vapor pressure regime breaking",
            "Vapor pressure regime collapsed",
        ),
        "light_par": (
            "Light intensity steady",
            "Light intensity drift detected",
            "Light intensity regime breaking",
            "Light intensity regime collapsed",
        ),
        "var_alpha": (
            "Primary signal steady",
            "Primary signal drift detected",
            "Primary signal decoupled",
            "Primary signal regime collapsed",
        ),
        "var_beta": (
            "Secondary signal steady",
            "Secondary signal drift detected",
            "Secondary signal decoupled",
            "Secondary signal regime collapsed",
        ),
        "var_gamma": (
            "Tertiary signal steady",
            "Tertiary signal drift detected",
            "Tertiary signal decoupled",
            "Tertiary signal regime collapsed",
        ),
        "var_delta": (
            "Quaternary signal steady",
            "Quaternary signal drift detected",
            "Quaternary signal decoupled",
            "Quaternary signal regime collapsed",
        ),
        "var_epsilon": (
            "Auxiliary signal steady",
            "Auxiliary signal drift detected",
            "Auxiliary signal decoupled",
            "Auxiliary signal regime collapsed",
        ),
    }
    idx = {"STABLE": 0, "TRANSITION": 1, "UNSTABLE": 2, "LOCK_IN": 3}.get(regime, 1)
    if key in library:
        return library[key][idx]
    pretty = _pretty_var(name).capitalize()
    return [
        f"{pretty} steady",
        f"{pretty} drift detected",
        f"{pretty} decoupled from baseline",
        f"{pretty} regime collapsed",
    ][idx]


# ------------------------------------------------------------------
# State-driven judgment text. Regime is the single source of truth;
# urgency is intentionally not surfaced.
# ------------------------------------------------------------------
# Constant short-form CONSEQUENCE strings (per spec, locked).
CONSEQUENCE_SHORT = {
    "STABLE":     "No degradation expected",
    "TRANSITION": "Instability will propagate",
    "UNSTABLE":   "System performance degrading",
    "LOCK_IN":    "Failure imminent or occurring",
}

# Long-form CONSEQUENCE strings used in the detail panel.
_CONSEQUENCE_LONG = {
    "STABLE": "No degradation expected — system remains within its operating envelope.",
    "TRANSITION": "Instability will propagate. Coupled variables will follow into divergence.",
    "UNSTABLE": ("System performance degrading. Without intervention, the regime will lock "
                 "into a permanently degraded operating point."),
    "LOCK_IN": ("Failure imminent or occurring. The system has crossed into structural "
                "lock-in and will not self-recover."),
}

# WHAT — primary line, state-aligned. Clean, no duplicate words.
def _what_for(regime: str, template: str, primary_pretty: Optional[str]) -> str:
    subj = _subject(template)
    if regime == "STABLE":
        return f"{subj} operating within stable bounds."
    if regime == "TRANSITION":
        return "Instability emerging."
    if regime == "UNSTABLE":
        return f"{subj} operating outside stable bounds."
    if regime == "LOCK_IN":
        return "Structural lock-in reached."
    return f"{subj} operating within stable bounds."


# WHAT — secondary clarifier line.
def _what_secondary(regime: str, template: str, primary_pretty: Optional[str]) -> str:
    subj = _subject(template)
    if regime == "STABLE":
        return "No structural instability detected."
    if regime == "TRANSITION":
        if primary_pretty:
            return f"System behavior diverging from baseline \u2014 {primary_pretty} leading."
        return "System behavior diverging from baseline."
    if regime == "UNSTABLE":
        if primary_pretty:
            return f"{primary_pretty.capitalize()} decoupled from baseline \u2014 coupling structure broken."
        return f"{subj} coupling structure broken."
    if regime == "LOCK_IN":
        if primary_pretty:
            return f"{primary_pretty.capitalize()} has driven the system into a new regime."
        return f"{subj} has crossed into a new regime."
    return ""


# RISK label — not shown for STABLE.
def _risk_for(regime: str) -> Optional[str]:
    return {
        "STABLE":     None,
        "TRANSITION": "Increasing",
        "UNSTABLE":   "Active",
        "LOCK_IN":    "Realised",
    }.get(regime)


# ACTION (multi-line, decisive). First line = imperative, second = clarifier.
def _action_for(regime: str, template: str, primary_pretty: Optional[str]) -> Tuple[str, str, str]:
    """Returns (action_text, expected_effect, timeframe)."""
    subj = _subject(template)
    target = primary_pretty or "the leading signal"
    if regime == "STABLE":
        return (
            "No intervention required\nSystem stable and operating within expected behavior",
            f"{subj} continues holding baseline coupling.",
            "ongoing",
        )
    if regime == "TRANSITION":
        return (
            f"Intervene now\nStabilise {target} before instability propagates",
            "Coupling restored within ~10 cycles when corrected at this stage.",
            "5\u201310 cycles",
        )
    if regime == "UNSTABLE":
        return (
            f"Intervene immediately\nRecalibrate {target} against baseline",
            "Recovery is still possible. Window closes within 10\u201320 cycles.",
            "5\u201315 cycles",
        )
    if regime == "LOCK_IN":
        return (
            f"Manual recovery only\n{target.capitalize()} requires manual recalibration",
            "System will not self-recover. Operator action is the only path back.",
            "manual intervention",
        )
    return (
        "No intervention required\nSystem stable and operating within expected behavior",
        "System remains stable.",
        "ongoing",
    )


# ------------------------------------------------------------------
# Variance-ratio attribution — same as before, kept for the secondary
# "WHY" line and Variables panel tooltips.
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
# Audit translated headline (used by the Audit Trail row).
# ------------------------------------------------------------------
def audit_headline(kind: str, from_value: Optional[str], to_value: Optional[str]) -> str:
    if kind != "regime":
        # Internal urgency transitions are no longer surfaced; if one
        # leaks into the audit log we collapse it to a generic line.
        return "System judgment refined"
    if to_value == "STABLE":
        return "System recovered \u2014 stable bounds re-established"
    if to_value == "TRANSITION":
        return "Instability emerging \u2014 early transition detected"
    if to_value == "UNSTABLE":
        return "System performance degrading \u2014 instability sustained"
    if to_value == "LOCK_IN":
        return "Failure imminent \u2014 structural lock-in reached"
    if to_value == "WARMUP":
        return "Engine establishing baseline"
    return f"System state changed \u2014 {to_value}"


# ------------------------------------------------------------------
# Public builder
# ------------------------------------------------------------------
def build_decision(system_id: str) -> Dict[str, Any]:
    last = ss.latest_state(system_id)
    rec = ss.get_system(system_id)
    if last is None or rec is None:
        return {"available": False}

    raw_regime = last["regime"]
    # Use the hysteresis-smoothed display_regime when available so the
    # operator-facing state doesn't flap as the engine hovers near a
    # threshold. Fall back to the raw regime, treating WARMUP as STABLE.
    smoothed = last.get("display_regime") or raw_regime
    state = smoothed if smoothed in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN") else "STABLE"

    velocity = float(last["drift_velocity"])
    instability = float(last["instability_score"])
    drift = float(last["structural_drift"])
    pressure = float(last["transition_pressure"])
    confidence = float(last["confidence"])

    drivers = _drivers(system_id, top_k=3)
    primary_raw = drivers[0][0] if drivers else None
    primary_pretty = _pretty_var(primary_raw) if primary_raw else None

    template = rec.template
    domain = _domain_word(template)
    subj = _subject(template)

    # ---------------------- WHAT / ACTION / CONSEQUENCE -----------------
    # In STABLE, drop the driver from secondary text entirely (no
    # instability language).
    primary_for_what = primary_pretty if state != "STABLE" else None
    what = _what_for(state, template, primary_for_what)
    what_secondary = _what_secondary(state, template, primary_for_what)
    action, expected, timeframe = _action_for(state, template, primary_for_what)
    consequence_short = CONSEQUENCE_SHORT[state]
    consequence = _CONSEQUENCE_LONG[state]
    risk = _risk_for(state)
    card_summary = _card_summary(template, state)

    # ---------------------- WHY (secondary) ----------------------------
    if state == "STABLE":
        why = f"Variance broadly stable across {domain} variables. No structural divergence detected."
    elif not drivers:
        why = "Baseline still forming \u2014 driver attribution requires more cycles."
    else:
        leader_name, leader_ratio = drivers[0]
        leader_pretty = _pretty_var(leader_name)
        if leader_ratio > 1.3:
            tail = ""
            if len(drivers) > 1 and drivers[1][1] > 1.15:
                tail = (f" {_pretty_var(drivers[1][0]).capitalize()} is following "
                        f"({drivers[1][1]:.1f}\u00d7 variance).")
            why = (f"{leader_pretty.capitalize()} variance has expanded {leader_ratio:.1f}\u00d7 "
                   f"vs baseline." + tail
                   + f" {subj} coupling structure is breaking down.")
        else:
            why = (f"Variance shifting across {domain} variables ({leader_ratio:.2f}\u00d7 "
                   f"baseline). Drift is structural rather than amplitude-driven.")

    # ---------------------- State-aligned subtext (replaces urgency_window) -
    if state == "STABLE":
        state_subtext = "System holding baseline."
    elif state == "TRANSITION":
        state_subtext = f"Risk increasing. Drift velocity {velocity:.4f}/cycle."
    elif state == "UNSTABLE":
        state_subtext = f"Risk active. Drift velocity {velocity:.4f}/cycle (accelerating)."
    elif state == "LOCK_IN":
        state_subtext = "Risk realised. Manual recovery only."
    else:
        state_subtext = ""

    # ---------------------- Driver phrases (semantic; no raw names) ----
    if state == "STABLE":
        driver_phrases: List[str] = []  # never imply instability when stable
    else:
        # Top-2 drivers as semantic phrases. Variance ratios stay in the
        # `drivers` array (used for tooltips / Variables panel).
        driver_phrases = [_driver_phrase(d[0], state) for d in drivers[:2]]

    paths = _future_paths(state, drift, velocity, len(rec.variables),
                          primary_pretty, expected, domain, subj)

    return {
        "available": True,
        "system_id": system_id,
        # Single canonical state — no urgency surfaced.
        "state": state,
        "regime": state,                       # alias for backwards-compat
        "what": what,
        "what_secondary": what_secondary,
        "risk": risk,                          # None for STABLE
        "card_summary": card_summary,          # short row label
        "action": action,
        "consequence": consequence,            # long form
        "consequence_short": consequence_short,
        "do": action,
        "if_ignored": consequence,
        "expected_effect": expected,
        "action_timeframe": timeframe,
        "state_subtext": state_subtext,
        "why": why,
        # Semantic driver phrases — what the UI should render
        "driver_phrases": driver_phrases,
        # Raw drivers — tooltips / Variables panel ONLY
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
# Future paths — declarative, state-aligned
# ------------------------------------------------------------------
def _future_paths(state: str, drift: float, velocity: float,
                  n_vars: int, primary, expected_effect: str, domain: str,
                  subj: str) -> Dict[str, Any]:
    if state == "STABLE":
        return {
            "recovery": {
                "label": "Hold", "eta": "current",
                "action": f"{subj} continues holding baseline coupling.",
                "expected_outcome": "No action required \u2014 system remains stable.",
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
            "eta": "5\u201315 cycles with corrective action" if state != "LOCK_IN" else "manual recalibration only",
            "action": f"Intervene on {primary_ref}. Coupling re-establishes within the window.",
            "expected_outcome": expected_effect,
            "probability": "achievable" if state == "TRANSITION" else "difficult" if state == "UNSTABLE" else "low",
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
