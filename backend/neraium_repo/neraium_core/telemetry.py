from pydantic import BaseModel
from typing import Dict
from datetime import datetime


class TelemetryPayload(BaseModel):
    timestamp: datetime
    signals: Dict[str, float]
