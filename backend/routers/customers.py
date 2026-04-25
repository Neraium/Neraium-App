"""Customer accounts + API-key management.

Each customer represents an external organisation that pushes telemetry
into the SII platform. Creating a customer mints a unique API key that
is then used as the path component of `POST /api/ingest/{api_key}`.

Storage: MongoDB collection `customers`. JSON-serialisable; never returns
Mongo `_id`.
"""
import os
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter()

_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME")
_client: Optional[AsyncIOMotorClient] = None


def _coll():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(_mongo_url)
    return _client[_db_name]["customers"]


class CreateCustomer(BaseModel):
    name: str
    email: Optional[str] = ""
    source_url: Optional[str] = ""    # informational; not yet polled
    notes: Optional[str] = ""


@router.post("/customers")
async def create(req: CreateCustomer) -> Dict[str, Any]:
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    customer = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": (req.email or "").strip(),
        "source_url": (req.source_url or "").strip(),
        "notes": (req.notes or "").strip(),
        "api_key": "nrm_" + secrets.token_urlsafe(24),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "systems_registered": 0,
        "frames_ingested": 0,
    }
    await _coll().insert_one(dict(customer))
    return customer


@router.get("/customers")
async def list_() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = await _coll().find({}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    return {"count": len(items), "items": items}


@router.delete("/customers/{cust_id}")
async def delete_(cust_id: str) -> Dict[str, Any]:
    res = await _coll().delete_one({"id": cust_id})
    return {"deleted": res.deleted_count}


# Internal helper for the ingest router
async def find_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    return await _coll().find_one({"api_key": api_key}, {"_id": 0})


async def bump_counters(cust_id: str, *, systems_delta: int = 0, frames_delta: int = 0) -> None:
    inc: Dict[str, int] = {}
    if systems_delta:
        inc["systems_registered"] = systems_delta
    if frames_delta:
        inc["frames_ingested"] = frames_delta
    if inc:
        await _coll().update_one({"id": cust_id}, {"$inc": inc})
