from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from neraium_core.features.window_feature_extractor import summarize_feature_delta


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def bounded_z(raw: float, mean: float, std: float, cap: float = 4.0) -> float:
    denom = max(1e-6, float(std))
    z = (float(raw) - float(mean)) / denom
    return clamp(float(z), 0.0, cap)


def corr_from_matrix(m: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(m.T)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def flatten_upper_tri(m: np.ndarray) -> np.ndarray:
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        return np.array([], dtype=float)
    idx = np.triu_indices(m.shape[0], k=1)
    return m[idx]


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return float(default)
        return f
    except (TypeError, ValueError):
        return float(default)


@dataclass
class NodeBaselineProfile:
    corr_baseline: np.ndarray | None = None
    corr_drift_mean: float = 0.0
    corr_drift_std: float = 0.1
    relational_mean: float = 0.0
    relational_std: float = 0.1
    temporal_gap_mean: float = 1.0
    temporal_gap_std: float = 0.1
    instability_mean: float = 0.0
    instability_std: float = 0.1
    finalized: bool = False


@dataclass
class RegimeMemory:
    centroids: list[np.ndarray] = field(default_factory=list)
    threshold: float = 2.0

    def nearest_distance(self, signature: np.ndarray) -> float:
        if not self.centroids:
            return 0.0
        dists = [float(np.linalg.norm(signature - c)) for c in self.centroids if c.shape == signature.shape]
        if not dists:
            return 0.0
        return float(min(dists))

    def update(self, signature: np.ndarray) -> float:
        if not self.centroids:
            self.centroids.append(signature.copy())
            return 0.0
        nearest = self.nearest_distance(signature)
        if nearest > self.threshold:
            self.centroids.append(signature.copy())
        return nearest


@dataclass
class NodeRuntime:
    node: str
    variant: str
    sensor_names: list[str]
    baseline_window: int
    recent_window: int
    values_history: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=500))
    timestamp_history: deque[float] = field(default_factory=lambda: deque(maxlen=500))
    score_history: deque[float] = field(default_factory=lambda: deque(maxlen=120))
    interpreted_history: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    baseline_profile: NodeBaselineProfile = field(default_factory=NodeBaselineProfile)
    regime_memory: RegimeMemory = field(default_factory=RegimeMemory)
    _baseline_corr_drift: list[float] = field(default_factory=list)
    _baseline_relational: list[float] = field(default_factory=list)
    _baseline_graph: list[float] = field(default_factory=list)
    _baseline_gap: list[float] = field(default_factory=list)
    _baseline_instability: list[float] = field(default_factory=list)

    def push(self, ts: float, sensors: dict[str, float]) -> np.ndarray:
        vec = np.array([safe_float(sensors.get(s), np.nan) for s in self.sensor_names], dtype=float)
        self.values_history.append(vec)
        self.timestamp_history.append(ts)
        return vec

    def recent_matrix(self) -> np.ndarray | None:
        if len(self.values_history) < self.recent_window:
            return None
        m = np.vstack(list(self.values_history)[-self.recent_window :])
        if np.isnan(m).any():
            col_mean = np.nanmean(m, axis=0)
            col_mean = np.nan_to_num(col_mean, nan=0.0)
            inds = np.where(np.isnan(m))
            m[inds] = np.take(col_mean, inds[1])
        return m

    def baseline_matrix(self) -> np.ndarray | None:
        if len(self.values_history) < self.baseline_window:
            return None
        m = np.vstack(list(self.values_history)[: self.baseline_window])
        if np.isnan(m).any():
            col_mean = np.nanmean(m, axis=0)
            col_mean = np.nan_to_num(col_mean, nan=0.0)
            inds = np.where(np.isnan(m))
            m[inds] = np.take(col_mean, inds[1])
        return m

    def recent_timestamps(self) -> list[float] | None:
        if len(self.timestamp_history) < self.recent_window:
            return None
        return list(self.timestamp_history)[-self.recent_window :]

    def baseline_timestamps(self) -> list[float] | None:
        if len(self.timestamp_history) < self.baseline_window:
            return None
        return list(self.timestamp_history)[: self.baseline_window]


