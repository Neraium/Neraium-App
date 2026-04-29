"""Demo control endpoints.

GET /api/demo/pronostia  — live time-advancing PRONOSTIA demo
POST /api/demo/reset     — restart the demo timer from cycle 0
GET /api/demo/systems    — list all registered systems (for manual controls)
POST /api/demo/set-state/{system_id} — manually override a system state
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time

from services import sii_state as ss
from services.synthetic_systems import make_system, tick

router = APIRouter(prefix="/demo")

# ---------------------------------------------------------------------------
# Time-based demo — state is computed purely from elapsed time, no SII engine
# ---------------------------------------------------------------------------
_CYCLE_DURATION = 0.3   # seconds per cycle
_MAX_CYCLE = 350        # after this the demo loops back to 0

_TIMELINE: Dict[str, int] = {
    "baseline_finalized": 80,
    "baseline_departure": 80,
    "structural_confirmation": 150,
    "actionable_point": 220,
    "failure_endpoint": _MAX_CYCLE,
}

_STATES = [
    (0,   80,  "STABLE"),
    (80,  150, "TRANSITION"),
    (150, 220, "UNSTABLE"),
    (220, _MAX_CYCLE, "LOCK_IN"),
]

_STATUS = {
    "STABLE":     ("MONITORING",  "nominal",   "BASELINE"),
    "TRANSITION": ("ALERT",       "elevated",  "STRUCTURAL DEPARTURE"),
    "UNSTABLE":   ("ACTIONABLE",  "critical",  "ACCELERATING DEGRADATION"),
    "LOCK_IN":    ("CRITICAL",    "critical",  "LOCKED-IN FAILURE"),
}

_RECOMMENDATION = {
    "STABLE":     "Continue routine monitoring. System operating normally.",
    "TRANSITION": "Investigate and plan intervention before degradation locks in.",
    "UNSTABLE":   "Immediate intervention required. Degradation is accelerating.",
    "LOCK_IN":    "Critical failure imminent. Execute contingency procedures.",
}

# Set at module import — demo advances from when the backend starts
_demo_started_at: float = time.time()


def _current_cycle() -> int:
    elapsed = time.time() - _demo_started_at
    raw = int(elapsed / _CYCLE_DURATION)
    return raw % (_MAX_CYCLE + 1)


def _state_for(cycle: int) -> str:
    for start, end, state in _STATES:
        if start <= cycle < end:
            return state
    return "LOCK_IN"


@router.get("/pronostia")
async def get_pronostia_demo() -> Dict[str, Any]:
    cycle = _current_cycle()
    state = _state_for(cycle)
    status, risk_band, severity = _STATUS[state]

    departure = _TIMELINE["baseline_departure"]
    failure = _TIMELINE["failure_endpoint"]
    actionable = _TIMELINE["actionable_point"]

    time_since_departure = max(0, cycle - departure)
    lead_cycles = max(0, failure - cycle)

    # Velocity and instability increase monotonically with cycle
    if state == "STABLE":
        velocity = 0.001 * cycle
        instability = 0.05 + 0.001 * cycle
        acceleration = 0.0
    elif state == "TRANSITION":
        t = cycle - 80
        velocity = 0.008 + t * 0.0003
        instability = 0.18 + t * 0.004
        acceleration = 0.0001
    elif state == "UNSTABLE":
        t = cycle - 150
        velocity = 0.03 + t * 0.0006
        instability = 0.46 + t * 0.006
        acceleration = 0.00025
    else:  # LOCK_IN
        t = cycle - 220
        velocity = 0.075 + t * 0.0002
        instability = min(0.97, 0.88 + t * 0.001)
        acceleration = -0.00005

    if velocity < 0.01:
        trend = "stable"
    elif velocity < 0.05:
        trend = "linear_or_flat_degradation"
    else:
        trend = "accelerating_degradation"

    trajectory_mode = (
        "early_stage_monitoring" if state == "STABLE" else
        "transition_phase"       if state == "TRANSITION" else
        "late_stage_intervention"
    )

    return {
        "system": "PRONOSTIA Rotating System",
        "dataset": "PRONOSTIA / FEMTO bearing degradation",
        "current_state": state,
        "cycle": cycle,
        "status": status,
        "risk_band": risk_band,
        "severity": severity,
        "departure_confidence": "CONFIRMED" if time_since_departure > 0 else "PENDING",
        "timeline": _TIMELINE,
        "decision": {
            "time_since_departure": time_since_departure,
            "actionable_lead_cycles": lead_cycles,
            "velocity": round(velocity, 6),
            "acceleration": round(acceleration, 7),
            "instability_score": round(instability, 4),
            "trend": trend,
            "trajectory_mode": trajectory_mode,
            "failure_time_estimate": (
                None if state in ("STABLE", "TRANSITION")
                else f"{lead_cycles} cycles"
            ),
            "recommendation": _RECOMMENDATION[state],
        },
        "series": [],
    }


@router.post("/reset")
async def reset_demo() -> Dict[str, Any]:
    """Restart the demo timer from cycle 0."""
    global _demo_started_at
    _demo_started_at = time.time()
    return {"ok": True, "cycle": 0, "state": "STABLE"}


# ---------------------------------------------------------------------------
# Systems list (for manual controls panel)
# ---------------------------------------------------------------------------
_manual_demo_state: Dict[str, Any] = {
    "system_id": None,
    "simulator": None,
    "started_at": None,
}


def _ensure_demo_system() -> str:
    global _manual_demo_state
    demo_id = "__demo_pronostia__"

    if ss.has_system(demo_id):
        return demo_id

    drift_schedule = [
        (80, 70, 0.3),
        (150, 70, 0.7),
        (220, 100, 0.95),
    ]
    sys = make_system(demo_id, template="industrial", seed=42, drift_schedule=drift_schedule)
    ss.register_system(demo_id, "industrial", "PRONOSTIA Rotating System", sys.variables, sys.units)

    for i in range(80):
        vals = tick(sys)
        ss.ingest_frame(demo_id, vals, float(i))

    _manual_demo_state["system_id"] = demo_id
    _manual_demo_state["simulator"] = sys
    _manual_demo_state["started_at"] = time.time()

    return demo_id


@router.get("/systems")
async def list_systems():
    all_recs = ss.all_systems()
    if not all_recs:
        _ensure_demo_system()
        all_recs = ss.all_systems()

    systems = []
    for rec in all_recs:
        latest = rec.history[-1] if rec.history else None
        if latest:
            systems.append({
                "system_id": rec.system_id,
                "label": rec.label,
                "current_state": latest.get("display_regime") or latest.get("regime"),
                "cycle": latest.get("cycle"),
            })
    return {"systems": systems}


# ---------------------------------------------------------------------------
# Manual state override (used by DemoControls panel)
# ---------------------------------------------------------------------------
class SetStateRequest(BaseModel):
    state: str
    cycle: Optional[int] = None
    instability_score: Optional[float] = None
    drift_velocity: Optional[float] = None
    display_regime: Optional[str] = None


@router.post("/set-state/{system_id}")
async def set_state(system_id: str, req: SetStateRequest):
    if req.state not in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN"):
        raise HTTPException(400, f"Invalid state: {req.state}")

    rec = ss.get_system(system_id)
    if rec is None:
        raise HTTPException(404, f"System {system_id} not found")
    if not rec.history:
        raise HTTPException(400, f"No data for {system_id}")

    latest = rec.history[-1].copy()
    latest["regime"] = req.state
    latest["display_regime"] = req.display_regime or req.state

    if req.cycle is not None:
        latest["cycle"] = req.cycle
    if req.instability_score is not None:
        latest["instability_score"] = req.instability_score
    if req.drift_velocity is not None:
        latest["drift_velocity"] = req.drift_velocity

    rec.history[-1] = latest

    return {
        "status": "ok",
        "system_id": system_id,
        "state": latest["display_regime"],
        "cycle": latest.get("cycle"),
        "instability_score": latest.get("instability_score"),
        "drift_velocity": latest.get("drift_velocity"),
        "timestamp": latest.get("timestamp"),
    }
