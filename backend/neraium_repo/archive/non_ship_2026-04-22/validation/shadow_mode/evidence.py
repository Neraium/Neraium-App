"""Structured evidence logging for shadow-mode runs.

Emits append-only JSONL logs containing:
- Frame-level detection results (drift, instability, transitions)
- State and policy decisions
- Per-unit isolation and trajectory tracking
- Metadata for reproducibility

All timestamps are ISO-8601 UTC.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class EvidenceFrame:
    """Single frame of evidence from shadow-mode processing."""

    # Timing
    timestamp_utc: str  # ISO-8601
    frame_index: int
    processing_latency_ms: float

    # Asset and context
    asset_id: str
    unit_id: Optional[str]
    domain: Optional[str]
    system_type: Optional[str]

    # Detection results
    state: str  # STABLE, WATCH, ALERT
    policy_state: str
    structural_drift_score: float
    structural_drift_score_smoothed: float
    relational_instability_score: float
    transition_pressure: float

    # Confidence and quality
    confidence_score: float
    data_quality_summary: Dict[str, Any]
    active_sensor_count: int
    missing_sensor_count: int

    # State transitions
    transition_detected: bool
    transition_state: str  # NONE, ENTERING, EXITING, CROSSED
    regime_name: Optional[str]
    regime_distance: Optional[float]

    # Attribution
    dominant_driver: Optional[str]
    top_drivers: Optional[List[Dict[str, Any]]]

    # Validation
    validation_errors: Optional[List[str]]
    input_validation_passed: bool

    # Raw output for detailed analysis
    raw_engine_output: Dict[str, Any]


class ShadowModeEvidenceLogger:
    """Append-only JSONL logger for shadow-mode evidence.

    Usage:
        logger = ShadowModeEvidenceLogger(output_dir="/tmp/shadow_runs")
        logger.write_frame(frame_data)
        summary = logger.close()
    """

    def __init__(
        self,
        output_dir: str,
        run_name: str,
        config: Optional[Dict[str, Any]] = None,
        engine_version: Optional[str] = None,
        doctrine_version: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.run_name = run_name
        self.config = config or {}
        self.engine_version = engine_version or "unknown"
        self.doctrine_version = doctrine_version or "unknown"

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Evidence log file
        self.log_path = self.output_dir / f"{run_name}_evidence.jsonl"
        self.log_file = open(self.log_path, "w")

        # Metadata
        self.start_time_utc = datetime.now(timezone.utc)
        self.start_time_iso = self.start_time_utc.isoformat()
        self.frame_count = 0
        self.asset_frames: Dict[str, int] = {}
        self.processing_latencies: List[float] = []

    def write_frame(self, frame: EvidenceFrame) -> None:
        """Write a single evidence frame to the log."""
        frame_dict = asdict(frame)
        self.log_file.write(json.dumps(frame_dict) + "\n")
        self.log_file.flush()

        self.frame_count += 1
        self.asset_frames[frame.asset_id] = self.asset_frames.get(frame.asset_id, 0) + 1
        self.processing_latencies.append(frame.processing_latency_ms)

    def write_raw_frame(self, frame_data: Dict[str, Any]) -> None:
        """Write a raw frame dictionary (more flexible)."""
        # Add standard fields if missing
        if "timestamp_utc" not in frame_data:
            frame_data["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        if "frame_index" not in frame_data:
            frame_data["frame_index"] = self.frame_count

        self.log_file.write(json.dumps(frame_data) + "\n")
        self.log_file.flush()

        self.frame_count += 1
        asset_id = frame_data.get("asset_id", "unknown")
        self.asset_frames[asset_id] = self.asset_frames.get(asset_id, 0) + 1

        latency = frame_data.get("processing_latency_ms", 0.0)
        if isinstance(latency, (int, float)):
            self.processing_latencies.append(float(latency))

    def close(self) -> Dict[str, Any]:
        """Close the logger and return metadata."""
        self.log_file.close()

        end_time_utc = datetime.now(timezone.utc)
        end_time_iso = end_time_utc.isoformat()
        duration_seconds = (end_time_utc - self.start_time_utc).total_seconds()

        # Compute latency stats
        latencies_sorted = sorted(self.processing_latencies)
        latency_stats = {
            "count": len(latencies_sorted),
            "min_ms": min(latencies_sorted) if latencies_sorted else 0.0,
            "max_ms": max(latencies_sorted) if latencies_sorted else 0.0,
            "mean_ms": sum(latencies_sorted) / len(latencies_sorted)
            if latencies_sorted
            else 0.0,
            "p50_ms": latencies_sorted[len(latencies_sorted) // 2]
            if latencies_sorted
            else 0.0,
            "p95_ms": latencies_sorted[int(len(latencies_sorted) * 0.95)]
            if latencies_sorted and len(latencies_sorted) > 1
            else 0.0,
            "p99_ms": latencies_sorted[int(len(latencies_sorted) * 0.99)]
            if latencies_sorted and len(latencies_sorted) > 1
            else 0.0,
        }

        metadata = {
            "run_name": self.run_name,
            "start_time_utc": self.start_time_iso,
            "end_time_utc": end_time_iso,
            "duration_seconds": duration_seconds,
            "frame_count": self.frame_count,
            "asset_count": len(self.asset_frames),
            "assets_processed": self.asset_frames,
            "latency_stats_ms": latency_stats,
            "log_path": str(self.log_path.absolute()),
            "engine_version": self.engine_version,
            "doctrine_version": self.doctrine_version,
            "config": self.config,
        }

        # Write metadata
        metadata_path = self.output_dir / f"{self.run_name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata


class EvidenceDataFrame:
    """CSV export interface for evidence logs."""

    @staticmethod
    def export_to_csv(jsonl_path: Path, csv_path: Path) -> int:
        """Convert JSONL evidence log to CSV.

        Returns:
            Number of rows written
        """
        import csv

        if not jsonl_path.exists():
            raise FileNotFoundError(f"Evidence log not found: {jsonl_path}")

        rows = []
        with open(jsonl_path) as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))

        if not rows:
            return 0

        # Flatten nested dicts for CSV
        flat_rows = []
        for row in rows:
            flat = _flatten_dict(row, parent_key="")
            flat_rows.append(flat)

        # Get all field names
        fieldnames = sorted(set().union(*(r.keys() for r in flat_rows)))

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)

        return len(flat_rows)


def _flatten_dict(d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """Flatten nested dictionary for CSV export."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}_{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, parent_key=new_key).items())
        elif isinstance(v, (list, tuple)):
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)
