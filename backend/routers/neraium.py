"""Canonical Neraium decision engine API."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.neraium_engine import get_engine


router = APIRouter(prefix="/neraium")


class NeraiumPacket(BaseModel):
    timestamp: str
    asset_id: str
    cycle: int
    signals: Dict[str, float]


@router.post("/ingest")
async def ingest(packet: NeraiumPacket) -> Dict[str, object]:
    payload = packet.model_dump() if hasattr(packet, "model_dump") else packet.dict()
    try:
        return get_engine().update(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/state/{asset_id}")
async def state(asset_id: str) -> Dict[str, object]:
    return get_engine().get_state(asset_id)
