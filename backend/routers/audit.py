"""Operator audit log — persists state transitions and operator notes to MongoDB."""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from routers.models import AuditEntryRequest

router = APIRouter()

_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME")
_client: Optional[AsyncIOMotorClient] = None


def _coll():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(_mongo_url)
    return _client[_db_name]["audit_log"]


_last_state: Dict[str, str] = {}


def reset_transition_tracker() -> None:
    _last_state.clear()


async def scan_and_log(asset_id: str, build_decision_fn) -> int:
    """Scan engine results for asset_id and log new urgency transitions.

    Tracks legacy `state` field (STABLE/WATCH/ALERT) since the UI uses that;
    the `urgency` change is captured in operational_risk on each entry.
    """
    from services import engine_service as es
    results = es.get_results(asset_id)
    logged = 0
    for raw in results:
        state = raw.get("state", "STABLE")
        prev = _last_state.get(asset_id)
        if prev == state:
            continue
        _last_state[asset_id] = state
        if prev is None and state == "STABLE":
            continue
        try:
            decision = build_decision_fn(raw)
        except Exception:
            decision = {}
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_id": asset_id,
            "frame_index": raw.get("_index"),
            "from_state": prev,
            "to_state": state,
            "action_type": "STATE_TRANSITION",
            "operational_risk": decision.get("risk_level"),
            "now_text": decision.get("now"),
            "do_this": decision.get("do_this"),
            "if_ignored": decision.get("if_ignored"),
            "operator_note": "",
        }
        try:
            await _coll().insert_one(dict(entry))
            logged += 1
        except Exception:
            pass
    return logged


@router.post("/audit")
async def add_audit(req: AuditEntryRequest):
    if req.action_type not in ("ACKNOWLEDGE", "NOTE", "OVERRIDE"):
        raise HTTPException(status_code=400, detail="Invalid action_type")
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": req.asset_id,
        "frame_index": None,
        "from_state": None,
        "to_state": None,
        "action_type": req.action_type,
        "operational_risk": None,
        "now_text": None,
        "do_this": None,
        "if_ignored": None,
        "operator_note": req.note,
    }
    await _coll().insert_one(dict(entry))
    return entry


@router.get("/audit")
async def list_audit(asset_id: str = "", limit: int = 100):
    q: Dict[str, Any] = {}
    if asset_id:
        q["asset_id"] = asset_id
    cursor = _coll().find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    return {"count": len(items), "items": items}


@router.delete("/audit")
async def clear_audit(asset_id: str = ""):
    q: Dict[str, Any] = {}
    if asset_id:
        q["asset_id"] = asset_id
    res = await _coll().delete_many(q)
    return {"deleted": res.deleted_count}