class DataQualityStage:
    @staticmethod
    def evaluate(
        baseline: np.ndarray,
        recent: np.ndarray,
        ts_base: list[float] | None,
        ts_recent: list[float] | None,
    ) -> dict[str, float | bool | list[str]]:
        _ = baseline
        _ = ts_base
        n_total = int(recent.size)
        miss = int(np.isnan(recent).sum())
        missingness_rate = float(miss / max(1, n_total))
        std_recent = np.nanstd(recent, axis=0)
        std_recent = np.nan_to_num(std_recent, nan=0.0)
        flatlined = int(np.sum(std_recent <= 1e-12))
        valid_signal_count = int(np.sum(std_recent > 1e-12))
        total_sensors = int(recent.shape[1])
        sensor_coverage = float(valid_signal_count / max(1, total_sensors))
        timestamp_irregularity = 0.0
        if ts_recent is not None and len(ts_recent) >= 3:
            gaps = np.diff(np.array(ts_recent, dtype=float))
            if np.all(gaps > 0):
                timestamp_irregularity = float(np.std(gaps) / (np.mean(gaps) + 1e-9))
        timestamp_irregularity = float(clamp(timestamp_irregularity, 0.0, 1.0))
        statuses: list[str] = []
        if missingness_rate > 0.5:
            statuses.append("DATA_QUALITY_LIMITED")
        if sensor_coverage < 0.5:
            statuses.append("LOW_SENSOR_COVERAGE")
        if timestamp_irregularity > 0.5:
            statuses.append("TIMESTAMP_IRREGULAR")
        gate_passed = bool(missingness_rate <= 0.5 and sensor_coverage >= 0.5 and valid_signal_count >= 2)
        return {
            "missingness_rate": missingness_rate,
            "timestamp_irregularity": timestamp_irregularity,
            "flatlined_sensor_count": flatlined,
            "valid_signal_count": valid_signal_count,
            "total_sensors": total_sensors,
            "sensor_coverage": sensor_coverage,
            "statuses": statuses,
            "gate_passed": gate_passed,
        }


class FeatureExtractionStage:
    @staticmethod
    def extract(baseline: np.ndarray, recent: np.ndarray) -> dict[str, Any]:
        base_mean = np.mean(baseline, axis=0)
        rec_mean = np.mean(recent, axis=0)
        base_std = np.std(baseline, axis=0)
        rec_std = np.std(recent, axis=0)
        corr_base = corr_from_matrix(baseline)
        corr_recent = corr_from_matrix(recent)
        rel_vec_base = flatten_upper_tri(corr_base)
        rel_vec_recent = flatten_upper_tri(corr_recent)
        signature = np.concatenate([rec_mean, rec_std, rel_vec_recent])
        rich = summarize_feature_delta(baseline, recent)
        return {
            "base_mean": base_mean,
            "rec_mean": rec_mean,
            "base_std": base_std,
            "rec_std": rec_std,
            "corr_base": corr_base,
            "corr_recent": corr_recent,
            "rel_vec_base": rel_vec_base,
            "rel_vec_recent": rel_vec_recent,
            "signature": signature,
            "rich_signal_features": rich,
        }


class StructuralDriftStage:
    @staticmethod
    def score(features: dict[str, Any], baseline_profile: NodeBaselineProfile) -> tuple[float, float]:
        corr_recent = features["corr_recent"]
        corr_ref = baseline_profile.corr_baseline if baseline_profile.corr_baseline is not None else features["corr_base"]
        raw = float(np.linalg.norm(corr_recent - corr_ref, ord="fro"))
        normalized = raw
        if baseline_profile.finalized:
            normalized = bounded_z(raw, baseline_profile.corr_drift_mean, baseline_profile.corr_drift_std, cap=4.0)
        return raw, normalized


class RelationalInstabilityStage:
    @staticmethod
    def score(features: dict[str, Any], baseline_profile: NodeBaselineProfile) -> tuple[float, float]:
        delta = features["rel_vec_recent"] - features["rel_vec_base"]
        raw = float(np.mean(np.abs(delta))) if delta.size else 0.0
        normalized = raw
        if baseline_profile.finalized:
            normalized = bounded_z(raw, baseline_profile.relational_mean, baseline_profile.relational_std, cap=4.0)
        return raw, normalized


