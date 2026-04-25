"""Replay comparison: deterministic diff of two runs on same telemetry.

Compares outputs from:
- Different doctrine versions
- Different engine configurations
- Different timestamps (to detect drift)

Produces structured comparison artifact showing per-field mismatches.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict


class ReplayDiff:
    """Compare two evidence logs from runs on identical telemetry."""

    # Fields that vary across runs due to execution environment, not decision logic
    NON_DETERMINISTIC_FIELDS = {
        "processing_latency_ms",  # Runtime varies by machine/load
        "timestamp_utc",          # Generated at runtime
        "run_id",                 # Unique per execution
        "session_id",             # Unique per execution
        "execution_timestamp",    # Generated at runtime
    }

    def __init__(
        self,
        run_a_evidence: Path,
        run_b_evidence: Path,
        run_a_name: str = "Run A",
        run_b_name: str = "Run B",
    ):
        self.run_a_name = run_a_name
        self.run_b_name = run_b_name

        self.frames_a = self._load_evidence(run_a_evidence)
        self.frames_b = self._load_evidence(run_b_evidence)

    def compare(self) -> Dict[str, Any]:
        """Generate comprehensive comparison.

        Returns:
            Dictionary with:
            - frame_count_diff
            - per_frame_mismatches
            - aggregate_statistics
            - field_differences
        """
        if len(self.frames_a) != len(self.frames_b):
            return self._mismatched_frame_count_report()

        mismatches = []
        field_differences = defaultdict(
            lambda: {"match_count": 0, "mismatch_count": 0, "examples": []}
        )

        for i, (frame_a, frame_b) in enumerate(zip(self.frames_a, self.frames_b)):
            frame_mismatch = self._compare_frames(frame_a, frame_b)
            if frame_mismatch:
                mismatches.append(frame_mismatch)

            # Aggregate field differences
            for field in self._get_all_fields(frame_a, frame_b):
                # Skip non-deterministic fields that vary across runs
                if field in self.NON_DETERMINISTIC_FIELDS:
                    continue

                val_a = self._get_field(frame_a, field)
                val_b = self._get_field(frame_b, field)

                if self._values_match(val_a, val_b):
                    field_differences[field]["match_count"] += 1
                else:
                    field_differences[field]["mismatch_count"] += 1
                    if len(field_differences[field]["examples"]) < 3:
                        field_differences[field]["examples"].append(
                            {
                                "frame_index": i,
                                "run_a": val_a,
                                "run_b": val_b,
                            }
                        )

        return {
            "metadata": {
                "run_a": self.run_a_name,
                "run_b": self.run_b_name,
                "frame_count": len(self.frames_a),
            },
            "summary": {
                "total_frames": len(self.frames_a),
                "frames_with_differences": len(mismatches),
                "match_rate": round(
                    (1.0 - len(mismatches) / len(self.frames_a)) * 100, 2
                ),
            },
            "field_level_diff": self._field_diff_summary(field_differences),
            "per_frame_mismatches": mismatches[:100],  # Limit to first 100
            "mismatch_count_total": len(mismatches),
        }

    def _compare_frames(
        self, frame_a: Dict[str, Any], frame_b: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Compare two frames, return None if identical."""
        differences = []

        for field in self._get_all_fields(frame_a, frame_b):
            # Skip non-deterministic fields that vary across runs
            if field in self.NON_DETERMINISTIC_FIELDS:
                continue

            val_a = self._get_field(frame_a, field)
            val_b = self._get_field(frame_b, field)

            if not self._values_match(val_a, val_b):
                differences.append(
                    {
                        "field": field,
                        "run_a": val_a,
                        "run_b": val_b,
                        "type": type(val_a).__name__,
                    }
                )

        if not differences:
            return None

        return {
            "frame_index": frame_a.get("frame_index", "unknown"),
            "asset_id": frame_a.get("asset_id", "unknown"),
            "differences": differences,
        }

    def _field_diff_summary(
        self, field_differences: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize field-level differences."""
        critical_fields = [
            "state",
            "policy_state",
            "structural_drift_score",
            "relational_instability_score",
            "transition_detected",
            "dominant_driver",
        ]

        return {
            "total_fields": len(field_differences),
            "fields_with_differences": sum(
                1 for f in field_differences.values() if f["mismatch_count"] > 0
            ),
            "critical_field_mismatches": [
                {
                    "field": field,
                    "mismatch_count": field_differences[field]["mismatch_count"],
                    "examples": field_differences[field]["examples"],
                }
                for field in critical_fields
                if field in field_differences
                and field_differences[field]["mismatch_count"] > 0
            ],
            "all_fields_with_diff": sorted(
                [
                    {
                        "field": field,
                        "match_count": data["match_count"],
                        "mismatch_count": data["mismatch_count"],
                        "match_rate": round(
                            data["match_count"]
                            / (data["match_count"] + data["mismatch_count"]),
                            3,
                        ),
                    }
                    for field, data in field_differences.items()
                    if data["mismatch_count"] > 0
                ],
                key=lambda x: x["mismatch_count"],
                reverse=True,
            ),
        }

    @staticmethod
    def _load_evidence(path: Path) -> List[Dict[str, Any]]:
        """Load evidence log."""
        if not path.exists():
            raise FileNotFoundError(f"Evidence log not found: {path}")

        frames = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    frames.append(json.loads(line))
        return frames

    @staticmethod
    def _get_all_fields(frame_a: Dict[str, Any], frame_b: Dict[str, Any]) -> set:
        """Get union of all field names."""
        return set(frame_a.keys()) | set(frame_b.keys())

    @staticmethod
    def _get_field(frame: Dict[str, Any], field: str) -> Any:
        """Safely get field value, handling nested access."""
        if field in frame:
            return frame[field]
        return None

    @staticmethod
    def _values_match(val_a: Any, val_b: Any) -> bool:
        """Check if values match (with tolerance for floats)."""
        if val_a == val_b:
            return True

        # Float tolerance
        if isinstance(val_a, float) and isinstance(val_b, float):
            if abs(val_a - val_b) < 1e-6:
                return True

        # String case-insensitive for state fields
        if isinstance(val_a, str) and isinstance(val_b, str):
            if val_a.upper() == val_b.upper():
                return True

        return False

    def _mismatched_frame_count_report(self) -> Dict[str, Any]:
        """Generate report when frame counts differ."""
        return {
            "metadata": {
                "run_a": self.run_a_name,
                "run_b": self.run_b_name,
                "frame_count": None,
            },
            "error": "Frame count mismatch",
            "details": {
                "run_a_frames": len(self.frames_a),
                "run_b_frames": len(self.frames_b),
                "difference": abs(len(self.frames_a) - len(self.frames_b)),
            },
            "summary": {
                "total_frames": None,
                "frames_with_differences": None,
                "match_rate": 0.0,
            },
        }


def generate_replay_diff(
    run_a_evidence: Path,
    run_b_evidence: Path,
    run_a_name: str = "Run A",
    run_b_name: str = "Run B",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate replay diff report.

    Args:
        run_a_evidence: Path to first run's _evidence.jsonl
        run_b_evidence: Path to second run's _evidence.jsonl
        run_a_name: Descriptive name for first run
        run_b_name: Descriptive name for second run
        output_path: Optional path to write JSON report

    Returns:
        Comparison report dictionary
    """
    diff = ReplayDiff(run_a_evidence, run_b_evidence, run_a_name, run_b_name)
    report = diff.compare()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    return report


def compare_decision_timing(
    run_a_evidence: Path, run_b_evidence: Path
) -> Dict[str, Any]:
    """Compare decision timing between two runs.

    Returns:
        Report with timing analysis
    """
    frames_a = _load_evidence(run_a_evidence)
    frames_b = _load_evidence(run_b_evidence)

    if len(frames_a) != len(frames_b):
        return {"error": "Frame count mismatch"}

    timing_diffs = []
    for i, (frame_a, frame_b) in enumerate(zip(frames_a, frames_b)):
        state_a = frame_a.get("state")
        state_b = frame_b.get("state")

        if state_a != state_b:
            timing_diffs.append(
                {
                    "frame_index": i,
                    "asset_id": frame_a.get("asset_id"),
                    "state_change": f"{state_a} -> {state_b}",
                    "drift_score_a": frame_a.get("structural_drift_score"),
                    "drift_score_b": frame_b.get("structural_drift_score"),
                    "timestamp": frame_a.get("timestamp_utc"),
                }
            )

    return {
        "total_timing_differences": len(timing_diffs),
        "examples": timing_diffs[:20],
    }


def _load_evidence(path: Path) -> List[Dict[str, Any]]:
    """Load evidence log."""
    if not path.exists():
        raise FileNotFoundError(f"Evidence log not found: {path}")

    frames = []
    with open(path) as f:
        for line in f:
            if line.strip():
                frames.append(json.loads(line))
    return frames
