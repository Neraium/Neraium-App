"""Pydantic request models shared by routers."""
from typing import List, Dict
from pydantic import BaseModel


class ProcessRequest(BaseModel):
    timestamp: float
    asset_id: str = "default"
    sensor_values: Dict[str, float]


class BatchProcessRequest(BaseModel):
    frames: List[ProcessRequest]


class DemoRunRequest(BaseModel):
    num_frames: int = 25
    append: bool = False


class FleetDemoRequest(BaseModel):
    num_frames: int = 80
    asset_count: int = 4


class ResetRequest(BaseModel):
    confirm: bool = True


class AuditEntryRequest(BaseModel):
    asset_id: str
    action_type: str = "ACKNOWLEDGE"  # ACKNOWLEDGE | NOTE | OVERRIDE
    note: str = ""
