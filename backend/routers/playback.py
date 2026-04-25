"""Live playback control."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from services import playback

router = APIRouter()


class SystemSpec(BaseModel):
    system_id: Optional[str] = None
    template: str = "industrial"
    label: Optional[str] = None
    drift_at: int = 80
    drift_severity: float = 0.85
    drift_duration: int = 240
    seed: Optional[int] = None


class StartRequest(BaseModel):
    speed: str = "normal"
    systems: Optional[List[SystemSpec]] = None


class SpeedRequest(BaseModel):
    speed: str


@router.get("/playback/templates")
async def templates():
    return {"templates": playback.list_templates()}


@router.get("/playback/status")
async def status():
    return playback.status()


@router.post("/playback/start")
async def start(req: StartRequest):
    specs = [s.model_dump() for s in req.systems] if req.systems else None
    return await playback.start(specs=specs, speed=req.speed)


@router.post("/playback/stop")
async def stop():
    return await playback.stop()


@router.post("/playback/speed")
async def speed(req: SpeedRequest):
    return playback.set_speed(req.speed)
