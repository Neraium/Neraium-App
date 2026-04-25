from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

import numpy as np

from neraium_core.sii.confidence import confidence_to_level, estimate_confidence
from neraium_core.sii.config import SIIConfig
from neraium_core.sii.context import ExternalContextProvider, NoOpContextProvider
from neraium_core.sii.decision import map_decision_state_with_config, map_to_interpreted_state
from neraium_core.sii.errors import SIIError, SIIProcessingError
from neraium_core.sii.explanation import build_explanation_text, dominant_drivers
from neraium_core.sii.attribution import build_structural_attribution
from neraium_core.sii.geometry_layer import build_geometry_state, flatten_upper
from neraium_core.sii.graph_layer import graph_state
from neraium_core.sii.ingestion import (
    canonical_records_from_payloads,
    frames_from_csv,
)
from neraium_core.sii.operator import build_operator_decision_support
from neraium_core.sii.preprocessing import data_quality, impute_column_mean, summarize_quality
from neraium_core.sii.regime_memory import summarize_regime_memory
from neraium_core.sii.dynamic_graph import compute_dynamic_graph_metrics
from neraium_core.sii.hypothesis_scoring import score_structural_hypothesis
from neraium_core.sii.regime_model import RegimeModel, RegimeObservation
from neraium_core.sii.risk import assess_forward_risk
from neraium_core.system_intelligence import StructuralSystemIntelligencePlatform
from neraium_core.decision_resolver import resolve_best_action
from neraium_core.sii.scoring import StructuralScoringModel
from neraium_core.sii.types import (
    ALLOWED_CONFIDENCE,
    ALLOWED_INTERPRETED_STATES,
    ALLOWED_STATES,
    CanonicalIngestionRecord,
    SIIResult,
    StructuralIndicators,
    TelemetryFrame,
    ingestion_record_to_frame,
)


@dataclass
class _State:
    vectors: deque[np.ndarray]
    timestamps: deque[float]
    sensor_order: list[str]
    baseline_corr: np.ndarray | None
    baseline_adj: np.ndarray | None
    composite_history: deque[float]
    interpreted_history: deque[str]
    raw_structural_history: deque[float]
    raw_relational_history: deque[float]
    raw_graph_history: deque[float]
    raw_regime_history: deque[float]
    raw_coherence_loss_history: deque[float]
    raw_mean_shift_history: deque[float]
    raw_cov_shift_history: deque[float]
    raw_subspace_shift_history: deque[float]
    raw_path_shift_history: deque[float]
    risk_trend_history: deque[str]
    smoothed_risk_trend: str
    cumulative_risk_pressure: float
    decision_hysteresis_state: dict[str, Any]
    intelligence_history: deque[dict[str, Any]]
    prev_graph_adj: np.ndarray | None = None
    prev_degree_centrality: dict[str, float] | None = None
    processed_frames: int = 0


