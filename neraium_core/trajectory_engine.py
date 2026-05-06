"""Forward-only trajectory inference utilities for Neraium."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np


RELATIONSHIP_PAIRS = (
    ("rms", "crest_factor"),
    ("kurtosis", "peak"),
    ("skewness", "kurtosis"),
)


@dataclass(frozen=True)
class TrajectorySnapshot:
    current_path: str
    velocity: float
    acceleration: float
    confidence: float
    persistence: float
    variance: float


class NeraiumTrajectoryEngine:
    def __init__(self, smoothing_window: int = 5, persistence_window: int = 12) -> None:
        self.smoothing_window = max(int(smoothing_window), 1)
        self.persistence_window = max(int(persistence_window), 3)
        self._drift_history: List[float] = []
        self._velocity_history: List[float] = []

    def update(self, structural_drift_score: float) -> TrajectorySnapshot:
        drift = float(np.clip(structural_drift_score, 0.0, 1.0))
        previous_drift = self._drift_history[-1] if self._drift_history else drift
        raw_velocity = drift - previous_drift
        previous_velocity = self._velocity_history[-1] if self._velocity_history else raw_velocity
        raw_acceleration = raw_velocity - previous_velocity

        self._drift_history.append(drift)
        self._velocity_history.append(raw_velocity)

        velocity = self._smooth(self._velocity_history)
        accelerations = np.diff(np.asarray(self._velocity_history, dtype=float))
        acceleration = self._smooth(accelerations)
        if len(self._velocity_history) == 1:
            acceleration = raw_acceleration

        recent = np.asarray(self._drift_history[-self.persistence_window :], dtype=float)
        recent_velocities = np.asarray(self._velocity_history[-self.persistence_window :], dtype=float)
        persistence = float(np.mean(recent_velocities > 0.0)) if recent_velocities.size else 0.0
        variance = float(np.var(recent)) if recent.size else 0.0
        current_path = classify_trajectory(drift, velocity, acceleration)
        confidence = trajectory_confidence(persistence, variance, len(self._drift_history))

        return TrajectorySnapshot(
            current_path=current_path,
            velocity=float(velocity),
            acceleration=float(acceleration),
            confidence=float(confidence),
            persistence=float(persistence),
            variance=float(variance),
        )

    def seed(self, drift_history: Iterable[float]) -> TrajectorySnapshot:
        snapshot = TrajectorySnapshot("STABLE", 0.0, 0.0, 0.0, 0.0, 0.0)
        for drift in drift_history:
            snapshot = self.update(float(drift))
        return snapshot

    def _smooth(self, values: Iterable[float]) -> float:
        arr = np.asarray(list(values), dtype=float)
        if arr.size == 0:
            return 0.0
        window = min(self.smoothing_window, arr.size)
        return float(np.mean(arr[-window:]))


def classify_trajectory(drift: float, velocity: float, acceleration: float) -> str:
    if drift < 0.12 and abs(velocity) < 0.01:
        return "STABLE"
    if velocity < -0.01:
        return "RECOVERY"
    if drift >= 0.85 and acceleration > 0.0:
        return "LOCK_IN"
    if velocity > 0.0 or drift >= 0.12:
        return "DEGRADATION"
    return "STABLE"


def infer_future_paths(snapshot: TrajectorySnapshot, drift: float) -> List[Dict[str, object]]:
    velocity = float(snapshot.velocity)
    acceleration = float(snapshot.acceleration)
    persistence = float(snapshot.persistence)
    variance = float(snapshot.variance)

    recovery = 0.18
    degradation = 0.44
    lock_in = 0.18

    if velocity < 0:
        recovery += min(0.45, abs(velocity) * 8.0)
        degradation -= 0.10
    if velocity > 0:
        degradation += min(0.30, velocity * 8.0)
    if acceleration > 0 and persistence >= 0.55:
        lock_in += min(0.35, acceleration * 10.0 + persistence * 0.20)
    if drift >= 0.60:
        degradation += 0.15
    if drift >= 0.85 and acceleration > 0:
        lock_in += 0.25
    if variance > 0.05:
        recovery += 0.05

    values = np.asarray([max(recovery, 0.01), max(degradation, 0.01), max(lock_in, 0.01)], dtype=float)
    values = values / float(np.sum(values))
    return [
        {
            "path": "RECOVERY",
            "conditions": "drift velocity turns negative and remains below the confirmation band",
            "likelihood": round(float(values[0]), 3),
        },
        {
            "path": "DEGRADATION",
            "conditions": "structural drift persists or continues rising across incoming windows",
            "likelihood": round(float(values[1]), 3),
        },
        {
            "path": "LOCK_IN",
            "conditions": "positive acceleration persists after actionability is confirmed",
            "likelihood": round(float(values[2]), 3),
        },
    ]


def trajectory_confidence(persistence: float, variance: float, sample_count: int) -> float:
    history_factor = min(float(sample_count) / 30.0, 1.0)
    variance_penalty = min(variance * 2.0, 0.25)
    confidence = 0.35 + 0.35 * persistence + 0.25 * history_factor - variance_penalty
    return float(np.clip(confidence, 0.0, 0.95))


def confidence_level(confidence: float) -> str:
    if confidence >= 0.72:
        return "HIGH"
    if confidence >= 0.45:
        return "MEDIUM"
    return "LOW"


def rank_feature_deviations(
    features: Optional[Dict[str, float]],
    baseline_means: Optional[Dict[str, float]],
    baseline_stds: Optional[Dict[str, float]],
) -> List[Dict[str, object]]:
    if not features or not baseline_means or not baseline_stds:
        return []
    rows: List[Dict[str, object]] = []
    for key, value in features.items():
        if key not in baseline_means or key not in baseline_stds:
            continue
        std = max(float(baseline_stds[key]), abs(float(baseline_means[key])) * 0.05, 1e-6)
        score = abs(float(value) - float(baseline_means[key])) / std
        rows.append({"feature": key, "deviation": round(float(score), 3)})
    rows.sort(key=lambda row: float(row["deviation"]), reverse=True)
    return rows[:3]


def infer_relationship_shifts(
    features: Optional[Dict[str, float]],
    baseline_means: Optional[Dict[str, float]],
    baseline_stds: Optional[Dict[str, float]],
) -> List[str]:
    if not features or not baseline_means or not baseline_stds:
        return []
    scores: Dict[str, float] = {}
    for key, value in features.items():
        if key not in baseline_means or key not in baseline_stds:
            continue
        std = max(float(baseline_stds[key]), abs(float(baseline_means[key])) * 0.05, 1e-6)
        scores[key] = abs(float(value) - float(baseline_means[key])) / std
    relationship_scores: List[tuple[float, str]] = []
    for left, right in RELATIONSHIP_PAIRS:
        left_score = scores.get(left)
        right_score = scores.get(right)
        if left_score is None or right_score is None:
            continue
        relationship_scores.append(((left_score + right_score) / 2.0, f"{left} <-> {right}"))
    relationship_scores.sort(key=lambda row: row[0], reverse=True)
    return [label for _, label in relationship_scores[:3]]
