"""Customer-facing telemetry ingest endpoint.

`POST /api/ingest/{api_key}` accepts a single sensor frame, registers
the system on first call, and feeds it through the canonical SII
adapter. The response carries the operator-facing display state so
the customer's pipeline can react to verdict changes too.
"""
import time
from typing import Dict, Optional, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import sii_state as ss
from services.synthetic_systems import _TEMPLATES
from . import customers as customers_router

router = APIRouter()


class IngestPayload(BaseModel):
    system_id: str
    template: Optional[str] = None
    variables: Optional[List[str]] = None
    units: Optional[Dict[str, str]] = None
    label: Optional[str] = None
    sensor_values: Dict[str, float]
    timestamp: Optional[float] = None


@router.post("/ingest/{api_key}")
async def ingest(api_key: str, payload: IngestPayload) -> Dict[str, Any]:
    cust = await customers_router.find_by_api_key(api_key)
    if not cust:
        raise HTTPException(401, "invalid api key")

    sid = (payload.system_id or "").strip()
    if not sid:
        raise HTTPException(400, "system_id required")
    if not payload.sensor_values:
        raise HTTPException(400, "sensor_values required")

    newly_registered = False
    if not ss.has_system(sid):
        # First call for this system_id — register it.
        if payload.template and payload.template in _TEMPLATES:
            tpl = _TEMPLATES[payload.template]
            variables = [v[0] for v in tpl["variables"]]
            units = {v[0]: v[3] for v in tpl["variables"]}
            label = tpl["label"]
            template_name = payload.template
        else:
            variables = payload.variables or list(payload.sensor_values.keys())
            units = payload.units or {v: "" for v in variables}
            label = payload.label or f"{cust['name']} · {sid}"
            template_name = "generic"
        ss.register_system(sid, template_name, label, variables, units)
        newly_registered = True

    ts = payload.timestamp if payload.timestamp is not None else time.time()
    try:
        unified = ss.ingest_frame(sid, payload.sensor_values, ts)
    except KeyError as exc:
        raise HTTPException(400, str(exc))

    await customers_router.bump_counters(
        cust["id"],
        systems_delta=1 if newly_registered else 0,
        frames_delta=1,
    )

    return {
        "ok": True,
        "system_id": sid,
        "newly_registered": newly_registered,
        "cycle": unified.get("cycle"),
        "state": unified.get("display_regime") or unified.get("regime"),
    }
