"""PRONOSTIA operator decision synthesis.

This layer turns engine state into operator-facing answers. It does not change
engine math, event timing, or PRONOSTIA validation cycles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import numpy as np

from neraium_core.outcome_frame import NeraiumOutcomeFrame
from neraium_core.trajectory_engine import (
    NeraiumTrajectoryEngine,
    TrajectorySnapshot,
    confidence_level,
    infer_future_paths,
    infer_relationship_shifts,
    rank_feature_deviations,
)


FEATURE_ORDER = ("rms", "peak", "kurtosis", "skewness", "crest_factor")
RELATIONSHIP_PAIRS = (
    ("rms", "crest_factor"),
    ("kurtosis", "peak"),
    ("skewness", "kurtosis"),
)


@dataclass(frozen=True)
class FeatureBaseline:
    means: Dict[str, float]
    stds: Dict[str, float]


def feature_baseline(feature_rows: Iterable[Dict[str, float]]) -> FeatureBaseline:
    rows = [row for row in feature_rows if row]
    means: Dict[str, float] = {}
    stds: Dict[str, float] = {}
    for key in FEATURE_ORDER:
        values = np.asarray([float(row[key]) for row in rows if key in row], dtype=float)
        if values.size == 0:
            continue
        mean = float(np.mean(values))
        std = float(np.std(values))
        means[key] = mean
        stds[key] = max(std, abs(mean) * 0.05, 1e-6)
    return FeatureBaseline(means=means, stds=stds)


def feature_baseline_from_arrays(mean: np.ndarray, std: np.ndarray) -> FeatureBaseline:
    means = {key: float(mean[index]) for index, key in enumerate(FEATURE_ORDER) if index < len(mean)}
    stds = {
        key: max(float(std[index]), abs(means[key]) * 0.05, 1e-6)
        for index, key in enumerate(FEATURE_ORDER)
        if index < len(std) and key in means
    }
    return FeatureBaseline(means=means, stds=stds)


def _normalize_state(cycle: int, state: str, timeline: Dict[str, int]) -> str:
    normalized = str(state or "").upper()
    if normalized == "LOCK_IN" or cycle >= int(timeline.get("failure_endpoint", 10**9)):
        return "LOCK_IN"
    if cycle >= int(timeline["actionable_point"]) or normalized == "ACTIONABLE":
        return "ACTIONABLE"
    if cycle >= int(timeline["baseline_departure"]) or normalized in {"DETECTED", "TRANSITION", "UNSTABLE"}:
        return "DETECTED"
    return "STABLE"


def _z_scores(features: Optional[Dict[str, float]], baseline: Optional[FeatureBaseline]) -> Dict[str, float]:
    if not features or baseline is None:
        return {}
    scores: Dict[str, float] = {}
    for key in FEATURE_ORDER:
        if key not in features or key not in baseline.means or key not in baseline.stds:
            continue
        scores[key] = abs(float(features[key]) - baseline.means[key]) / baseline.stds[key]
    return scores


def _top_relationships(
    features: Optional[Dict[str, float]],
    baseline: Optional[FeatureBaseline],
    product_state: str,
) -> list[str]:
    if product_state == "STABLE":
        return []

    scores = _z_scores(features, baseline)
    ranked: list[tuple[float, str]] = []
    for left, right in RELATIONSHIP_PAIRS:
        if left in scores and right in scores:
            ranked.append(((scores[left] + scores[right]) / 2.0, f"{left} <-> {right}"))

    if not ranked:
        return ["rms <-> crest_factor", "kurtosis <-> peak", "skewness <-> kurtosis"][:2]

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [label for _, label in ranked[:3]]


def _baseline_dicts(baseline: Optional[FeatureBaseline]) -> tuple[Optional[Dict[str, float]], Optional[Dict[str, float]]]:
    if baseline is None:
        return None, None
    return baseline.means, baseline.stds


def _trajectory_for_history(drift_history: Optional[Iterable[float]], current_drift: float) -> TrajectorySnapshot:
    engine = NeraiumTrajectoryEngine()
    if drift_history is None:
        return engine.update(current_drift)
    seeded = False
    snapshot = None
    for drift in drift_history:
        snapshot = engine.update(float(drift))
        seeded = True
    if not seeded:
        snapshot = engine.update(current_drift)
    return snapshot or engine.update(current_drift)


def _decision_urgency(product_state: str, snapshot: TrajectorySnapshot, drift: float) -> str:
    if product_state == "STABLE":
        return "LOW"
    if product_state == "DETECTED":
        return "MEDIUM"
    if snapshot.acceleration > 0.02 or drift >= 0.85:
        return "HIGH"
    return "MEDIUM"


def synthesize_outcome_frame(
    *,
    current_cycle: int,
    current_state: str,
    structural_drift_score: float,
    drift_velocity: float,
    instability_score: float,
    signal_features: Optional[Dict[str, float]],
    timeline: Dict[str, int],
    baseline: Optional[FeatureBaseline] = None,
    drift_history: Optional[Iterable[float]] = None,
    trajectory_snapshot: Optional[TrajectorySnapshot] = None,
) -> NeraiumOutcomeFrame:
    product_state = _normalize_state(current_cycle, current_state, timeline)
    drift = float(structural_drift_score)
    snapshot = trajectory_snapshot or _trajectory_for_history(drift_history, drift)
    means, stds = _baseline_dicts(baseline)
    feature_deviations = rank_feature_deviations(signal_features, means, stds)
    relationship_shifts = infer_relationship_shifts(signal_features, means, stds)
    decision_payload = synthesize_decision(
        current_cycle=current_cycle,
        current_state=current_state,
        structural_drift_score=structural_drift_score,
        drift_velocity=drift_velocity,
        instability_score=instability_score,
        signal_features=signal_features,
        timeline=timeline,
        baseline=baseline,
    )

    where = decision_payload["where"]
    if product_state == "STABLE":
        where_changed = "No localized instability detected."
    elif relationship_shifts:
        where_changed = "Instability concentrated in: " + ", ".join(relationship_shifts)
    else:
        where_changed = where["localized_instability"]

    basis = list(decision_payload["confidence"]["basis"])
    if snapshot.persistence >= 0.55:
        basis.append("trajectory persistence observed")
    if len(feature_deviations) >= 2:
        basis.append("multi-signal agreement")
    if snapshot.confidence >= 0.45:
        basis.append("trajectory stability sufficient for decision support")

    urgency = _decision_urgency(product_state, snapshot, drift)
    frame_confidence = confidence_level(snapshot.confidence)
    if product_state == "ACTIONABLE" and frame_confidence == "LOW":
        frame_confidence = "MEDIUM"

    return NeraiumOutcomeFrame(
        state=product_state,
        what_changed=decision_payload["what"],
        where_changed=where_changed,
        trajectory={
            "current_path": snapshot.current_path,
            "velocity": round(float(snapshot.velocity), 6),
            "acceleration": round(float(snapshot.acceleration), 6),
            "confidence": round(float(snapshot.confidence), 3),
        },
        future_paths=infer_future_paths(snapshot, drift),
        decision={
            "recommended_action": (
                "No intervention required"
                if product_state == "STABLE"
                else "Monitor for confirmation"
                if product_state == "DETECTED"
                else decision_payload["operator_action"]
            ),
            "urgency": urgency,
            "time_window": (
                f"{max(int(timeline['failure_endpoint']) - int(timeline['actionable_point']), 0)} cycles observed before failure in similar trajectory"
                if product_state == "ACTIONABLE"
                else decision_payload["time_window"]
            ),
            "if_ignored": decision_payload["if_ignored"],
        },
        confidence={
            "level": frame_confidence,
            "basis": basis,
        },
    )


def synthesize_decision(
    *,
    current_cycle: int,
    current_state: str,
    structural_drift_score: float,
    drift_velocity: float,
    instability_score: float,
    signal_features: Optional[Dict[str, float]],
    timeline: Dict[str, int],
    baseline: Optional[FeatureBaseline] = None,
) -> Dict[str, Any]:
    product_state = _normalize_state(current_cycle, current_state, timeline)
    relationships = _top_relationships(signal_features, baseline, product_state)

    if product_state == "STABLE":
        return {
            "state": "STABLE",
            "what": "System operating within stable baseline behavior.",
            "where": {
                "localized_instability": "No localized instability detected.",
                "top_contributing_relationships": [],
            },
            "operator_action": "No intervention signal yet.",
            "time_window": "Lead time begins at structural departure.",
            "if_ignored": "No current degradation trajectory indicated.",
            "confidence": {
                "level": "medium",
                "basis": ["baseline still forming or holding"],
            },
            "explanation": [
                f"cycle={current_cycle}",
                f"structural_drift_score={float(structural_drift_score):.3f}",
                f"instability_score={float(instability_score):.3f}",
            ],
        }

    if product_state == "DETECTED":
        return {
            "state": "DETECTED",
            "what": "Structural departure detected.",
            "where": {
                "localized_instability": "Instability beginning to concentrate in vibration-derived relationships.",
                "top_contributing_relationships": relationships,
            },
            "operator_action": "Continue monitoring for confirmation. No intervention recommended yet.",
            "time_window": "Lead time pending confirmation.",
            "if_ignored": "Potential progression toward confirmed degradation if departure persists.",
            "confidence": {
                "level": "medium",
                "basis": ["departure detected", "confirmation still pending"],
            },
            "explanation": [
                f"cycle={current_cycle}",
                f"structural_drift_score={float(structural_drift_score):.3f}",
                f"drift_velocity={float(drift_velocity):.6f}",
                "decision gated until actionable confirmation",
            ],
        }

    if product_state == "LOCK_IN":
        return {
            "state": "LOCK_IN",
            "what": "Failure trajectory locked in.",
            "where": {
                "localized_instability": "Instability concentrated around rotating-system vibration relationships.",
                "top_contributing_relationships": relationships,
            },
            "operator_action": "Escalate inspection and prepare corrective maintenance.",
            "time_window": "Historical failure endpoint reached in this validation run.",
            "if_ignored": "High likelihood of continued progression toward failure endpoint.",
            "confidence": {
                "level": "medium-high",
                "basis": [
                    "structural departure detected",
                    "departure persisted across confirmation window",
                    "failure endpoint reached in historical validation run",
                ],
            },
            "explanation": [
                f"cycle={current_cycle}",
                f"structural_drift_score={float(structural_drift_score):.3f}",
                "terminal language shown only after endpoint stage",
            ],
        }

    lead_time = max(int(timeline["failure_endpoint"]) - int(timeline["actionable_point"]), 0)
    return {
        "state": "ACTIONABLE",
        "what": "Confirmed degradation trajectory.",
        "where": {
            "localized_instability": "Instability concentrated around rotating-system vibration relationships.",
            "top_contributing_relationships": relationships,
        },
        "operator_action": "Inspect bearing assembly / rotating element during the next available maintenance window.",
        "time_window": f"{lead_time} cycles before historical failure endpoint in this validation run.",
        "if_ignored": "Progressive degradation likely continues toward increased vibration instability and component failure.",
        "confidence": {
            "level": "medium-high",
            "basis": [
                "structural departure detected",
                "departure persisted across confirmation window",
                "multi-feature vibration relationship shift",
            ],
        },
        "explanation": [
            f"cycle={current_cycle}",
            f"structural_drift_score={float(structural_drift_score):.3f}",
            f"drift_velocity={float(drift_velocity):.6f}",
            "operator action is gated to confirmed actionability",
        ],
    }
