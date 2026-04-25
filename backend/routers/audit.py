"""Operator audit log — auto-logs every regime+urgency transition and accepts manual entries."""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

from services import sii_state as ss

router = APIRouter()

_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME")
_client: Optional[AsyncIOMotorClient] = None


def _coll():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(_mongo_url)
    return _client[_db_name]["audit_log"]


# (system_id, "regime"|"urgency") -> last value seen
_last_seen: Dict[tuple, str] = {}


def reset_tracker() -> None:
    _last_seen.clear()


async def scan_and_log() -> int:
    """Scan history of every system, emit one entry per regime/urgency transition."""
    logged = 0
    for rec in ss.all_systems():
        for unified in rec.history:
            sid = rec.system_id
            for kind, key in (("regime", "regime"), ("urgency", "urgency")):
                cur = unified.get(key)
                prev = _last_seen.get((sid, kind))
                if prev == cur:
                    continue
                _last_seen[(sid, kind)] = cur
                if prev is None:
                    # don't emit the very first observed value — it's the baseline
                    continue
                entry = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "system_id": sid,
                    "system_label": rec.label,
                    "kind": kind,           # "regime" or "urgency"
                    "from_value": prev,
                    "to_value": cur,
                    "frame_index": unified.get("cycle"),
                    "instability_score": float(unified.get("instability_score") or 0),
                    "drift_velocity": float(unified.get("drift_velocity") or 0),
                    "action_type": "AUTO_TRANSITION",
                    "operator_note": "",
                }
                try:
                    await _coll().insert_one(dict(entry))
                    logged += 1
                except Exception:
                    pass
    return logged


class AuditEntryRequest(BaseModel):
    system_id: str
    action_type: str = "ACKNOWLEDGE"  # ACKNOWLEDGE | NOTE | OVERRIDE
    note: str = ""


@router.post("/audit")
async def add(req: AuditEntryRequest):
    if req.action_type not in ("ACKNOWLEDGE", "NOTE", "OVERRIDE"):
        raise HTTPException(status_code=400, detail="Invalid action_type")
    rec = ss.get_system(req.system_id)
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system_id": req.system_id,
        "system_label": rec.label if rec else None,
        "kind": "operator",
        "from_value": None, "to_value": None,
        "frame_index": None,
        "instability_score": None, "drift_velocity": None,
        "action_type": req.action_type,
        "operator_note": req.note,
    }
    await _coll().insert_one(dict(entry))
    return entry


@router.get("/audit")
async def list_(system_id: str = "", limit: int = 100):
    q: Dict[str, Any] = {}
    if system_id:
        q["system_id"] = system_id
    cursor = _coll().find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    return {"count": len(items), "items": items}


@router.delete("/audit")
async def clear(system_id: str = ""):
    q: Dict[str, Any] = {}
    if system_id:
        q["system_id"] = system_id
    res = await _coll().delete_many(q)
    return {"deleted": res.deleted_count}