class SystemicInfrastructureIntelligenceEngine:
    """
    Read-only Systemic Infrastructure Intelligence platform engine.

    This engine instruments multivariate structural behavior:
    - statistical geometry of relational state
    - graph topology deformation
    - regime departure from historically stable operating structure
    """

    def __init__(
        self,
        config: SIIConfig | None = None,
        *,
        context_provider: ExternalContextProvider | None = None,
    ) -> None:
        self.config = config or SIIConfig.from_env()
        self.context_provider = context_provider or NoOpContextProvider()
        self.scoring = StructuralScoringModel()
        self.regimes = RegimeModel(config=self.config)
        self.logger = logging.getLogger("neraium.sii.engine")
        self.state = _State(
            vectors=deque(maxlen=self.config.max_history),
            timestamps=deque(maxlen=self.config.max_history),
            sensor_order=[],
            baseline_corr=None,
            baseline_adj=None,
            composite_history=deque(maxlen=240),
            interpreted_history=deque(maxlen=80),
            raw_structural_history=deque(maxlen=240),
            raw_relational_history=deque(maxlen=240),
            raw_graph_history=deque(maxlen=240),
            raw_regime_history=deque(maxlen=240),
            raw_coherence_loss_history=deque(maxlen=240),
            raw_mean_shift_history=deque(maxlen=240),
            raw_cov_shift_history=deque(maxlen=240),
            raw_subspace_shift_history=deque(maxlen=240),
            raw_path_shift_history=deque(maxlen=240),
            risk_trend_history=deque(maxlen=5),
            smoothed_risk_trend="uncertain",
            cumulative_risk_pressure=0.0,
            decision_hysteresis_state={},
            intelligence_history=deque(maxlen=120),
            prev_graph_adj=None,
            prev_degree_centrality=None,
        )
        self.intelligence = StructuralSystemIntelligencePlatform()
        self.logger.info(
            "engine_initialized",
            extra={
                "baseline_window": self.config.baseline_window,
                "recent_window": self.config.recent_window,
                "graph_edge_threshold": self.config.effective_graph_edge_threshold,
                "regime_distance_threshold": self.config.regime_distance_threshold,
            },
        )

    @staticmethod
    def _to_float_timestamp(value: str, fallback: float) -> float:
        text = str(value or "").strip()
        if text:
            try:
                return float(text)
            except (TypeError, ValueError):
                pass
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return float(dt.timestamp())
            except Exception:
                pass
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    def _clear_reference_histories(self) -> None:
        self.state.raw_structural_history.clear()
        self.state.raw_relational_history.clear()
        self.state.raw_graph_history.clear()
        self.state.raw_regime_history.clear()
        self.state.raw_coherence_loss_history.clear()
        self.state.raw_mean_shift_history.clear()
        self.state.raw_cov_shift_history.clear()
        self.state.raw_subspace_shift_history.clear()
        self.state.raw_path_shift_history.clear()
        self.state.composite_history.clear()
        self.state.interpreted_history.clear()

    def _expand_schema(self, new_sensors: list[str]) -> None:
        if not new_sensors:
            return
        updated: deque[np.ndarray] = deque(maxlen=self.config.max_history)
        pad = np.full(shape=(len(new_sensors),), fill_value=np.nan, dtype=float)
        for row in self.state.vectors:
            updated.append(np.concatenate((row, pad)).astype(float, copy=False))
        self.state.vectors = updated
        self.state.sensor_order.extend(new_sensors)
        self.state.baseline_corr = None
        self.state.baseline_adj = None
        self._clear_reference_histories()
        self.logger.warning("sensor_schema_extended", extra={"new_sensors": new_sensors})

    def _ensure_sensor_order(self, frame: TelemetryFrame) -> None:
        frame_sensors = sorted(frame.sensor_values.keys())
        if not self.state.sensor_order:
            self.state.sensor_order = frame_sensors
            return
        current = set(self.state.sensor_order)
        incoming = set(frame_sensors)
        new_sensors = sorted(incoming - current)
        if new_sensors:
            self._expand_schema(new_sensors)

    def _vectorize(self, frame: TelemetryFrame) -> np.ndarray:
        vals: list[float] = []
        for s in self.state.sensor_order:
            v = frame.sensor_values.get(s)
            if v is None:
                vals.append(float("nan"))
            else:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    vals.append(float("nan"))
        return np.asarray(vals, dtype=float)

    def _history_windows(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        n = len(self.state.vectors)
        if n < self.config.recent_window:
            return None, None
        recent = np.vstack(list(self.state.vectors)[-self.config.recent_window :])
        if n >= self.config.baseline_window + self.config.recent_window:
            baseline = np.vstack(
                list(self.state.vectors)[
                    -(self.config.baseline_window + self.config.recent_window) : -self.config.recent_window
                ]
            )
        elif n >= self.config.baseline_window:
            baseline = np.vstack(list(self.state.vectors)[: self.config.baseline_window])
        else:
            baseline = np.vstack(list(self.state.vectors)[: self.config.recent_window])
        return baseline, recent

    def _classification_stability(self) -> float:
        if len(self.state.interpreted_history) < 2:
            return 1.0
        counts = Counter(self.state.interpreted_history)
        return float(max(counts.values())) / float(len(self.state.interpreted_history))

    def _trend(self) -> float:
        vals = np.asarray(list(self.state.composite_history), dtype=float)
        if vals.size < 6:
            return 0.0
        x = np.arange(vals.size, dtype=float)
        slope, _ = np.polyfit(x, vals, 1)
        return float(slope)

    @staticmethod
    def _risk_level_to_scalar(level: str) -> float:
        normalized = str(level or "").strip().lower()
        return {"low": 0.2, "medium": 0.6, "high": 0.9}.get(normalized, 0.35)

    @staticmethod
    def _trend_to_scalar(trend: str) -> float:
        normalized = str(trend or "").strip().lower()
        if normalized in {"increasing", "rising", "worsening", "up"}:
            return 1.0
        if normalized in {"flat", "stable", "uncertain", "drifting"}:
            return 0.5
        if normalized in {"decreasing", "falling", "improving", "down"}:
            return 0.25
        return 0.4

    def _smooth_risk_trend(self, raw_trend: str) -> str:
        trend = str(raw_trend or "uncertain").strip().lower() or "uncertain"
        self.state.risk_trend_history.append(trend)
        previous = str(self.state.smoothed_risk_trend or "uncertain").strip().lower()
        window = list(self.state.risk_trend_history)[-3:]
        votes = Counter(window)
        majority, majority_count = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
        opposing = {("increasing", "decreasing"), ("decreasing", "increasing")}

        smoothed = majority
        if (previous, majority) in opposing and majority_count < 2:
            smoothed = previous
        elif previous != majority and majority_count == 1:
            smoothed = previous
        self.state.smoothed_risk_trend = smoothed
        return smoothed

    @staticmethod
    def _avg_shortest_path_length(adj: np.ndarray) -> float:
        a = np.asarray(adj, dtype=float)
        if a.ndim != 2 or a.shape[0] != a.shape[1]:
            return 0.0
        n = int(a.shape[0])
        if n <= 1:
            return 0.0
        dist = np.full((n, n), np.inf, dtype=float)
        np.fill_diagonal(dist, 0.0)
        edge_idx = np.where(a > 0.0)
        dist[edge_idx] = 1.0
        for k in range(n):
            dist = np.minimum(dist, dist[:, [k]] + dist[[k], :])
        finite = dist[np.isfinite(dist) & (dist > 0.0)]
        if finite.size == 0:
            return 0.0
        return float(np.mean(finite))

    @staticmethod
    def _clamp01(value: float) -> float:
        return float(max(0.0, min(1.0, value)))

    def _score_from_reference(self, value: float, history: deque[float], fallback_scale: float) -> float:
        v = float(max(0.0, value))
        scale = max(1e-6, float(fallback_scale))
        if len(history) < 12:
            return self._clamp01(v / (v + scale))
        arr = np.asarray(history, dtype=float)
        q50 = float(np.percentile(arr, 50.0))
        q90 = float(np.percentile(arr, 90.0))
        if q90 <= q50 + 1e-6:
            return self._clamp01((v - q50) / (q50 + 1e-6))
        return self._clamp01((v - q50) / (q90 - q50))

    def _geometry_signature(self, mean_delta: np.ndarray, std_delta: np.ndarray, corr: np.ndarray, coherence: float) -> np.ndarray:
        corr_flat = flatten_upper(corr)
        return np.concatenate(
            [
                np.clip(mean_delta, -6.0, 6.0),
                np.clip(std_delta, -6.0, 6.0),
                np.clip(corr_flat, -1.0, 1.0),
                np.asarray([float(max(0.0, min(1.0, coherence)))], dtype=float),
            ]
        ).astype(float, copy=False)

    def _graph_signature(self, adjacency: np.ndarray, density: float, avg_degree: float, deformation: float) -> np.ndarray:
        adj = np.asarray(adjacency, dtype=float)
        n = int(adj.shape[0]) if adj.ndim == 2 else 0
        deg = np.sum(adj, axis=1) / max(1.0, float(n - 1)) if n > 1 else np.zeros((n,), dtype=float)
        avg_path = self._avg_shortest_path_length(adj)
        return np.concatenate(
            [
                np.asarray([float(density), float(avg_degree), float(avg_path), float(deformation)], dtype=float),
                np.asarray(deg, dtype=float),
            ]
        ).astype(float, copy=False)

    def _warmup_output(self, frame: TelemetryFrame) -> SIIResult:
        out: SIIResult = {
            "timestamp": frame.timestamp,
            "site_id": frame.site_id,
            "asset_id": frame.asset_id,
            "state": "STABLE",
            "interpreted_state": "NOMINAL_STRUCTURE",
            "confidence": "low",
            "structural_drift_score": 0.0,
            "relational_instability_score": 0.0,
            "regime_distance": 0.0,
            "coherence_score": 1.0,
            "graph_deformation_score": 0.0,
            "dominant_drivers": [],
            "confidence_reasoning": ["insufficient_history"],
            "explanation": "Warmup: awaiting multivariate relational history.",
            "read_only": True,
            "system_health": 100,
            "data_quality_summary": {
                "missingness_rate": 1.0,
                "sensor_coverage": 0.0,
                "timestamp_irregularity": 0.0,
                "gate_passed": False,
                "statuses": ["DATA_QUALITY_LIMITED"],
                "valid_signal_count": 0,
                "total_sensor_count": len(self.state.sensor_order),
            },
            "experimental_analytics": {
                "components": {},
                "raw_components": {},
                "graph_metrics": {},
                "regime": {},
                "context": None,
            },
            "attribution": {
                "status": "warming_up",
                "top_sensors": [],
                "top_relationships": [],
                "subsystem_impact": {"primary_cluster": "none", "clusters": []},
                "change_character": {"scope": "local", "tempo": "gradual"},
                "contribution_scores": {},
                "explanation": "Warmup: attribution unavailable until windows are populated.",
            },
            "regime_memory": {
                "status": "warming_up",
                "current_regime": "warmup",
                "nearest_matches": [],
                "best_similarity": 0.0,
                "confidence": 0.0,
                "is_novel": True,
            },
            "risk_assessment": {
                "status": "warming_up",
                "current_risk_level": "low",
                "projected_near_term_trend": "uncertain",
                "trajectory": "stabilizing",
                "risk_score": 0.0,
                "projected_score": 0.0,
                "evidence": {},
            },
            "operator_guidance": {
                "status": "warming_up",
                "concise_summary": "Warmup: insufficient history for structural attribution or risk projection.",
                "concern": "Insufficient history",
                "first_inspection_target": "none",
                "recommended_actions": ["Collect more telemetry to establish baseline and recent windows."],
            },
            "causal_analysis": {
                "status": "warming_up",
                "best_next_action": None,
                "recommended_sequence": [],
                "top_hypotheses": [],
                "validation_plan": [],
                "summary": "Warmup: causal prioritization unavailable until sufficient history is present.",
            },
            "structural_system_intelligence": {
                "status": "warming_up",
                "reason": "latent_state_unavailable_until_windows_are_populated",
            },
        }
        out["decision"] = resolve_best_action(
            attribution=out["attribution"],
            regime_memory=out["regime_memory"],
            risk_assessment=out["risk_assessment"],
            operator_guidance=out["operator_guidance"],
            causal_analysis=out["causal_analysis"],
            readiness={"ready": False, "reason": "Warmup window is incomplete."},
        )
        return out

    def _update_adaptive_baseline(
        self,
        *,
        recent_corr: np.ndarray,
        recent_adj: np.ndarray,
        decision_state: str,
        interpreted_state: str,
        dq_passed: bool,
    ) -> None:
        if self.state.baseline_corr is None:
            self.state.baseline_corr = np.asarray(recent_corr, dtype=float)
        if self.state.baseline_adj is None:
            self.state.baseline_adj = np.asarray(recent_adj, dtype=float)
        if self.state.baseline_corr is None or self.state.baseline_adj is None:
            return
        if self.state.processed_frames < self.config.freeze_baseline_frames:
            return
        if not dq_passed:
            return
        if decision_state != "STABLE" or interpreted_state != "NOMINAL_STRUCTURE":
            return
        alpha = float(self.config.baseline_adaptation_alpha)
        self.state.baseline_corr = alpha * self.state.baseline_corr + (1.0 - alpha) * np.asarray(recent_corr, dtype=float)
        smoothed_adj = alpha * self.state.baseline_adj + (1.0 - alpha) * np.asarray(recent_adj, dtype=float)
        self.state.baseline_adj = (smoothed_adj >= 0.5).astype(float)
        np.fill_diagonal(self.state.baseline_adj, 0.0)

    def _update_reference_histories(
        self,
        *,
        dq_passed: bool,
        decision_state: str,
        interpreted_state: str,
        raw_structural: float,
        raw_relational: float,
        raw_graph: float,
        raw_regime: float,
        raw_coherence_loss: float,
        raw_mean_shift: float,
        raw_cov_shift: float,
        raw_subspace_shift: float,
        raw_path_shift: float,
    ) -> None:
        if not dq_passed:
            return
        if decision_state != "STABLE" or interpreted_state != "NOMINAL_STRUCTURE":
            return
        self.state.raw_structural_history.append(float(max(0.0, raw_structural)))
        self.state.raw_relational_history.append(float(max(0.0, raw_relational)))
        self.state.raw_graph_history.append(float(max(0.0, raw_graph)))
        self.state.raw_regime_history.append(float(max(0.0, raw_regime)))
        self.state.raw_coherence_loss_history.append(float(max(0.0, raw_coherence_loss)))
        self.state.raw_mean_shift_history.append(float(max(0.0, raw_mean_shift)))
        self.state.raw_cov_shift_history.append(float(max(0.0, raw_cov_shift)))
        self.state.raw_subspace_shift_history.append(float(max(0.0, raw_subspace_shift)))
        self.state.raw_path_shift_history.append(float(max(0.0, raw_path_shift)))

    def close(self) -> None:
        self.regimes.save()
        self.logger.info("engine_closed", extra={"processed_frames": self.state.processed_frames})

    def process_frame(self, frame: TelemetryFrame) -> SIIResult:
        try:
            self._ensure_sensor_order(frame)
            frame_ts = self._to_float_timestamp(frame.timestamp, self.state.processed_frames)
            if self.state.timestamps and frame_ts < float(self.state.timestamps[-1]):
                self.logger.warning(
                    "out_of_order_frame_dropped",
                    extra={
                        "timestamp": frame.timestamp,
                        "last_timestamp": self.state.timestamps[-1],
                        "site_id": frame.site_id,
                        "asset_id": frame.asset_id,
                    },
                )
                dropped = self._warmup_output(frame)
                dropped["confidence_reasoning"] = list(
                    dict.fromkeys([*dropped.get("confidence_reasoning", []), "out_of_order_timestamp_dropped"])
                )
                dropped["explanation"] = (
                    "Dropped out-of-order telemetry frame to preserve deterministic windowed analysis."
                )
                dropped["data_quality_summary"] = {
                    **dropped.get("data_quality_summary", {}),
                    "statuses": ["TEMPORAL_IRREGULARITY", "FRAME_DROPPED"],
                    "gate_passed": False,
                }
                dropped["experimental_analytics"] = {
                    **dropped.get("experimental_analytics", {}),
                    "processing": {
                        "status": "warning",
                        "code": "out_of_order_timestamp_dropped",
                        "dropped": True,
                    },
                }
                dropped["decision"] = resolve_best_action(
                    attribution=dropped["attribution"],
                    regime_memory=dropped["regime_memory"],
                    risk_assessment=dropped["risk_assessment"],
                    operator_guidance=dropped["operator_guidance"],
                    causal_analysis=dropped["causal_analysis"],
                    readiness={"ready": False, "reason": "out_of_order_timestamp_dropped"},
                )
                return dropped

            vec = self._vectorize(frame)
            self.state.vectors.append(vec)
            self.state.timestamps.append(frame_ts)
            self.state.processed_frames += 1

            baseline, recent = self._history_windows()
            if baseline is None or recent is None:
                out = self._warmup_output(frame)
                self.state.interpreted_history.append(out["interpreted_state"])
                return out

            recent_ts = list(self.state.timestamps)[-recent.shape[0] :]
            dq = data_quality(recent, recent_timestamps=recent_ts)
            baseline_imp = impute_column_mean(baseline)
            recent_imp = impute_column_mean(recent)

            geom = build_geometry_state(
                baseline_imp,
                recent_imp,
                reference_corr=self.state.baseline_corr,
                dependence_backend=self.config.dependence_backend,
                dependence_lag=self.config.dependence_lag,
            )
            gstate = graph_state(
                geom.recent_corr,
                baseline_adj=self.state.baseline_adj,
                threshold=self.config.effective_graph_edge_threshold,
                feature_names=self.state.sensor_order,
            )

            if self.state.baseline_corr is None:
                self.state.baseline_corr = np.asarray(geom.baseline_corr, dtype=float)
            if self.state.baseline_adj is None:
                self.state.baseline_adj = np.asarray(gstate.adjacency, dtype=float)

            denom = np.abs(geom.baseline_std) + 1e-6
            mean_delta = (geom.recent_mean - geom.baseline_mean) / denom
            std_delta = (geom.recent_std - geom.baseline_std) / denom
            geometry_signature = self._geometry_signature(mean_delta, std_delta, geom.recent_corr, geom.coherence_score)
            graph_signature = self._graph_signature(
                gstate.adjacency,
                gstate.density,
                gstate.avg_degree,
                gstate.l1_deformation,
            )

            reg_assign = self.regimes.observe(
                RegimeObservation(
                    geometry_signature=np.asarray(geometry_signature, dtype=float),
                    graph_signature=np.asarray(graph_signature, dtype=float),
                    feature_names=list(self.state.sensor_order),
                )
            )

            baseline_path = (
                self._avg_shortest_path_length(self.state.baseline_adj)
                if self.state.baseline_adj is not None
                else self._avg_shortest_path_length(gstate.adjacency)
            )
            current_path = self._avg_shortest_path_length(gstate.adjacency)
            path_shift = abs(current_path - baseline_path)

            raw_structural = float(max(0.0, geom.structural_drift))
            raw_relational = float(max(0.0, geom.relational_instability))
            raw_graph = float(max(0.0, 0.70 * gstate.l1_deformation + 0.30 * path_shift))
            raw_regime = float(max(0.0, reg_assign.regime_distance))
            raw_coherence_loss = float(max(0.0, 1.0 - geom.coherence_score))
            raw_mean_shift = float(max(0.0, geom.mean_shift_norm))
            raw_cov_shift = float(max(0.0, geom.covariance_shift_norm))
            raw_subspace_shift = float(max(0.0, geom.subspace_rotation))

            structural_score = self._score_from_reference(raw_structural, self.state.raw_structural_history, fallback_scale=1.0)
            relational_score = self._score_from_reference(raw_relational, self.state.raw_relational_history, fallback_scale=0.35)
            graph_score = self._score_from_reference(raw_graph, self.state.raw_graph_history, fallback_scale=0.35)
            regime_score = self._score_from_reference(
                raw_regime,
                self.state.raw_regime_history,
                fallback_scale=max(0.25, float(self.config.regime_distance_threshold)),
            )
            coherence_loss_score = self._score_from_reference(
                raw_coherence_loss,
                self.state.raw_coherence_loss_history,
                fallback_scale=0.30,
            )
            mean_shift_score = self._score_from_reference(raw_mean_shift, self.state.raw_mean_shift_history, fallback_scale=0.45)
            cov_shift_score = self._score_from_reference(raw_cov_shift, self.state.raw_cov_shift_history, fallback_scale=0.45)
            subspace_shift_score = self._score_from_reference(
                raw_subspace_shift,
                self.state.raw_subspace_shift_history,
                fallback_scale=0.35,
            )
            path_shift_score = self._score_from_reference(path_shift, self.state.raw_path_shift_history, fallback_scale=0.35)
            coupling_score = self._clamp01(0.45 * relational_score + 0.35 * graph_score + 0.20 * coherence_loss_score)

            curr_degree = {name: float(np.sum(gstate.adjacency[idx]) / max(1.0, float(gstate.adjacency.shape[0] - 1))) for idx, name in enumerate(gstate.feature_names)}
            dyn_graph = compute_dynamic_graph_metrics(
                current_adj=np.asarray(gstate.adjacency, dtype=float),
                prev_adj=self.state.prev_graph_adj,
                current_degree_centrality=curr_degree,
                prev_degree_centrality=self.state.prev_degree_centrality,
                structural_drift=float(structural_score),
                coupling_score=float(coupling_score),
            )
            self.state.prev_graph_adj = np.asarray(gstate.adjacency, dtype=float)
            self.state.prev_degree_centrality = dict(curr_degree)

            components = {
                "structural_drift_score": structural_score,
                "relational_instability_score": relational_score,
                "regime_distance": regime_score,
                "coherence_loss_score": coherence_loss_score,
                "graph_deformation_score": graph_score,
                "coupling_instability_score": coupling_score,
            }
            component_extensions = {
                "mean_shift_score": mean_shift_score,
                "covariance_shift_score": cov_shift_score,
                "subspace_rotation_score": subspace_shift_score,
                "path_length_shift_score": path_shift_score,
            }

            indicators = StructuralIndicators(
                structural_drift_score=float(components["structural_drift_score"]),
                relational_instability_score=float(components["relational_instability_score"]),
                regime_distance=float(components["regime_distance"]),
                coherence_loss_score=float(components["coherence_loss_score"]),
                graph_deformation_score=float(components["graph_deformation_score"]),
                coupling_instability_score=float(components["coupling_instability_score"]),
                mean_shift_score=float(component_extensions["mean_shift_score"]),
                covariance_shift_score=float(component_extensions["covariance_shift_score"]),
                subspace_rotation_score=float(component_extensions["subspace_rotation_score"]),
                path_length_shift_score=float(component_extensions["path_length_shift_score"]),
            )
            composite = float(self.scoring.composite_departure_score(indicators))
            self.state.composite_history.append(composite)

            coherence_for_decision = self._clamp01(1.0 - coherence_loss_score)
            interpreted = map_to_interpreted_state(
                structural_drift=float(structural_score),
                relational_instability=float(relational_score),
                regime_distance=float(regime_score),
                coherence_score=float(coherence_for_decision),
                graph_instability=float(graph_score),
            )
            trend = self._trend()
            classification_stability = self._classification_stability()
            decision_state = map_decision_state_with_config(
                composite_score=float(composite),
                interpreted_state=interpreted,
                trend=trend,
                stability=classification_stability,
                config=self.config,
            )
            if not bool(dq.gate_passed):
                interpreted = "NOMINAL_STRUCTURE"
                decision_state = "STABLE"
            if self.state.processed_frames < int(self.config.min_samples_for_alerts):
                decision_state = "STABLE"

            self._update_adaptive_baseline(
                recent_corr=geom.recent_corr,
                recent_adj=gstate.adjacency,
                decision_state=decision_state,
                interpreted_state=interpreted,
                dq_passed=bool(dq.gate_passed),
            )
            self._update_reference_histories(
                dq_passed=bool(dq.gate_passed),
                decision_state=decision_state,
                interpreted_state=interpreted,
                raw_structural=raw_structural,
                raw_relational=raw_relational,
                raw_graph=raw_graph,
                raw_regime=raw_regime,
                raw_coherence_loss=raw_coherence_loss,
                raw_mean_shift=raw_mean_shift,
                raw_cov_shift=raw_cov_shift,
                raw_subspace_shift=raw_subspace_shift,
                raw_path_shift=path_shift,
            )

            conf = estimate_confidence(
                data_quality={
                    "missingness_rate": dq.missingness_rate,
                    "sensor_coverage": dq.sensor_coverage,
                    "timestamp_irregularity": dq.timestamp_irregularity,
                },
                component_scores=components,
                classification_stability=classification_stability,
                regime_support=float(reg_assign.regime_support),
            )
            confidence = confidence_to_level(float(conf.score))
            if not bool(dq.gate_passed):
                confidence = "low"
            if confidence not in ALLOWED_CONFIDENCE:
                confidence = "low"

            driver_scores = {**components, **component_extensions}
            driver_names = dominant_drivers(driver_scores, top_k=3)
            attribution = build_structural_attribution(
                sensor_names=list(self.state.sensor_order),
                baseline_corr=np.asarray(geom.baseline_corr, dtype=float),
                recent_corr=np.asarray(geom.recent_corr, dtype=float),
                baseline_adj=np.asarray(self.state.baseline_adj, dtype=float) if self.state.baseline_adj is not None else np.asarray(gstate.adjacency, dtype=float),
                recent_adj=np.asarray(gstate.adjacency, dtype=float),
                baseline_mean=np.asarray(geom.baseline_mean, dtype=float),
                recent_mean=np.asarray(geom.recent_mean, dtype=float),
                structural_score=float(structural_score),
                relational_score=float(relational_score),
                graph_score=float(graph_score),
                coupling_score=float(coupling_score),
                recent_composite=list(self.state.composite_history),
            )
            nearest_matches = self.regimes.nearest_matches(
                geometry_signature=np.asarray(geometry_signature, dtype=float),
                graph_signature=np.asarray(graph_signature, dtype=float),
                top_k=3,
            )
            regime_memory = summarize_regime_memory(
                current_regime=str(reg_assign.regime_name),
                nearest_matches=nearest_matches,
                threshold=float(self.config.regime_distance_threshold),
            )
            regime_confidence = round(float(max(regime_memory.confidence, reg_assign.regime_confidence)), 4)
            regime_uncertainty = round(float(reg_assign.regime_uncertainty), 4)
            risk_assessment_data = assess_forward_risk(
                composite_history=list(self.state.composite_history),
                structural_score=float(structural_score),
                regime_score=float(regime_score),
                coupling_score=float(coupling_score),
            )
            raw_risk_trend = str(risk_assessment_data.projected_near_term_trend)
            risk_trend_smoothed = self._smooth_risk_trend(raw_risk_trend)
            instant_risk_pressure = self._clamp01(
                0.45 * float(risk_assessment_data.projected_score)
                + 0.30 * self._risk_level_to_scalar(str(risk_assessment_data.current_risk_level))
                + 0.25 * self._trend_to_scalar(risk_trend_smoothed)
            )
            trend_reinforcement = 0.02 if risk_trend_smoothed == "increasing" else (0.005 if risk_trend_smoothed == "flat" else 0.0)
            self.state.cumulative_risk_pressure = round(
                self._clamp01(max(float(self.state.cumulative_risk_pressure) + trend_reinforcement, instant_risk_pressure)),
                4,
            )
            operator_guidance = build_operator_decision_support(
                interpreted_state=str(interpreted),
                decision_state=str(decision_state),
                confidence=str(confidence),
                attribution={
                    "top_sensors": attribution.top_sensors,
                    "top_relationships": attribution.top_relationships,
                    "subsystem_impact": attribution.subsystem_impact,
                    "change_character": attribution.change_character,
                    "contribution_scores": attribution.contribution_scores,
                    "explanation": attribution.explanation,
                },
                regime_memory={
                    "current_regime": regime_memory.current_regime,
                    "nearest_matches": regime_memory.nearest_matches,
                    "best_similarity": regime_memory.best_similarity,
                    "confidence": regime_confidence,
                    "uncertainty": regime_uncertainty,
                    "is_novel": regime_memory.is_novel,
                },
                risk_assessment={
                    "current_risk_level": risk_assessment_data.current_risk_level,
                    "projected_near_term_trend": risk_assessment_data.projected_near_term_trend,
                    "trajectory": risk_assessment_data.trajectory,
                    "risk_score": risk_assessment_data.risk_score,
                    "projected_score": risk_assessment_data.projected_score,
                    "evidence": risk_assessment_data.evidence,
                },
            )
            law_support: dict[str, Any] | None = None

            top_sensors = attribution.top_sensors if isinstance(attribution.top_sensors, list) else []
            attribution_sensor_names = [
                str(item.get("sensor", "")).strip()
                for item in top_sensors
                if isinstance(item, dict) and str(item.get("sensor", "")).strip()
            ]
            primary_causal_drivers = attribution_sensor_names[:3] or (driver_names[:3] if driver_names else ["dominant subsystem"])
            attribution_set = set(attribution_sensor_names[:5])
            causal_set = set(primary_causal_drivers)
            overlap_score = self._clamp01(len(attribution_set & causal_set) / max(1, len(causal_set)))
            hypo = score_structural_hypothesis(
                leading_sensor=primary_causal_drivers[0] if primary_causal_drivers else "dominant subsystem",
                localization=float(structural_score),
                persistence=float(min(1.0, np.mean(np.asarray(list(self.state.composite_history)[-6:], dtype=float) > 0.55))) if self.state.composite_history else 0.0,
                subsystem_coherence=float(max(0.0, min(1.0, geom.coherence_score))),
                robustness=float(max(0.0, min(1.0, 1.0 - abs(structural_score - relational_score)))),
                multi_signal_agreement=float(overlap_score),
            )
            top_hypothesis = {
                "hypothesis": hypo.hypothesis,
                "confidence": hypo.confidence,
                "evidence_strength": hypo.evidence_strength,
                "robustness": hypo.robustness,
                "counterfactual_strength": round(float(max(0.0, min(1.0, 0.5 * coupling_score + 0.5 * graph_score))), 4),
                "primary_drivers": primary_causal_drivers,
                "score_breakdown": dict(hypo.score_breakdown),
            }
            validation_plan = [
                {
                    "rank": 1,
                    "step": str(operator_guidance.recommended_actions[0]) if operator_guidance.recommended_actions else "Inspect leading subsystem",
                    "expected_voi": round(float(max(0.05, min(1.0, 0.55 + 0.35 * structural_score))), 4),
                },
                {
                    "rank": 2,
                    "step": "Validate top sensor calibration and strongest relationship pair.",
                    "expected_voi": round(float(max(0.05, min(1.0, 0.35 + 0.35 * relational_score))), 4),
                },
            ]
            causal_analysis = {
                "status": "ready",
                "best_next_action": {
                    "action": str(operator_guidance.recommended_actions[0]) if operator_guidance.recommended_actions else "Inspect subsystem",
                    "target": str(operator_guidance.first_inspection_target or "none"),
                    "priority": 1,
                    "confidence": round(float(max(0.0, min(1.0, 0.5 * top_hypothesis["confidence"] + 0.5 * risk_assessment_data.projected_score))), 4),
                },
                "recommended_sequence": [
                    {
                        "action": str(a),
                        "target": str(operator_guidance.first_inspection_target or "none"),
                        "priority": idx + 1,
                    }
                    for idx, a in enumerate(operator_guidance.recommended_actions[:3])
                ],
                "top_hypotheses": [top_hypothesis],
                "primary_drivers": primary_causal_drivers,
                "attribution_causal_overlap_score": round(float(overlap_score), 4),
                "validation_plan": validation_plan,
                "summary": "Deterministic causal prioritization built from structural drift, coupling, and near-term risk trend.",
            }
            intelligence_observation = {
                "asset_id": frame.asset_id,
                "structural_drift_score": structural_score,
                "relational_instability_score": relational_score,
                "regime_distance": regime_score,
                "graph_deformation_score": graph_score,
                "coherence_score": geom.coherence_score,
                "coupling_instability_score": coupling_score,
                "risk_pressure": self.state.cumulative_risk_pressure,
                "path_length_shift": path_shift,
                "subspace_rotation": raw_subspace_shift,
                "mean_shift": raw_mean_shift,
                "covariance_shift": raw_cov_shift,
                "composite_instability": composite,
                "contribution_scores": attribution.contribution_scores,
                "top_relationships": attribution.top_relationships,
                "subsystem_impact": attribution.subsystem_impact,
            }
            structural_intelligence = self.intelligence.update(intelligence_observation)
            self.state.intelligence_history.append(structural_intelligence)
            law_support = structural_intelligence.get("law_engine_decision") if isinstance(structural_intelligence, dict) else None
            law_adjusted_risk = None
            if isinstance(law_support, dict):
                law_adjusted_risk = law_support.get("law_adjusted_risk")
                if isinstance(law_adjusted_risk, (int, float)):
                    risk_assessment_data = risk_assessment_data.__class__(
                        current_risk_level=risk_assessment_data.current_risk_level,
                        projected_near_term_trend=risk_assessment_data.projected_near_term_trend,
                        trajectory=risk_assessment_data.trajectory,
                        risk_score=risk_assessment_data.risk_score,
                        projected_score=max(
                            0.0,
                            min(1.0, float(risk_assessment_data.projected_score) + 0.5 * float(law_support.get("law_risk_delta", 0.0))),
                        ),
                        evidence={
                            **dict(risk_assessment_data.evidence),
                            "law_influence_weight": round(float(law_support.get("law_influence_weight", 0.0)), 4),
                            "law_risk_delta": round(float(law_support.get("law_risk_delta", 0.0)), 4),
                        },
                    )
                    if law_support.get("law_informed_recommendations"):
                        operator_guidance = operator_guidance.__class__(
                            concise_summary=f"{operator_guidance.concise_summary} {law_support.get('law_layer_message', '')}".strip(),
                            concern=operator_guidance.concern,
                            first_inspection_target=operator_guidance.first_inspection_target,
                            recommended_actions=list(law_support.get("law_informed_recommendations") or operator_guidance.recommended_actions),
                        )
                    causal_analysis["law_linked_interventions"] = list(law_support.get("law_linked_interventions") or [])
            context = None
            if self.config.allow_context_provider:
                try:
                    snap = self.context_provider.snapshot(
                        {
                            "timestamp": frame.timestamp,
                            "site_id": frame.site_id,
                            "asset_id": frame.asset_id,
                            "sensor_values": frame.sensor_values,
                        }
                    )
                    context = None if snap is None else {"source": snap.source, "payload": snap.payload}
                except Exception:
                    self.logger.exception("context_provider_snapshot_failed")
                    context = None

            system_health = int(max(0.0, min(100.0, 100.0 - (composite * 55.0))))
            out: SIIResult = {
                "timestamp": frame.timestamp,
                "site_id": frame.site_id,
                "asset_id": frame.asset_id,
                "state": decision_state,
                "interpreted_state": interpreted,
                "confidence": confidence,
                "structural_drift_score": round(float(structural_score), 4),
                "relational_instability_score": round(float(relational_score), 4),
                "regime_distance": round(float(regime_score), 4),
                "coherence_score": round(float(geom.coherence_score), 4),
                "graph_deformation_score": round(float(graph_score), 4),
                "dominant_drivers": driver_names,
                "confidence_reasoning": list(conf.reasoning),
                "explanation": build_explanation_text(
                    interpreted_state=interpreted,
                    decision_state=decision_state,
                    dominant=driver_names,
                    confidence_reasoning=list(conf.reasoning),
                ),
                "read_only": True,
                "system_health": system_health,
                "attribution": {
                    "status": "ready",
                    "top_sensors": attribution.top_sensors,
                    "top_relationships": attribution.top_relationships,
                    "subsystem_impact": attribution.subsystem_impact,
                    "change_character": attribution.change_character,
                    "contribution_scores": attribution.contribution_scores,
                    "explanation": attribution.explanation,
                },
                "regime_memory": {
                    "status": "ready",
                    "current_regime": regime_memory.current_regime,
                    "nearest_matches": regime_memory.nearest_matches,
                    "best_similarity": regime_memory.best_similarity,
                    "confidence": regime_confidence,
                    "uncertainty": regime_uncertainty,
                    "is_novel": regime_memory.is_novel,
                },
                "risk_assessment": {
                    "status": "ready",
                    "current_risk_level": risk_assessment_data.current_risk_level,
                    "projected_near_term_trend": risk_assessment_data.projected_near_term_trend,
                    "risk_trend_smoothed": risk_trend_smoothed,
                    "trajectory": risk_assessment_data.trajectory,
                    "risk_score": risk_assessment_data.risk_score,
                    "projected_score": risk_assessment_data.projected_score,
                    "cumulative_risk_pressure": self.state.cumulative_risk_pressure,
                    "evidence": risk_assessment_data.evidence,
                    "base_risk": (law_support or {}).get("base_risk") if isinstance(law_support, dict) else None,
                    "law_adjusted_risk": (law_support or {}).get("law_adjusted_risk") if isinstance(law_support, dict) else None,
                    "law_risk_delta": (law_support or {}).get("law_risk_delta") if isinstance(law_support, dict) else None,
                    "law_influence_weight": (law_support or {}).get("law_influence_weight") if isinstance(law_support, dict) else None,
                    "confidence_adjustment": (law_support or {}).get("confidence_adjustment") if isinstance(law_support, dict) else None,
                },
                "operator_guidance": {
                    "status": "ready",
                    "concise_summary": operator_guidance.concise_summary,
                    "concern": operator_guidance.concern,
                    "first_inspection_target": operator_guidance.first_inspection_target,
                    "recommended_actions": operator_guidance.recommended_actions,
                    "law_layer_message": (law_support or {}).get("law_layer_message") if isinstance(law_support, dict) else None,
                    "matched_law_ids": (law_support or {}).get("matched_law_ids") if isinstance(law_support, dict) else [],
                },
                "causal_analysis": causal_analysis,
                "structural_system_intelligence": structural_intelligence,
                "data_quality_summary": summarize_quality(dq),
                "experimental_analytics": {
                    "components": {k: round(float(v), 6) for k, v in components.items()},
                    "component_extensions": {k: round(float(v), 6) for k, v in component_extensions.items()},
                    "raw_components": {
                        "structural_drift": round(raw_structural, 6),
                        "relational_instability": round(raw_relational, 6),
                        "graph_deformation": round(raw_graph, 6),
                        "regime_distance": round(raw_regime, 6),
                        "coherence_loss": round(raw_coherence_loss, 6),
                        "mean_shift": round(raw_mean_shift, 6),
                        "covariance_shift": round(raw_cov_shift, 6),
                        "subspace_rotation": round(raw_subspace_shift, 6),
                        "path_length_shift": round(path_shift, 6),
                    },
                    "composite_instability": round(composite, 6),
                    "geometry": {
                        "mean_shift_norm": round(float(geom.mean_shift_norm), 6),
                        "covariance_shift_norm": round(float(geom.covariance_shift_norm), 6),
                        "subspace_rotation": round(float(geom.subspace_rotation), 6),
                        "coherence_score": round(float(geom.coherence_score), 6),
                        "dependence_backend": str(self.config.dependence_backend),
                        "dependence_lag": int(self.config.dependence_lag),
                    },
                    "graph_metrics": {
                        "density": round(float(gstate.density), 6),
                        "avg_degree": round(float(gstate.avg_degree), 6),
                        "path_length": round(float(current_path), 6),
                        "path_length_shift": round(float(path_shift), 6),
                        "deformation": round(float(gstate.l1_deformation), 6),
                        "edge_persistence": dyn_graph.edge_persistence,
                        "edge_birth_rate": dyn_graph.edge_birth_rate,
                        "edge_death_rate": dyn_graph.edge_death_rate,
                        "centrality_shift": dyn_graph.centrality_shift,
                        "dynamic_fragility": dyn_graph.fragility_score,
                    },
                    "regime": {
                        "name": reg_assign.regime_name,
                        "distance": reg_assign.regime_distance,
                        "geometry_distance": reg_assign.geometry_distance,
                        "graph_distance": reg_assign.graph_distance,
                        "pending": not bool(reg_assign.regime_activated),
                        "support": reg_assign.regime_support,
                        "confidence": reg_assign.regime_confidence,
                        "uncertainty": reg_assign.regime_uncertainty,
                    },
                    "context": context,
                    "processing": {
                        "status": "success" if bool(dq.gate_passed) else "warning",
                        "code": "data_quality_gate_passed" if bool(dq.gate_passed) else "data_quality_gate_failed",
                        "dropped": False,
                    },
                },
            }
            out["decision"] = resolve_best_action(
                attribution=out["attribution"],
                regime_memory=out["regime_memory"],
                risk_assessment=out["risk_assessment"],
                operator_guidance=out["operator_guidance"],
                causal_analysis=out.get("causal_analysis"),
                readiness={"ready": True, "reason": "engine_ready"},
                decision_context=self.state.decision_hysteresis_state,
            )
            if isinstance(out.get("decision"), dict):
                if isinstance(law_support, dict):
                    out["decision"]["law_decision_trace"] = law_support.get("law_decision_trace")
                    out["decision"]["law_influence_weight"] = law_support.get("law_influence_weight")
                    out["decision"]["matched_law_ids"] = law_support.get("matched_law_ids")
                next_hysteresis = out["decision"].get("hysteresis_state")
                if isinstance(next_hysteresis, dict):
                    self.state.decision_hysteresis_state = dict(next_hysteresis)
            if out["state"] not in ALLOWED_STATES:
                out["state"] = "STABLE"
            if out["interpreted_state"] not in ALLOWED_INTERPRETED_STATES:
                out["interpreted_state"] = "NOMINAL_STRUCTURE"
            self.state.interpreted_history.append(out["interpreted_state"])
            if self.state.processed_frames % 25 == 0:
                self.regimes.save()
            return out
        except SIIError:
            raise
        except Exception as exc:
            self.logger.exception("frame_processing_failure")
            raise SIIProcessingError(
                f"Failed to process telemetry frame safely for asset={frame.asset_id!r} "
                f"site={frame.site_id!r} timestamp={frame.timestamp!r}"
            ) from exc

    def process_payload(self, payload: dict[str, Any]) -> SIIResult:
        record = canonical_records_from_payloads(
            [payload],
            source_type="payload",
            source_name="engine_process_payload",
        )[0]
        return self.process_record(record)

    def process_record(self, record: CanonicalIngestionRecord) -> SIIResult:
        return self.process_frame(ingestion_record_to_frame(record))

    def process_records(self, records: list[CanonicalIngestionRecord]) -> list[SIIResult]:
        return [self.process_record(record) for record in records]

    def process_csv_text(self, csv_text: str) -> list[SIIResult]:
        frames = frames_from_csv(csv_text)
        return [self.process_frame(f) for f in frames]


SIIEngine = SystemicInfrastructureIntelligenceEngine
