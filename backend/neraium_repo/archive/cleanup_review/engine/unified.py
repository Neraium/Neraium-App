"""Unified Engine: canonical entrypoint for all Neraium use cases.

This module now owns live ingestion, batch ingestion, replay, and diagnostics
without delegating to secondary wrapper engines.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from neraium_core.alignment import StructuralEngine
from neraium_core.engine.config import ProductionEngineConfig, ProductionLoggingConfig
from neraium_core.engine.dataset_loader import load_dataset
from neraium_core.engine.logging_setup import get_logger
from neraium_core.engine.schemas import BatchResult, EngineResult, InputFrame
from neraium_core.engine_optimizations import get_asset_config
from neraium_core.decision import DecisionEngine

logger = logging.getLogger(__name__)


class Engine:
    """Unified Neraium engine with a single implementation path for all modes."""

    def __init__(
        self,
        config: ProductionEngineConfig | None = None,
        logging_config: ProductionLoggingConfig | None = None,
        baseline_window: int | None = None,
        recent_window: int | None = None,
        enable_shadow_mode: bool = False,
    ):
        self.config = config or ProductionEngineConfig.from_env()
        self.logging_config = logging_config or ProductionLoggingConfig.from_env()
        self.enable_shadow_mode = enable_shadow_mode

        if baseline_window is not None:
            self.config = replace(self.config, baseline_window=baseline_window)
        if recent_window is not None:
            self.config = replace(self.config, recent_window=recent_window)

        self.config.validate()

        self._logger = get_logger(__name__, self.logging_config)
        self._frame_count_by_unit: dict[str, int] = {}
        self._structural_engines: dict[str, StructuralEngine] = {}  # Per-unit engines for asset-specific tuning
        self._decision_engines: dict[str, DecisionEngine] = {}  # Per-unit decision engines

        self._structural_engine = self._build_structural_engine()
        self._decision_engine = DecisionEngine()  # Default decision engine
        self._shadow_mode_evidence: list[dict[str, Any]] = []
        self._replay_results: list[dict[str, Any]] = []
        self._previous_outputs: dict[str, dict[str, Any]] = {}  # Track previous output per unit

    def _build_structural_engine(self, unit_id: str | None = None) -> StructuralEngine:
        """Build structural engine with optional asset-specific tuning."""
        asset_config = get_asset_config(unit_id) if unit_id else None

        if asset_config:
            return StructuralEngine(
                baseline_window=asset_config.baseline_window,
                recent_window=asset_config.recent_window,
                frame_debug=False,
                drift_smoothing_window=asset_config.drift_smoothing_window,
                watch_quantile=asset_config.watch_quantile,
                alert_quantile=asset_config.alert_quantile,
                watch_persistence=asset_config.watch_persistence,
                alert_persistence=asset_config.alert_persistence,
            )

        return StructuralEngine(
            baseline_window=self.config.baseline_window,
            recent_window=self.config.recent_window,
            frame_debug=False,
            drift_smoothing_window=25,
            watch_quantile=0.65,
            alert_quantile=0.85,
            watch_persistence=5,
            alert_persistence=3,
        )

    def _get_engine_for_unit(self, unit_id: str) -> StructuralEngine:
        """Get or create engine for specific unit, using asset-specific config if available."""
        if unit_id not in self._structural_engines:
            self._structural_engines[unit_id] = self._build_structural_engine(unit_id)
        return self._structural_engines[unit_id]

    def _get_decision_engine_for_unit(self, unit_id: str) -> DecisionEngine:
        """Get or create decision engine for specific unit."""
        if unit_id not in self._decision_engines:
            self._decision_engines[unit_id] = DecisionEngine()
        return self._decision_engines[unit_id]

    def _reset_runtime_state(self) -> None:
        self._structural_engine = self._build_structural_engine()
        self._frame_count_by_unit = {}
        self._replay_results = []
        self._shadow_mode_evidence = []

    def ingest_frame(
        self,
        timestamp: float,
        unit_id: str,
        sensors: dict[str, float],
    ) -> EngineResult:
        frame = InputFrame(timestamp=timestamp, unit_id=unit_id, sensors=sensors)
        return self.process_frame(frame)

    def process_frame(self, frame: InputFrame) -> EngineResult:
        try:
            frame.validate()
        except ValueError as e:
            self._logger.error(f"Invalid frame for unit {frame.unit_id}: {e}")
            raise

        self._frame_count_by_unit[frame.unit_id] = self._frame_count_by_unit.get(frame.unit_id, 0) + 1
        frame_count = self._frame_count_by_unit[frame.unit_id]

        engine_frame = {
            "timestamp": frame.timestamp,
            "asset_id": frame.unit_id,
            "site_id": "production",
            "sensor_values": frame.sensors,
        }

        try:
            # Use asset-specific engine if available, otherwise fallback to default
            engine = self._get_engine_for_unit(frame.unit_id)
            raw_result = engine.process_frame(engine_frame)

            state = self._extract_state(raw_result)
            drift_score = self._extract_drift_score(raw_result)
            stability_score = self._compute_stability_score(raw_result)
            health_percentage = self._compute_health(drift_score, stability_score)

            result = EngineResult(
                timestamp=frame.timestamp,
                unit_id=frame.unit_id,
                frame_count=frame_count,
                state=state,
                drift_score=drift_score,
                stability_score=stability_score,
                health_percentage=health_percentage,
                baseline_ready=len(engine.frames) >= engine.baseline_window,
                sensor_count=len(frame.sensors),
                model_age_frames=len(engine.frames),
            )
            result.validate()

            # === DECISION LAYER INTEGRATION ===
            # Apply decision logic to determine what to surface and recommend
            decision_engine = self._get_decision_engine_for_unit(frame.unit_id)
            prev_output = self._previous_outputs.get(frame.unit_id)
            decision = decision_engine.decide(raw_result, prev_output)

            # Attach decision to result
            result.decision = decision.to_dict()
            self._previous_outputs[frame.unit_id] = raw_result

            if self.enable_shadow_mode:
                self._shadow_mode_evidence.append(result.to_dict())

            return result
        except Exception as e:
            self._logger.error(f"Error processing frame for unit {frame.unit_id}: {e}", exc_info=True)
            return self._safe_degraded_result(frame, frame_count)

    def ingest_batch(self, frames: list[InputFrame]) -> BatchResult:
        return self.process_batch(frames)

    def process_batch(self, frames: list[InputFrame]) -> BatchResult:
        start = time.time()
        results: list[EngineResult] = []
        errors: list[str] = []
        for i, frame in enumerate(frames):
            try:
                results.append(self.process_frame(frame))
            except Exception as e:
                errors.append(f"Frame {i}: {e}")
        return BatchResult(results=results, errors=errors, processing_time_seconds=time.time() - start)

    def replay(
        self,
        dataset_path: Path | str,
        dataset_type: str,
        unit_filter: str | list[str] | None = None,
        decision_audit_out: Path | str | None = None,
    ) -> dict[str, Any]:
        dataset_path = Path(dataset_path)
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        self._logger.info(f"Replaying dataset: {dataset_path} (type={dataset_type})")
        df = load_dataset(dataset_path, dataset_type)
        if df is None:
            raise ValueError(f"Failed to load dataset: {dataset_path}")

        if unit_filter is not None:
            if isinstance(unit_filter, str):
                unit_filter = [unit_filter]
            df = df[df["asset_id"].isin(unit_filter)]

        self._reset_runtime_state()

        # Initialize decision audit logger if requested
        audit_logger = None
        if decision_audit_out:
            from neraium_core.decision_audit_logger import DecisionAuditLogger
            audit_logger = DecisionAuditLogger(decision_audit_out)
            self._logger.info(f"Decision audit logging enabled: {decision_audit_out}")

        try:
            for _, row in df.iterrows():
                try:
                    asset_id = row["asset_id"]
                    engine = self._get_engine_for_unit(asset_id)
                    raw_result = engine.process_frame(
                        {
                            "timestamp": row["timestamp"],
                            "asset_id": asset_id,
                            "site_id": row.get("site_id", "default-site"),
                            "sensor_values": self._extract_sensors_from_row(row),
                            "structural_drift_score": row.get("structural_drift_score", 0.0),
                        }
                    )
                    self._replay_results.append(raw_result)

                    # Integrate decision layer if audit logging is enabled
                    if audit_logger:
                        try:
                            decision_engine = self._get_decision_engine_for_unit(asset_id)
                            prev_output = self._previous_outputs.get(asset_id)
                            decision = decision_engine.decide(raw_result, prev_output)
                            self._previous_outputs[asset_id] = raw_result

                            # Prepare audit row with decision data
                            audit_row = dict(raw_result)
                            audit_row["unit_id"] = asset_id
                            audit_row["decision"] = decision.to_dict()
                            audit_row["cycle"] = row.get("cycle", "")
                            audit_row["phase"] = raw_result.get("system_phase", "")
                            audit_row["composite_instability"] = raw_result.get("relational_instability_score", 0.0)

                            audit_logger.write_frame(audit_row)
                        except Exception as e:
                            self._logger.warning(f"Error in decision audit for {asset_id}: {e}")
                            # Write audit row without decision data when decision processing fails
                            audit_row = dict(raw_result)
                            audit_row["unit_id"] = asset_id
                            audit_row["decision"] = {}
                            audit_row["cycle"] = row.get("cycle", "")
                            audit_row["phase"] = raw_result.get("system_phase", "")
                            audit_row["composite_instability"] = raw_result.get("relational_instability_score", 0.0)
                            audit_logger.write_frame(audit_row)

                    if self.enable_shadow_mode:
                        self._shadow_mode_evidence.append({"timestamp": row["timestamp"], "asset_id": row["asset_id"], "result": raw_result})
                except Exception as e:
                    self._logger.warning(f"Error processing row: {e}")

        finally:
            if audit_logger:
                audit_logger.close()

        return {
            "dataset": str(dataset_path),
            "dataset_type": dataset_type,
            "records_loaded": len(df),
            "records_processed": len(self._replay_results),
            "units": df["asset_id"].nunique() if len(df) > 0 else 0,
            "decision_audit_logged": decision_audit_out is not None,
        }

    def get_summary(self) -> dict[str, Any]:
        if not self._replay_results:
            return {"error": "No replay data available"}
        results = self._replay_results
        states = [r.get("state", "STABLE") for r in results]
        drifts = [float(r.get("structural_drift_score", 0.0)) for r in results]
        return {
            "total_frames": len(results),
            "avg_drift": sum(drifts) / len(drifts) if drifts else 0.0,
            "max_drift": max(drifts) if drifts else 0.0,
            "min_drift": min(drifts) if drifts else 0.0,
            "state_distribution": {state: states.count(state) for state in set(states)},
            "alert_count": states.count("ALERT"),
            "watch_count": states.count("WATCH"),
            "stable_count": states.count("STABLE"),
        }

    def get_evidence_report(self) -> dict[str, Any]:
        if not self.enable_shadow_mode:
            return {"error": "Shadow mode not enabled"}
        if not self._shadow_mode_evidence:
            return {"error": "No evidence data available"}
        return {
            "evidence_count": len(self._shadow_mode_evidence),
            "evidence": self._shadow_mode_evidence[:100],
            "summary": self.get_summary(),
        }

    def get_readiness(self) -> dict[str, Any]:
        # Aggregate readiness across all units if using per-unit engines
        if self._structural_engines:
            total_frames = sum(len(e.frames) for e in self._structural_engines.values())
            all_baseline_ready = all(
                len(e.frames) >= e.baseline_window for e in self._structural_engines.values()
            )
            all_sensors = set()
            for e in self._structural_engines.values():
                all_sensors.update(e.sensor_order)
            baseline_window = next(iter(self._structural_engines.values())).baseline_window if self._structural_engines else self._structural_engine.baseline_window
        else:
            total_frames = len(self._structural_engine.frames)
            all_baseline_ready = total_frames >= self._structural_engine.baseline_window
            all_sensors = set(self._structural_engine.sensor_order)
            baseline_window = self._structural_engine.baseline_window

        return {
            "baseline_ready": all_baseline_ready,
            "frames_collected": total_frames,
            "baseline_window": baseline_window,
            "sensors_detected": len(all_sensors),
            "sensor_names": sorted(list(all_sensors)),
            "units_tracked": len(self._frame_count_by_unit),
        }

    def get_diagnostics(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "logging_config": self.logging_config.to_dict(),
            "readiness": self.get_readiness(),
            "frame_count_by_unit": dict(self._frame_count_by_unit),
        }

    @staticmethod
    def _extract_state(raw_result: dict[str, Any]) -> str:
        state = raw_result.get("state") or raw_result.get("policy_state")
        if state in {"STABLE", "WATCH", "ALERT"}:
            return str(state)
        return "STABLE"

    @staticmethod
    def _extract_drift_score(raw_result: dict[str, Any]) -> float:
        try:
            score = float(raw_result.get("score") or raw_result.get("drift_score") or 0.0)
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            return 0.0

    def _compute_stability_score(self, raw_result: dict[str, Any]) -> float:
        try:
            stability = raw_result.get("stability_score")
            if stability is not None:
                return max(0.0, min(1.0, float(stability)))
            drift = self._extract_drift_score(raw_result)
            return max(0.0, 1.0 - drift)
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _compute_health(drift_score: float, stability_score: float) -> int:
        health = 100.0 - (drift_score * 50.0)
        health += stability_score * 20.0
        return int(round(max(0.0, min(100.0, health))))

    def _safe_degraded_result(self, frame: InputFrame, frame_count: int) -> EngineResult:
        return EngineResult(
            timestamp=frame.timestamp,
            unit_id=frame.unit_id,
            frame_count=frame_count,
            state="STABLE",
            drift_score=0.0,
            stability_score=0.5,
            health_percentage=50,
            baseline_ready=False,
            sensor_count=len(frame.sensors),
            model_age_frames=len(self._structural_engine.frames),
        )

    def get_future_path_map(self, unit_id: str | None = None) -> dict[str, Any]:
        """Get future path map for a unit or default engine.

        Args:
            unit_id: Optional unit ID. Uses default engine if not provided.

        Returns:
            Dict with current_state, future_paths, and recommended_interventions
        """
        if unit_id is None:
            return self._structural_engine.get_future_path_map()
        else:
            engine = self._get_engine_for_unit(unit_id)
            return engine.get_future_path_map()

    @staticmethod
    def _extract_sensors_from_row(row: dict) -> dict[str, float]:
        skip_cols = {
            "timestamp", "asset_id", "site_id", "unit", "cycle",
            "structural_drift_score", "true_rul", "failure_cycle", "lead_time",
        }
        sensors: dict[str, float] = {}
        for key, value in row.items():
            if key not in skip_cols and isinstance(value, (int, float)):
                try:
                    sensors[key] = float(value)
                except (TypeError, ValueError):
                    pass
        return sensors


__all__ = ["Engine", "InputFrame", "EngineResult", "BatchResult"]