class TemporalCoherenceStage:
    @staticmethod
    def score(ts_recent: list[float] | None, baseline_profile: NodeBaselineProfile) -> tuple[float, float]:
        if ts_recent is None or len(ts_recent) < 3:
            return 0.0, 0.0
        gaps = np.diff(np.array(ts_recent, dtype=float))
        if not np.all(gaps > 0):
            return 1.0, 3.0
        cv = float(np.std(gaps) / (np.mean(gaps) + 1e-9))
        raw = float(clamp(cv, 0.0, 5.0))
        normalized = raw
        if baseline_profile.finalized:
            normalized = bounded_z(raw, baseline_profile.temporal_gap_mean, baseline_profile.temporal_gap_std, cap=4.0)
        return raw, normalized


class RegimeStage:
    @staticmethod
    def distance(runtime: NodeRuntime, signature: np.ndarray) -> float:
        return runtime.regime_memory.update(signature)


class ConfidenceStage:
    @staticmethod
    def score(
        dq: dict[str, Any],
        component_scores: dict[str, float],
        score_history: deque[float],
        baseline_profile: NodeBaselineProfile,
    ) -> float:
        quality = (1.0 - float(dq["missingness_rate"])) * float(dq["sensor_coverage"]) * (
            1.0 - float(dq["timestamp_irregularity"])
        )
        quality = clamp(quality, 0.0, 1.0)
        if len(score_history) >= 6:
            recent = np.array(list(score_history)[-6:], dtype=float)
            persistence = float(np.mean(recent > 1.0))
            volatility = float(np.std(recent))
        else:
            persistence = 0.0
            volatility = 0.0
        vals = np.array(list(component_scores.values()), dtype=float)
        spread = float(np.std(vals) / (np.mean(vals) + 1e-6)) if vals.size else 1.0
        agreement = clamp(1.0 - 0.5 * spread, 0.0, 1.0)
        if baseline_profile.finalized:
            baseline_std = max(0.05, baseline_profile.instability_std)
            distance_factor = clamp(float(np.mean(vals)) / (2.0 * baseline_std + 1e-6), 0.0, 1.0)
        else:
            distance_factor = 0.3
        conf = (
            0.35 * quality
            + 0.20 * agreement
            + 0.20 * clamp(1.0 - volatility, 0.0, 1.0)
            + 0.15 * clamp(persistence, 0.0, 1.0)
            + 0.10 * distance_factor
        )
        return clamp(conf, 0.0, 1.0)

    @staticmethod
    def categorical(conf: float) -> str:
        if conf >= 0.70:
            return "high"
        if conf >= 0.40:
            return "medium"
        return "low"


class LocalizationStage:
    @staticmethod
    def compute(anomaly_evidence_by_node: dict[str, float]) -> dict[str, float]:
        vals = np.array([max(0.0, float(v)) for v in anomaly_evidence_by_node.values()], dtype=float)
        s = float(np.sum(vals))
        if s <= 1e-9:
            return {k: 0.0 for k in anomaly_evidence_by_node.keys()}
        shares = {k: float(v) / s for k, v in anomaly_evidence_by_node.items()}
        concentration = float(np.max(vals) / (s + 1e-9))
        return {k: clamp(shares[k] * concentration * 2.0, 0.0, 1.0) for k in anomaly_evidence_by_node.keys()}


class DecisionStage:
    @staticmethod
    def interpreted_state(
        structural: float,
        relational: float,
        regime_distance: float,
        temporal_distortion: float,
        localization: float,
        trend: float,
    ) -> str:
        motion = structural > 1.2 or relational > 1.0
        strong_coupling_break = relational > 1.4
        regime_shift = regime_distance > 0.8
        sustained_degrading = trend > 0.03
        if strong_coupling_break and localization > 0.25:
            return "COUPLING_INSTABILITY_OBSERVED"
        if motion and regime_shift and sustained_degrading and localization > 0.20:
            return "STRUCTURAL_INSTABILITY_OBSERVED"
        if motion and regime_shift and not sustained_degrading:
            return "REGIME_SHIFT_OBSERVED"
        if motion and temporal_distortion > 1.0 and localization < 0.20:
            return "COHERENCE_UNDER_CONSTRAINT"
        return "NOMINAL_STRUCTURE"

    @staticmethod
    def state_from_score(instability: float, confidence: float, localization: float) -> str:
        loc_gate = 0.40 + 0.60 * localization
        conf_gate = 0.55 + 0.45 * confidence
        adjusted = instability * loc_gate * conf_gate
        if localization < 0.16 and confidence < 0.55 and adjusted < 2.6:
            return "STABLE"
        if adjusted >= 2.0:
            return "ALERT"
        if adjusted >= 1.0:
            return "WATCH"
        return "STABLE"

    @staticmethod
    def adjusted_instability(instability: float, confidence: float, localization: float) -> float:
        """Same inner product as state_from_score (instability × loc_gate × conf_gate), exposed for calibration."""
        loc_gate = 0.40 + 0.60 * float(localization)
        conf_gate = 0.55 + 0.45 * float(confidence)
        return float(max(0.0, float(instability) * loc_gate * conf_gate))


