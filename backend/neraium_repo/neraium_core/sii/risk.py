from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ForwardRiskAssessment:
    current_risk_level: str
    projected_near_term_trend: str
    trajectory: str
    risk_score: float
    projected_score: float
    evidence: dict[str, float]


def _risk_level(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _markov_transition_probabilities(series: np.ndarray) -> dict[str, float]:
    # latent states in escalating order
    labels = ["stable", "drift", "unstable"]
    bins = np.digitize(series, [0.45, 0.72], right=False)
    counts = np.ones((3, 3), dtype=float)  # Laplace smoothing
    for i in range(len(bins) - 1):
        counts[int(bins[i]), int(bins[i + 1])] += 1.0
    trans = counts / np.sum(counts, axis=1, keepdims=True)
    curr = int(bins[-1]) if bins.size else 0
    one_step = trans[curr]
    two_step = one_step @ trans
    return {
        f"p_next_{labels[i]}": float(one_step[i]) for i in range(3)
    } | {
        "p_escalate_2step": float(two_step[2]),
        "state_entropy": float(-np.sum(one_step * np.log(one_step + 1e-12)) / np.log(3.0)),
    }


def assess_forward_risk(
    *,
    composite_history: list[float],
    structural_score: float,
    regime_score: float,
    coupling_score: float,
) -> ForwardRiskAssessment:
    arr = np.asarray(composite_history[-24:], dtype=float)
    if arr.size < 4:
        score = float(max(structural_score, regime_score, coupling_score))
        return ForwardRiskAssessment(
            current_risk_level=_risk_level(score),
            projected_near_term_trend="uncertain",
            trajectory="stabilizing",
            risk_score=round(score, 4),
            projected_score=round(score, 4),
            evidence={"trend": 0.0, "hazard": 0.0, "uncertainty": 1.0},
        )

    x = np.arange(arr.size, dtype=float)
    slope, _ = np.polyfit(x, arr, 1)
    slope = float(slope)
    recent_diff = np.diff(arr)
    accel = float(np.mean(recent_diff[-4:])) if recent_diff.size else 0.0
    persistence = float(np.mean(arr[-8:] > 0.55)) if arr.size >= 8 else float(np.mean(arr > 0.55))

    current = float(0.56 * arr[-1] + 0.22 * structural_score + 0.22 * coupling_score)
    trans = _markov_transition_probabilities(arr)
    hazard = max(0.0, min(1.0, 0.45 * trans["p_next_unstable"] + 0.35 * trans["p_escalate_2step"] + 0.20 * persistence))
    projected = float(max(0.0, min(1.0, 0.52 * current + 0.30 * hazard + 0.10 * regime_score + 0.08 * max(0.0, slope * 8.0 + accel * 4.0))))

    uncertainty = float(max(0.0, min(1.0, 0.65 * trans["state_entropy"] + 0.35 * (1.0 - min(1.0, arr.size / 24.0)))))

    if hazard >= 0.62 or slope > 0.015:
        trend = "increasing"
        trajectory = "deteriorating"
        projected = max(projected, current)
    elif hazard <= 0.35 and slope < -0.010:
        trend = "decreasing"
        trajectory = "stabilizing"
    else:
        trend = "flat"
        trajectory = "drifting"

    return ForwardRiskAssessment(
        current_risk_level=_risk_level(current),
        projected_near_term_trend=trend,
        trajectory=trajectory,
        risk_score=round(max(0.0, min(1.0, current)), 4),
        projected_score=round(projected, 4),
        evidence={
            "trend": round(slope, 6),
            "acceleration": round(accel, 6),
            "persistence": round(persistence, 6),
            "hazard": round(hazard, 6),
            "uncertainty": round(uncertainty, 6),
            **{k: round(v, 6) for k, v in trans.items()},
        },
    )
