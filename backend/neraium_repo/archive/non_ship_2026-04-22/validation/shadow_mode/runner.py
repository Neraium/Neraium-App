"""Shadow-mode runner: read-only production deployment harness.

Ingests telemetry (live or replayed) and processes through ProductionEngine
without triggering any external actions. Records all outputs with full
timestamps and isolation per asset/unit.

Usage:
    runner = ShadowModeRunner(decision_fn=engine.process_frame)
    results = runner.process_telemetry_file("telemetry.jsonl")
    summary = runner.finalize()

    # Or use CLI:
    python -m validation.shadow_mode.runner process \\
        --telemetry telemetry.jsonl \\
        --output /var/shadow_runs/2024-04-12
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import traceback

from .evidence import ShadowModeEvidenceLogger, EvidenceFrame
from .report import ShadowModeSummaryReport


class ShadowModeRunner:
    """Process telemetry in read-only shadow mode.

    Attributes:
        decision_fn: Callable that takes frame dict and returns engine output
        output_dir: Path for evidence and reports
        run_name: Descriptive run identifier
        logger: Evidence logger instance
    """

    def __init__(
        self,
        decision_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        output_dir: str = "/tmp/shadow_runs",
        run_name: str = "shadow_run",
        config: Optional[Dict[str, Any]] = None,
        engine_version: Optional[str] = None,
        doctrine_version: Optional[str] = None,
    ):
        self.decision_fn = decision_fn
        self.output_dir = Path(output_dir)
        self.run_name = run_name

        self.logger = ShadowModeEvidenceLogger(
            output_dir=str(self.output_dir),
            run_name=run_name,
            config=config or {},
            engine_version=engine_version,
            doctrine_version=doctrine_version,
        )

        self.frame_count = 0
        self.asset_frames: Dict[str, int] = {}
        self.errors: List[Dict[str, Any]] = []

    def process_telemetry_file(self, telemetry_path: str) -> Dict[str, Any]:
        """Process telemetry from JSONL file.

        Args:
            telemetry_path: Path to .jsonl file with frames

        Returns:
            Processing summary
        """
        telemetry_path = Path(telemetry_path)
        if not telemetry_path.exists():
            raise FileNotFoundError(f"Telemetry file not found: {telemetry_path}")

        frame_count = 0
        with open(telemetry_path) as f:
            for line in f:
                if line.strip():
                    try:
                        frame_data = json.loads(line)
                        self.process_frame(frame_data)
                        frame_count += 1
                    except Exception as e:
                        self.errors.append(
                            {
                                "frame_index": frame_count,
                                "error": str(e),
                                "type": type(e).__name__,
                            }
                        )

        return {"frames_processed": frame_count, "errors": len(self.errors)}

    def process_telemetry_stream(
        self, frames: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process telemetry from in-memory list.

        Args:
            frames: List of frame dictionaries

        Returns:
            Processing summary
        """
        for i, frame_data in enumerate(frames):
            try:
                self.process_frame(frame_data, frame_index=i)
            except Exception as e:
                self.errors.append(
                    {
                        "frame_index": i,
                        "error": str(e),
                        "type": type(e).__name__,
                    }
                )

        return {"frames_processed": len(frames), "errors": len(self.errors)}

    def process_frame(
        self, frame_data: Dict[str, Any], frame_index: Optional[int] = None
    ) -> None:
        """Process a single frame through the engine.

        Args:
            frame_data: Raw telemetry frame
            frame_index: Optional explicit frame index (otherwise auto-incremented)
        """
        if frame_index is None:
            frame_index = self.frame_count

        # Validate and extract key fields
        asset_id = str(frame_data.get("asset_id", f"asset_{frame_index}"))
        unit_id = frame_data.get("unit_id")
        timestamp = frame_data.get("timestamp")

        # Record frame processing start
        processing_start = time.perf_counter()

        try:
            # Call decision function (read-only)
            engine_output = self.decision_fn(frame_data)

            processing_latency_ms = (
                time.perf_counter() - processing_start
            ) * 1000

            # Extract key outputs
            state = engine_output.get("state", "STABLE")
            policy_state = engine_output.get("policy_state", "STABLE")
            drift_score = engine_output.get("structural_drift_score", 0.0)
            drift_smoothed = engine_output.get(
                "structural_drift_score_smoothed", drift_score
            )
            relational_instability = engine_output.get(
                "relational_instability_score", 0.0
            )
            transition_pressure = engine_output.get("transition_pressure", 0.0)
            transition_detected = engine_output.get("transition_detected", False)
            transition_state = engine_output.get("transition_state", "NONE")

            # Confidence and reliability
            confidence = engine_output.get("system_health", 100) / 100.0
            if "reliability_intelligence" in engine_output:
                confidence = engine_output.get(
                    "reliability_intelligence", {}
                ).get("risk_advisory", {}).get("calibrated_confidence", confidence)

            # Attribution
            attribution = engine_output.get("attribution", {})
            top_drivers = attribution.get("top_drivers", [])
            dominant_driver = engine_output.get("dominant_driver")

            # Data quality
            data_quality = engine_output.get("data_quality_summary", {})
            active_sensors = engine_output.get("active_sensor_count", 0)
            missing_sensors = engine_output.get("missing_sensor_count", 0)

            # Regime
            regime_name = engine_output.get("regime_name")
            regime_distance = engine_output.get("regime_distance")

            # Build evidence frame
            evidence_frame = EvidenceFrame(
                timestamp_utc=(
                    datetime.now(timezone.utc).isoformat()
                    if timestamp is None
                    else str(timestamp)
                ),
                frame_index=frame_index,
                processing_latency_ms=processing_latency_ms,
                asset_id=asset_id,
                unit_id=unit_id,
                domain=frame_data.get("domain"),
                system_type=frame_data.get("system_type"),
                state=state,
                policy_state=policy_state,
                structural_drift_score=float(drift_score),
                structural_drift_score_smoothed=float(drift_smoothed),
                relational_instability_score=float(relational_instability),
                transition_pressure=float(transition_pressure),
                confidence_score=float(confidence),
                data_quality_summary=data_quality,
                active_sensor_count=int(active_sensors),
                missing_sensor_count=int(missing_sensors),
                transition_detected=bool(transition_detected),
                transition_state=transition_state,
                regime_name=regime_name,
                regime_distance=(
                    float(regime_distance) if regime_distance is not None else None
                ),
                dominant_driver=dominant_driver,
                top_drivers=top_drivers,
                validation_errors=None,
                input_validation_passed=True,
                raw_engine_output=engine_output,
            )

            self.logger.write_frame(evidence_frame)

        except Exception as e:
            # Log validation error but continue processing
            processing_latency_ms = (
                time.perf_counter() - processing_start
            ) * 1000

            error_frame = EvidenceFrame(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                frame_index=frame_index,
                processing_latency_ms=processing_latency_ms,
                asset_id=asset_id,
                unit_id=unit_id,
                domain=frame_data.get("domain"),
                system_type=frame_data.get("system_type"),
                state="ERROR",
                policy_state="ERROR",
                structural_drift_score=0.0,
                structural_drift_score_smoothed=0.0,
                relational_instability_score=0.0,
                transition_pressure=0.0,
                confidence_score=0.0,
                data_quality_summary={"error": str(e)},
                active_sensor_count=0,
                missing_sensor_count=0,
                transition_detected=False,
                transition_state="NONE",
                regime_name=None,
                regime_distance=None,
                dominant_driver=None,
                top_drivers=None,
                validation_errors=[str(e), traceback.format_exc()],
                input_validation_passed=False,
                raw_engine_output={},
            )

            self.logger.write_frame(error_frame)
            self.errors.append(
                {
                    "frame_index": frame_index,
                    "asset_id": asset_id,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

        self.frame_count += 1
        self.asset_frames[asset_id] = self.asset_frames.get(asset_id, 0) + 1

    def finalize(self) -> Dict[str, Any]:
        """Close logger and generate summary report.

        Returns:
            Dictionary with:
            - metadata: Run metadata
            - summary: Summary report
            - evidence_log_path: Path to JSONL log
            - report_path: Path to summary JSON
            - errors: List of errors if any
        """
        metadata = self.logger.close()

        # Generate summary report
        report_gen = ShadowModeSummaryReport()
        report_gen.load_evidence(self.logger.log_path)
        summary = report_gen.generate_summary()

        # Write summary
        summary_path = self.output_dir / f"{self.run_name}_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return {
            "success": True,
            "run_name": self.run_name,
            "metadata": metadata,
            "summary_stats": {
                "total_frames": self.frame_count,
                "unique_assets": len(self.asset_frames),
                "error_count": len(self.errors),
                "error_rate": (
                    round(100 * len(self.errors) / self.frame_count, 2)
                    if self.frame_count > 0
                    else 0.0
                ),
            },
            "paths": {
                "evidence_log": str(self.logger.log_path.absolute()),
                "metadata_file": str(
                    self.output_dir / f"{self.run_name}_metadata.json"
                ),
                "summary_report": str(summary_path.absolute()),
                "output_directory": str(self.output_dir.absolute()),
            },
            "errors": self.errors[:50],  # First 50 errors
            "error_count_total": len(self.errors),
        }


def create_dummy_decision_fn() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Create a minimal dummy decision function for testing."""

    def dummy_decision(frame: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "state": "STABLE",
            "policy_state": "STABLE",
            "structural_drift_score": 0.1,
            "structural_drift_score_smoothed": 0.1,
            "relational_instability_score": 0.05,
            "transition_pressure": 0.0,
            "transition_detected": False,
            "transition_state": "NONE",
            "system_health": 100,
            "active_sensor_count": 10,
            "missing_sensor_count": 0,
            "data_quality_summary": {"all_good": True},
            "dominant_driver": None,
        }

    return dummy_decision


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Shadow-mode runner for telemetry processing"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Process command
    process_parser = subparsers.add_parser(
        "process", help="Process telemetry file"
    )
    process_parser.add_argument(
        "--telemetry", required=True, help="Path to telemetry JSONL file"
    )
    process_parser.add_argument(
        "--output",
        default="/tmp/shadow_runs",
        help="Output directory for evidence logs",
    )
    process_parser.add_argument(
        "--run-name", default="shadow_run", help="Descriptive run name"
    )

    args = parser.parse_args()

    if args.command == "process":
        runner = ShadowModeRunner(
            decision_fn=create_dummy_decision_fn(),
            output_dir=args.output,
            run_name=args.run_name,
        )

        print(f"Processing telemetry: {args.telemetry}")
        result = runner.process_telemetry_file(args.telemetry)
        print(f"Processed {result['frames_processed']} frames")

        final = runner.finalize()
        print(f"\nEvidence log: {final['paths']['evidence_log']}")
        print(f"Summary report: {final['paths']['summary_report']}")
        print(
            f"Total errors: {final['summary_stats']['error_count']}/{final['summary_stats']['total_frames']}"
        )
