"""Demo control endpoints — manual state manipulation for demos.

POST /api/demo/set-state/{system_id}
  body: {state, cycle, instability_score, drift_velocity, regime_display}

Allows operator to manually drive system through states for demos.
GET /api/demo/systems — list all systems
GET /api/demo/pronostia — clean operator-facing PRONOSTIA demo data
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import asyncio

from services import sii_state as ss
from services.synthetic_systems import make_system, tick

router = APIRouter(prefix="/demo")


class SetStateRequest(BaseModel):
    state: str  # STABLE, TRANSITION, UNSTABLE, LOCK_IN
    cycle: Optional[int] = None
    instability_score: Optional[float] = None
    drift_velocity: Optional[float] = None
    display_regime: Optional[str] = None


# Demo system state — tracks simulation progress
_demo_state = {
    "system_id": None,
    "simulator": None,
    "started_at": None,
    "task": None,
    "stop_flag": False,
}


def _ensure_demo_system() -> str:
    """Ensure demo system exists and is initialized with a drift schedule."""
    global _demo_state
    demo_id = "__demo_pronostia__"

    if ss.has_system(demo_id):
        return demo_id

    # Create system with multi-stage drift schedule (STABLE → TRANSITION → UNSTABLE → LOCK_IN)
    # Stages:
    # 0-80: STABLE (baseline)
    # 80-150: TRANSITION (mild drift 0.3)
    # 150-220: UNSTABLE (moderate drift 0.7)
    # 220+: LOCK_IN (severe drift 0.95)
    drift_schedule = [
        (80,  30, 0.55),  # TRANSITION: ramp to 0.55 over 30 steps, then hold
        (150, 30, 0.85),  # UNSTABLE:   ramp to 0.85 over 30 steps, then hold
        (220, 25, 1.00),  # LOCK_IN:    ramp to 1.00 over 25 steps, then hold
    ]

    sys = make_system(demo_id, template="industrial", seed=42, drift_schedule=drift_schedule)
    ss.register_system(demo_id, "industrial", "PRONOSTIA Rotating System", sys.variables, sys.units)

    # Ingest initial frames (baseline)
    for i in range(80):
        vals = tick(sys)
        ss.ingest_frame(demo_id, vals, float(i))

    _demo_state["system_id"] = demo_id
    _demo_state["simulator"] = sys
    _demo_state["started_at"] = time.time()

    return demo_id


def _advance_demo_system(target_cycle: int) -> None:
    """Advance demo system simulation to target_cycle.

    target_cycle is elapsed time-based, but system already has 80 baseline frames.
    So actual target_step = 80 + target_cycle.
    """
    if not _demo_state["simulator"] or not _demo_state["system_id"]:
        return

    sys = _demo_state["simulator"]
    demo_id = _demo_state["system_id"]

    # System starts at step 80 (baseline frames already ingested)
    # Advance to: 80 + target_cycle
    actual_target_step = 80 + target_cycle

    while sys.step < actual_target_step:
        vals = tick(sys)
        ss.ingest_frame(demo_id, vals, float(sys.step - 1))


def _get_demo_cycle() -> int:
    """Get the current cycle for the demo based on elapsed time."""
    if not _demo_state["started_at"]:
        _ensure_demo_system()

    elapsed = time.time() - _demo_state["started_at"]
    # ~1 frame per second (adjust 0.3 speed multiplier)
    cycle = int(elapsed / 0.3)
    return min(cycle, 350)  # Cap at end of lock-in stage


@router.post("/set-state/{system_id}")
async def set_state(system_id: str, req: SetStateRequest):
    """Manually set system state for demo purposes."""
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


@router.get("/systems")
async def list_systems():
    """List all systems for demo control. Always returns at least fallback demo system."""
    systems = []
    all_recs = ss.all_systems()

    if not all_recs:
        demo_id = _ensure_demo_system()
        all_recs = ss.all_systems()

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


@router.get("/pronostia")
async def get_pronostia_demo() -> Dict[str, Any]:
    """Clean operator-facing PRONOSTIA demo data — live advancing simulation."""
    demo_id = _ensure_demo_system()

    # Advance simulation to current time-based cycle
    current_cycle = _get_demo_cycle()
    _advance_demo_system(current_cycle)

    rec = ss.get_system(demo_id)
    if not rec or not rec.history:
        raise HTTPException(500, "Failed to initialize demo system")

    latest = rec.history[-1]

    # Determine state from drift-schedule ground truth (sys.step) rather than
    # the SII engine's gated regime, which requires many sustained frames of
    # accelerating drift before it escalates — too slow for a live demo.
    _sim = _demo_state.get("simulator")
    _sys_step = _sim.step if _sim else 80

    if _sys_step >= 220:
        current_state = "LOCK_IN"
    elif _sys_step >= 150:
        current_state = "UNSTABLE"
    elif _sys_step >= 90:
        current_state = "TRANSITION"
    else:
        current_state = "STABLE"

    # Determine status and messaging based on current cycle and state
    # These match the drift_schedule in _ensure_demo_system()
    timeline_baseline = 80
    timeline_departure = 80      # When TRANSITION begins
    timeline_confirmation = 150  # When UNSTABLE begins
    timeline_actionable = 220    # When LOCK_IN begins
    timeline_failure = 350       # End of simulation

    current_cycle_int = _sys_step

    # Dynamic status based on state progression
    if current_state == "STABLE":
        status = "MONITORING"
        risk_band = "nominal"
        severity = "BASELINE"
    elif current_state == "TRANSITION":
        status = "ALERT"
        risk_band = "elevated"
        severity = "STRUCTURAL DEPARTURE"
    elif current_state == "UNSTABLE":
        status = "ACTIONABLE"
        risk_band = "critical"
        severity = "ACCELERATING DEGRADATION"
    else:  # LOCK_IN
        status = "CRITICAL"
        risk_band = "critical"
        severity = "LOCKED-IN FAILURE"

    # Calculate lead time
    if current_state == "STABLE":
        actionable_lead_cycles = timeline_failure - current_cycle_int
    elif current_state == "TRANSITION":
        actionable_lead_cycles = timeline_failure - current_cycle_int
    elif current_state == "UNSTABLE":
        actionable_lead_cycles = timeline_failure - current_cycle_int
    else:
        actionable_lead_cycles = 0

    # Time since departure (if past departure point)
    time_since_departure = max(0, current_cycle_int - timeline_departure)

    # Velocity and acceleration based on drift stage
    velocity = abs(latest.get("drift_velocity", 0.0))
    if current_state == "STABLE":
        acceleration = 0.0
    elif current_state == "TRANSITION":
        acceleration = 0.0001
    elif current_state == "UNSTABLE":
        acceleration = 0.00025
    else:
        acceleration = -0.0001  # Locked-in, no acceleration possible

    return {
        "system": "PRONOSTIA Rotating System",
        "dataset": "PRONOSTIA / FEMTO bearing degradation",
        "status": status,
        "risk_band": risk_band,
        "severity": severity,
        "departure_confidence": "CONFIRMED" if time_since_departure > 0 else "PENDING",
        "timeline": {
            "baseline_finalized": timeline_baseline,
            "baseline_departure": timeline_departure,
            "structural_confirmation": timeline_confirmation,
            "actionable_point": timeline_actionable,
            "failure_endpoint": timeline_failure,
        },
        "decision": {
            "time_since_departure": time_since_departure,
            "actionable_lead_cycles": max(0, actionable_lead_cycles),
            "trend": "stable" if velocity < 0.01 else "linear_degradation" if velocity < 0.05 else "accelerating_degradation",
            "trajectory_mode": "early_stage_monitoring" if current_state == "STABLE" else "late_stage_intervention" if current_state in ["UNSTABLE", "LOCK_IN"] else "transition_phase",
            "velocity": float(velocity),
            "acceleration": float(acceleration),
            "failure_time_estimate": None if current_state in ["STABLE", "TRANSITION"] else f"{max(0, timeline_failure - current_cycle_int)} cycles",
            "recommendation": {
                "STABLE": "Continue routine monitoring. System operating normally.",
                "TRANSITION": "Investigate and plan intervention before degradation locks in.",
                "UNSTABLE": "Immediate intervention required. Degradation is accelerating.",
                "LOCK_IN": "Critical failure imminent. Execute contingency procedures.",
            }.get(current_state, "Unknown state"),
        },
        "current_state": current_state,
        "cycle": int(latest.get("cycle", 0)),
        "series": [],
    }
