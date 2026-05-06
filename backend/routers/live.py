"""Live PRONOSTIA/FEMTO telemetry ingestion endpoints."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import live_pronostia_ingestion


router = APIRouter(prefix="/live")


class LiveTelemetryPacket(BaseModel):
    timestamp: str
    asset_id: str
    cycle: int
    signals: Dict[str, float]


@router.post("/ingest")
async def ingest_live(packet: LiveTelemetryPacket) -> Dict[str, object]:
    try:
        payload = packet.model_dump() if hasattr(packet, "model_dump") else packet.dict()
        return live_pronostia_ingestion.ingest_packet(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reset/{asset_id}")
async def reset_live(asset_id: str) -> Dict[str, str]:
    live_pronostia_ingestion.reset_asset(asset_id)
    return {"status": "ok", "asset_id": asset_id}
