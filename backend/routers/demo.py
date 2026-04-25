"""Demo control endpoints — manual state manipulation for demos.

POST /api/demo/set-state/{system_id}
  body: {state, cycle, instability_score, drift_velocity}

Allows operator to manually drive system through states for demos.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services import sii_state as ss

router = APIRouter(prefix="/demo")


class SetStateRequest(BaseModel):
    state: str  # STABLE, TRANSITION, UNSTABLE, LOCK_IN
    cycle: Optional[int] = None
    instability_score: Optional[float] = None
    drift_velocity: Optional[float] = None


@router.post("/set-state/{system_id}")
async def set_state(system_id: str, req: SetStateRequest):
    """Manually set system state for demo purposes."""
    if req.state not in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN"):
        raise HTTPException(400, f"Invalid state: {req.state}")

    rec = ss.get_system(system_id)
    if rec is None:
        raise HTTPException(404, f"System {system_id} not found")

    # Get latest state and update it
    if not rec.history:
        raise HTTPException(400, f"No data for {system_id}")

    latest = rec.history[-1].copy()
    latest["regime"] = req.state
    latest["display_regime"] = req.state

    if req.cycle is not None:
        latest["cycle"] = req.cycle
    if req.instability_score is not None:
        latest["instability_score"] = req.instability_score
    if req.drift_velocity is not None:
        latest["drift_velocity"] = req.drift_velocity

    # Replace last state in history
    rec.history[-1] = latest

    return {
        "status": "ok",
        "system_id": system_id,
        "state": req.state,
        "cycle": latest.get("cycle"),
    }


@router.get("/systems")
async def list_systems():
    """List all systems for demo control."""
    systems = []
    for rec in ss.all_systems():
        latest = rec.history[-1] if rec.history else None
        if latest:
            systems.append({
                "system_id": rec.system_id,
                "label": rec.label,
                "current_state": latest.get("display_regime") or latest.get("regime"),
                "cycle": latest.get("cycle"),
            })
    return {"systems": systems}