# Minimum baseline samples before switching from global DecisionStage to per-node quantile triage.
MIN_BASELINE_SAMPLES_FOR_CALIBRATION = 28


def decision_adjusted_score(instability: float, confidence: float, localization: float) -> float:
    """Alias for DecisionStage.adjusted_instability - benchmark / diagnostics naming."""
    return DecisionStage.adjusted_instability(instability, confidence, localization)


def adaptive_gal2_fusion_coherence(
    temporal_coherence: float,
    gal2_timing_distortion_index: float,
    *,
    enabled: bool = True,
) -> float:
    """
    Adaptive GAL-2 calibration for SII+GAL-2 *fusion* paths.

    Under disturbed clocks, raw temporal_coherence is often low while GAL-2 still reports
    meaningful timing distortion. Multiplicative fusion terms (instability × coherence) then
    collapse and the Combined lane is underpowered. This blends in a bounded, distortion-driven
    coupling term: higher distortion raises effective coherence only where coherence was weak,
    preserving strong-coherent regimes unchanged.

    Toggle at call sites (e.g. env NERAIUM_ADAPTIVE_GAL2_FUSION) - not a global threshold hack.
    """
    if not enabled:
        return float(clamp(temporal_coherence, 0.0, 1.0))
    tc = float(clamp(temporal_coherence, 0.0, 1.0))
    g = float(clamp(gal2_timing_distortion_index, 0.0, 1.0))
    # Distortion acts as a second, complementary signal when coherence alone is pessimistic
    return float(clamp(tc + 0.45 * g * (1.0 - tc), 0.0, 1.0))


def state_from_node_quantiles(dec_adj: float, watch_thr: float, alert_thr: float) -> str:
    """Data-driven triage from a node's own baseline score distribution (no shared global cut)."""
    w = float(watch_thr)
    a = float(alert_thr)
    if a <= w:
        a = w + max(1e-6, 0.01 * (abs(w) + 1.0))
    x = float(dec_adj)
    if x <= w:
        return "STABLE"
    if x <= a:
        return "WATCH"
    return "ALERT"


def decide_state_with_calibration(
    *,
    phase: str,
    adj: float,
    confidence: float,
    localization: float,
    dec_adj: float,
    baseline_dec_adj_prior: list[float],
    frozen_watch_alert: tuple[float, float] | None,
) -> tuple[str, str]:
    """
    Returns (state, decision_mode).

    After burn-in, baseline uses quantiles of *this node's prior* adjusted scores; after baseline,
    perturbation/recovery use frozen quantiles from the full baseline window for that node so
    variant-specific score paths produce variant-specific stability statistics.
    """
    if phase == "baseline":
        if len(baseline_dec_adj_prior) < MIN_BASELINE_SAMPLES_FOR_CALIBRATION:
            return DecisionStage.state_from_score(adj, confidence, localization), "global_fallback"
        arr = np.asarray(baseline_dec_adj_prior, dtype=float)
        w_thr = float(np.percentile(arr, 82.0))
        a_thr = float(np.percentile(arr, 93.5))
        return state_from_node_quantiles(dec_adj, w_thr, a_thr), "online_baseline_quantile"
    if frozen_watch_alert is not None:
        w_thr, a_thr = frozen_watch_alert
        return state_from_node_quantiles(dec_adj, w_thr, a_thr), "frozen_post_baseline_quantile"
    return DecisionStage.state_from_score(adj, confidence, localization), "global_fallback"


class AttributionStage:
    @staticmethod
    def explain(components: dict[str, float], state: str) -> tuple[str, dict[str, float]]:
        total = sum(max(0.0, v) for v in components.values()) + 1e-9
        contrib = {k: max(0.0, v) / total for k, v in components.items()}
        ranked = sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
        top = [k for k, _ in ranked[:3]]
        msg = f"{state}: dominated by {', '.join(top)}." if top else f"{state}: no dominant structural drivers."
        return msg, contrib

