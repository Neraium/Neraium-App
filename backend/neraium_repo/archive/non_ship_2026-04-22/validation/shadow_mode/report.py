"""Summary report generation for shadow-mode runs.

Produces structured summaries including:
- Frame and asset counts
- Decision distribution (STABLE, WATCH, ALERT)
- State transition statistics
- Data quality metrics
- Latency distribution
"""

import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
import statistics


class ShadowModeSummaryReport:
    """Generate comprehensive summary from evidence logs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.frames: List[Dict[str, Any]] = []
        self.per_asset: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.state_transitions: List[tuple] = []

    def load_evidence(self, jsonl_path: Path) -> None:
        """Load evidence log from JSONL."""
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Evidence log not found: {jsonl_path}")

        self.reset()
        with open(jsonl_path) as f:
            for line in f:
                if line.strip():
                    frame = json.loads(line)
                    self.frames.append(frame)
                    asset_id = frame.get("asset_id", "unknown")
                    self.per_asset[asset_id].append(frame)

    def generate_summary(self) -> Dict[str, Any]:
        """Generate full summary report."""
        if not self.frames:
            return self._empty_summary()

        return {
            "overview": self._summary_overview(),
            "per_asset": self._per_asset_summary(),
            "state_distribution": self._state_distribution(),
            "transitions": self._transition_analysis(),
            "data_quality": self._data_quality_summary(),
            "latency": self._latency_summary(),
            "validation": self._validation_summary(),
        }

    def _summary_overview(self) -> Dict[str, Any]:
        """Overview statistics."""
        return {
            "total_frames": len(self.frames),
            "unique_assets": len(self.per_asset),
            "time_range": self._time_range(),
            "frame_indices": {
                "first": self.frames[0].get("frame_index", 0) if self.frames else None,
                "last": self.frames[-1].get("frame_index", 0) if self.frames else None,
            },
        }

    def _per_asset_summary(self) -> Dict[str, Dict[str, Any]]:
        """Per-asset statistics."""
        summary = {}
        for asset_id, frames in self.per_asset.items():
            state_counts = Counter(f.get("state", "UNKNOWN") for f in frames)
            summary[asset_id] = {
                "frame_count": len(frames),
                "state_distribution": dict(state_counts),
                "transitions_detected": sum(1 for f in frames if f.get("transition_detected", False)),
                "avg_drift_score": self._safe_mean([f.get("structural_drift_score", 0.0) for f in frames]),
                "avg_instability_score": self._safe_mean([f.get("relational_instability_score", 0.0) for f in frames]),
                "min_confidence": self._safe_min([f.get("confidence_score", 1.0) for f in frames]),
                "max_confidence": self._safe_max([f.get("confidence_score", 1.0) for f in frames]),
            }
        return summary

    def _state_distribution(self) -> Dict[str, Any]:
        """Overall state distribution."""
        state_counts = Counter(f.get("state", "UNKNOWN") for f in self.frames)
        policy_state_counts = Counter(
            f.get("policy_state", "UNKNOWN") for f in self.frames
        )

        return {
            "state_counts": dict(state_counts),
            "policy_state_counts": dict(policy_state_counts),
            "state_percentages": {
                state: round(100 * count / len(self.frames), 2)
                for state, count in state_counts.items()
            },
            "alert_frames": state_counts.get("ALERT", 0),
            "watch_frames": state_counts.get("WATCH", 0),
            "stable_frames": state_counts.get("STABLE", 0),
        }

    def _transition_analysis(self) -> Dict[str, Any]:
        """Analyze state transitions across per-asset chronology."""
        transitions = []

        # Compute transitions per asset to handle interleaved telemetry correctly
        per_asset_transitions = self._count_transitions_per_asset()

        # Build detailed transition list from per-asset frames
        for asset_id, frames in self.per_asset.items():
            for i in range(len(frames) - 1):
                current_state = frames[i].get("state", "UNKNOWN")
                next_state = frames[i + 1].get("state", "UNKNOWN")

                if current_state != next_state:
                    transitions.append(
                        {
                            "frame_index": frames[i].get("frame_index"),
                            "asset_id": asset_id,
                            "from": current_state,
                            "to": next_state,
                            "timestamp": frames[i + 1].get("timestamp_utc"),
                        }
                    )

        transition_types = Counter(
            f"{t['from']}->{t['to']}" for t in transitions
        )

        # Total transitions is sum of per-asset transitions
        total_transitions = sum(per_asset_transitions.values())

        return {
            "total_transitions": total_transitions,
            "transition_types": dict(transition_types),
            "per_asset_transitions": per_asset_transitions,
        }

    def _data_quality_summary(self) -> Dict[str, Any]:
        """Data quality statistics."""
        active_sensor_counts = [
            f.get("active_sensor_count", 0) for f in self.frames
        ]
        missing_sensor_counts = [
            f.get("missing_sensor_count", 0) for f in self.frames
        ]

        validation_errors = []
        passed_count = 0
        for f in self.frames:
            if f.get("input_validation_passed", True):
                passed_count += 1
            else:
                errors = f.get("validation_errors", [])
                if errors:
                    validation_errors.extend(errors)

        return {
            "validation_pass_rate": (
                round(100 * passed_count / len(self.frames), 2)
                if self.frames
                else 0.0
            ),
            "failed_frames": len(self.frames) - passed_count,
            "avg_active_sensors": self._safe_mean(active_sensor_counts),
            "avg_missing_sensors": self._safe_mean(missing_sensor_counts),
            "error_summary": self._summarize_errors(validation_errors),
        }

    def _latency_summary(self) -> Dict[str, Any]:
        """Processing latency statistics."""
        latencies = [
            f.get("processing_latency_ms", 0.0) for f in self.frames
        ]
        latencies = [latency for latency in latencies if isinstance(latency, (int, float))]

        if not latencies:
            return {
                "samples": 0,
                "min_ms": None,
                "max_ms": None,
                "mean_ms": None,
                "median_ms": None,
                "p95_ms": None,
                "p99_ms": None,
            }

        sorted_latencies = sorted(latencies)
        return {
            "samples": len(latencies),
            "min_ms": round(min(latencies), 3),
            "max_ms": round(max(latencies), 3),
            "mean_ms": round(statistics.mean(latencies), 3),
            "median_ms": round(statistics.median(latencies), 3),
            "p95_ms": round(
                sorted_latencies[int(len(sorted_latencies) * 0.95)], 3
            ),
            "p99_ms": round(
                sorted_latencies[int(len(sorted_latencies) * 0.99)], 3
            ),
            "stdev_ms": round(statistics.stdev(latencies), 3)
            if len(latencies) > 1
            else 0.0,
        }

    def _validation_summary(self) -> Dict[str, Any]:
        """Validation and contradiction summary."""
        input_errors = []
        failed_frame_count = 0
        for f in self.frames:
            if not f.get("input_validation_passed", True):
                failed_frame_count += 1
                errors = f.get("validation_errors", [])
                input_errors.extend(errors)

        error_counts = Counter(input_errors)

        return {
            "total_validation_failures": len(input_errors),
            "failure_types": dict(error_counts),
            "failure_rate_percent": round(
                100 * failed_frame_count / len(self.frames), 2
            )
            if self.frames
            else 0.0,
        }

    def _time_range(self) -> Optional[Dict[str, str]]:
        """Extract time range from frames."""
        timestamps = [
            f.get("timestamp_utc")
            for f in self.frames
            if f.get("timestamp_utc")
        ]

        if not timestamps:
            return None

        return {"start": min(timestamps), "end": max(timestamps)}

    def _count_transitions_per_asset(self) -> Dict[str, int]:
        """Count transitions per asset."""
        per_asset = defaultdict(int)
        for asset_id, frames in self.per_asset.items():
            for i in range(len(frames) - 1):
                current_state = frames[i].get("state", "UNKNOWN")
                next_state = frames[i + 1].get("state", "UNKNOWN")
                if current_state != next_state:
                    per_asset[asset_id] += 1
        return dict(per_asset)

    def _summarize_errors(self, errors: List[str]) -> Dict[str, int]:
        """Summarize error types."""
        return dict(Counter(errors))

    @staticmethod
    def _safe_mean(values: List[float]) -> Optional[float]:
        valid = [v for v in values if isinstance(v, (int, float))]
        return round(sum(valid) / len(valid), 3) if valid else None

    @staticmethod
    def _safe_min(values: List[float]) -> Optional[float]:
        valid = [v for v in values if isinstance(v, (int, float))]
        return round(min(valid), 3) if valid else None

    @staticmethod
    def _safe_max(values: List[float]) -> Optional[float]:
        valid = [v for v in values if isinstance(v, (int, float))]
        return round(max(valid), 3) if valid else None

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary."""
        return {
            "overview": {
                "total_frames": 0,
                "unique_assets": 0,
                "time_range": None,
                "frame_indices": {"first": None, "last": None},
            },
            "per_asset": {},
            "state_distribution": {},
            "transitions": {
                "total_transitions": 0,
                "transition_types": {},
                "per_asset_transitions": {},
            },
            "data_quality": {
                "validation_pass_rate": 0.0,
                "failed_frames": 0,
                "avg_active_sensors": None,
                "avg_missing_sensors": None,
                "error_summary": {},
            },
            "latency": {
                "samples": 0,
                "min_ms": None,
                "max_ms": None,
                "mean_ms": None,
                "median_ms": None,
            },
            "validation": {
                "total_validation_failures": 0,
                "failure_types": {},
                "failure_rate_percent": 0.0,
            },
        }


def generate_report_from_evidence(
    evidence_path: Path, output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Generate summary report from evidence log.

    Args:
        evidence_path: Path to _evidence.jsonl file
        output_path: Optional path to write JSON report

    Returns:
        Summary report dictionary
    """
    generator = ShadowModeSummaryReport()
    generator.load_evidence(evidence_path)
    report = generator.generate_summary()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    return report
