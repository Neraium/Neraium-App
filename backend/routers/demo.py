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
import logging

from services import sii_state as ss
from services.synthetic_systems import make_system, tick

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo")

OVERRIDE_TTL = 60.0  # seconds a manual override suppresses simulation advance


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

# Manual override — when active, _advance_demo_system is skipped and
# get_pronostia_demo uses these values directly so set-state is reflected
# immediately in the UI without being overwritten by the next simulation tick.
_manual_override: Dict[str, Any] = {
    "active": False,
    "state": "STABLE",
    "cycle": 0,
    "instability_score": 0.0,
    "drift_velocity": 0.0,
    "display_regime": "STABLE",
    "expires_at": 0.0,
}


def _override_active() -> bool:
    return _manual_override["active"] and time.time() < _manual_override["expires_at"]


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
        (80, 70, 0.3),       # Transition: cycles 80-150, mild drift
        (150, 70, 0.7),      # Unstable: cycles 150-220, moderate drift
        (220, 100, 0.95),    # Lock-in: cycles 220+, severe drift
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
    Skipped while a manual override is active so set-state changes persist.
    """
    if _override_active():
        return
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

    # Freeze simulation so this override persists across the next /pronostia polls
    if system_id == "__demo_pronostia__":
        _manual_override.update({
            "active": True,
            "state": req.state,
            "cycle": latest.get("cycle", 0),
            "instability_score": latest.get("instability_score", 0.0),
            "drift_velocity": latest.get("drift_velocity", 0.0),
            "display_regime": latest["display_regime"],
            "expires_at": time.time() + OVERRIDE_TTL,
        })
        logger.info(
            "Demo override active: state=%s cycle=%s expires_in=%.0fs",
            req.state, latest.get("cycle"), OVERRIDE_TTL,
        )

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
            # When a manual override is active for the demo system, surface it
            if rec.system_id == "__demo_pronostia__" and _override_active():
                current_state = _manual_override["display_regime"]
                cycle = _manual_override["cycle"]
            else:
                current_state = latest.get("display_regime") or latest.get("regime")
                cycle = latest.get("cycle")
            systems.append({
                "system_id": rec.system_id,
                "label": rec.label,
                "current_state": current_state,
                "cycle": cycle,
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

    # If a manual override is active, use its state so the UI reflects set-state immediately
    if _override_active():
        current_state = _manual_override["display_regime"]
        # Patch latest so downstream metric reads (velocity, cycle) use override values
        latest = dict(latest)
        latest["display_regime"] = current_state
        latest["regime"] = current_state
        if _manual_override["instability_score"] is not None:
            latest["instability_score"] = _manual_override["instability_score"]
        if _manual_override["drift_velocity"] is not None:
            latest["drift_velocity"] = _manual_override["drift_velocity"]
        if _manual_override["cycle"] is not None:
            latest["cycle"] = _manual_override["cycle"]
    else:
        _manual_override["active"] = False  # TTL expired — reset flag
        current_state = latest.get("display_regime", latest.get("regime", "STABLE"))

    # Determine status and messaging based on current cycle and state
    # These match the drift_schedule in _ensure_demo_system()
    timeline_baseline = 80
    timeline_departure = 80      # When TRANSITION begins
    timeline_confirmation = 150  # When UNSTABLE begins
    timeline_actionable = 220    # When LOCK_IN begins
    timeline_failure = 350       # End of simulation

    current_cycle_int = int(latest.get("cycle", 0))

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
