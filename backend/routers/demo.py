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

from services import sii_state as ss
from services.synthetic_systems import make_system, tick

router = APIRouter(prefix="/demo")


class SetStateRequest(BaseModel):
    state: str  # STABLE, TRANSITION, UNSTABLE, LOCK_IN
    cycle: Optional[int] = None
    instability_score: Optional[float] = None
    drift_velocity: Optional[float] = None
    display_regime: Optional[str] = None


def _ensure_demo_system() -> str:
    """Ensure at least one synthetic demo system exists. Returns system_id."""
    demo_id = "__demo_pronostia__"
    if ss.has_system(demo_id):
        return demo_id

    sys = make_system(demo_id, template="industrial", seed=42)
    ss.register_system(demo_id, "industrial", "PRONOSTIA Rotating System", sys.variables, sys.units)

    for _ in range(80):
        vals = tick(sys)
        ss.ingest_frame(demo_id, vals, float(_))

    return demo_id


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
    """Clean operator-facing PRONOSTIA demo data."""
    demo_id = _ensure_demo_system()
    rec = ss.get_system(demo_id)

    if not rec or not rec.history:
        raise HTTPException(500, "Failed to initialize demo system")

    latest = rec.history[-1]

    return {
        "system": "PRONOSTIA Rotating System",
        "dataset": "PRONOSTIA / FEMTO bearing degradation",
        "status": "ACTIONABLE",
        "risk_band": "elevated",
        "severity": "FAST DEGRADATION",
        "departure_confidence": "LOW",
        "timeline": {
            "baseline_finalized": 51,
            "baseline_departure": 94,
            "structural_confirmation": 94,
            "actionable_point": 114,
            "failure_endpoint": 2802,
        },
        "decision": {
            "time_since_departure": 20,
            "actionable_lead_cycles": 2688,
            "trend": "linear_or_flat_degradation",
            "trajectory_mode": "early_stage_monitoring",
            "velocity": latest.get("drift_velocity", 0.0101),
            "acceleration": -0.000014,
            "failure_time_estimate": None,
            "recommendation": "Investigate and plan intervention before degradation locks in.",
        },
        "current_state": latest.get("display_regime", "STABLE"),
        "cycle": latest.get("cycle", 0),
        "series": [],
    }
