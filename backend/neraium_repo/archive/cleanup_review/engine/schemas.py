"""Strict input and output schemas for production deployments.

All frames and results flowing through the engine must conform to these schemas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class InputFrame:
    """Strict schema for input frames.

    Each frame represents a single time step of multivariate sensor data.
    """

    timestamp: float  # Unix timestamp (seconds)
    unit_id: str  # Unique identifier for the asset/unit being monitored
    sensors: dict[str, float]  # sensor_name -> value mapping

    def validate(self) -> None:
        """Validate frame against schema constraints.

        Raises:
            ValueError: If frame is invalid
        """
        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError(f"Invalid timestamp: must be non-negative number, got {self.timestamp}")

        if not isinstance(self.unit_id, str) or not self.unit_id.strip():
            raise ValueError(f"Invalid unit_id: must be non-empty string, got {self.unit_id!r}")

        if not isinstance(self.sensors, dict):
            raise ValueError(f"Invalid sensors: must be dict, got {type(self.sensors)}")

        if not self.sensors:
            raise ValueError("Invalid sensors: cannot be empty")

        for name, value in self.sensors.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"Invalid sensor name: must be non-empty string, got {name!r}")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Invalid sensor value for {name}: must be number, got {value!r}")
            if math.isnan(value):
                raise ValueError(f"Invalid sensor value for {name}: cannot be NaN")
            if math.isinf(value):
                raise ValueError(f"Invalid sensor value for {name}: cannot be infinite")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> InputFrame:
        """Create from dictionary with validation."""
        frame = InputFrame(
            timestamp=data.get("timestamp"),
            unit_id=data.get("unit_id"),
            sensors=data.get("sensors", {}),
        )
        frame.validate()
        return frame


@dataclass
class EngineResult:
    """Strict schema for engine output results.

    Result emitted by the engine after processing a frame.
    """

    timestamp: float  # Timestamp of the processed frame
    unit_id: str  # Unit that was processed
    frame_count: int  # Total frames processed for this unit
    state: str  # Current state: STABLE, WATCH, or ALERT
    drift_score: float  # Normalized drift score [0, 1]
    stability_score: float  # Normalized stability metric [0, 1]
    health_percentage: int  # Health metric [0, 100]

    # Optional detailed metrics
    baseline_ready: bool = False
    sensor_count: int = 0
    model_age_frames: int = 0

    # Decision layer metadata (populated by DecisionEngine)
    decision: dict[str, Any] | None = None

    def validate(self) -> None:
        """Validate result against schema constraints.

        Raises:
            ValueError: If result is invalid
        """
        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp}")

        if not isinstance(self.unit_id, str) or not self.unit_id.strip():
            raise ValueError(f"Invalid unit_id: {self.unit_id!r}")

        if not isinstance(self.frame_count, int) or self.frame_count < 0:
            raise ValueError(f"Invalid frame_count: {self.frame_count}")

        if self.state not in {"STABLE", "WATCH", "ALERT"}:
            raise ValueError(f"Invalid state: {self.state!r}")

        if not (0 <= self.drift_score <= 1):
            raise ValueError(f"Invalid drift_score: must be in [0, 1], got {self.drift_score}")

        if not (0 <= self.stability_score <= 1):
            raise ValueError(f"Invalid stability_score: must be in [0, 1], got {self.stability_score}")

        if not (0 <= self.health_percentage <= 100):
            raise ValueError(f"Invalid health_percentage: must be in [0, 100], got {self.health_percentage}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class BatchResult:
    """Result from processing a batch of frames."""

    results: list[EngineResult]
    errors: list[str]  # Any frames that failed processing
    processing_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "results": [r.to_dict() for r in self.results],
            "errors": self.errors,
            "processing_time_seconds": self.processing_time_seconds,
        }
