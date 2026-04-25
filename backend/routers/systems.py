"""System-level read/write routes."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import sii_state as ss
from services.serialise import sf
from services.decision_synth import build_decision

router = APIRouter()


class ProcessFrameRequest(BaseModel):
    timestamp: float
    sensor_values: Dict[str, float]


class RegisterSystemRequest(BaseModel):
    system_id: str
    template: str = "generic"
    label: Optional[str] = None
    variable_names: Optional[List[str]] = None  # only used if template=='generic-custom'


@router.get("/systems")
async def list_systems():
    """Return all systems with their latest unified state — for the System Grid."""
    out: List[Dict[str, Any]] = []
    for rec in ss.all_systems():
        latest = rec.history[-1] if rec.history else None
        out.append({
            "system_id": rec.system_id,
            "template": rec.template,
            "label": rec.label,
            "variables": rec.variables,
            "units": rec.units,
            "frame_count": len(rec.history),
            "created_at": rec.created_at,
            "latest": sf(latest) if latest else None,
        })
    return {"count": len(out), "systems": out}


@router.get("/systems/{system_id}")
async def get_system(system_id: str):
    rec = ss.get_system(system_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="System not found")
    return {
        "system_id": rec.system_id,
        "template": rec.template,
        "label": rec.label,
        "variables": rec.variables,
        "units": rec.units,
        "frame_count": len(rec.history),
        "latest": sf(rec.history[-1]) if rec.history else None,
        "latest_sensors": ss.latest_sensors(system_id),
    }


@router.get("/systems/{system_id}/state")
async def latest_state(system_id: str):
    s = ss.latest_state(system_id)
    if s is None:
        raise HTTPException(status_code=404, detail="No data for system")
    return sf(s)


@router.get("/systems/{system_id}/history")
async def history(system_id: str, limit: int = 200):
    return sf({"system_id": system_id, "history": ss.history(system_id, limit=limit)})


@router.get("/systems/{system_id}/decision")
async def decision(system_id: str):
    return sf(build_decision(system_id))


@router.post("/systems/{system_id}/ingest")
async def ingest(system_id: str, req: ProcessFrameRequest):
    """Manual frame ingest — useful for connecting an external feed."""
    if not ss.has_system(system_id):
        raise HTTPException(status_code=404, detail="System not registered")
    return sf(ss.ingest_frame(system_id, req.sensor_values, req.timestamp))


@router.post("/systems/register")
async def register(req: RegisterSystemRequest):
    """Register a system without starting playback. Used by external integrations."""
    from services.synthetic_systems import _TEMPLATES
    if req.template not in _TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown template: {req.template}")
    tpl = _TEMPLATES[req.template]
    variables = [v[0] for v in tpl["variables"]]
    units = {v[0]: v[3] for v in tpl["variables"]}
    rec = ss.register_system(
        system_id=req.system_id, template=req.template,
        label=req.label or f"{tpl['label']} {req.system_id}",
        variables=variables, units=units,
    )
    return {"status": "ok", "system_id": rec.system_id, "variables": rec.variables, "template": rec.template}


@router.delete("/systems/{system_id}")
async def delete_system(system_id: str):
    ss.reset_system(system_id)
    return {"status": "ok"}
