from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .types import ConfidenceLevel


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    level: ConfidenceLevel
    reasoning: list[str]
    quality_factor: float
    evidence_factor: float


def confidence_to_level(score: float) -> ConfidenceLevel:
    s = float(max(0.0, min(1.0, score)))
    if s >= 0.7:
        return "high"
    if s >= 0.4:
        return "medium"
    return "low"


def estimate_confidence(
    *,
    data_quality: Mapping[str, float | int | bool | list[str]],
    component_scores: Mapping[str, float],
    classification_stability: float,
    regime_support: float,
) -> ConfidenceResult:
    missingness = float(data_quality.get("missingness_rate", 1.0) or 1.0)
    coverage = float(data_quality.get("sensor_coverage", 0.0) or 0.0)
    irregularity = float(data_quality.get("timestamp_irregularity", 1.0) or 1.0)

    quality = max(0.0, min(1.0, (1.0 - missingness) * coverage * (1.0 - irregularity)))
    vals = [max(0.0, float(v)) for v in component_scores.values()]
    if vals:
        mean_v = sum(vals) / len(vals)
        spread = (sum((v - mean_v) ** 2 for v in vals) / len(vals)) ** 0.5
        spread_consistency = max(0.0, min(1.0, 1.0 - spread / (mean_v + 1e-6)))
        evidence_strength = max(0.0, min(1.0, mean_v))
        evidence = 0.6 * spread_consistency + 0.4 * evidence_strength
    else:
        evidence = 0.0

    stability = max(0.0, min(1.0, float(classification_stability)))
    regime = max(0.0, min(1.0, float(regime_support)))

    score = 0.45 * quality + 0.25 * evidence + 0.20 * stability + 0.10 * regime
    score = max(0.0, min(1.0, score))

    reasons: list[str] = []
    if missingness > 0.2:
        reasons.append("elevated_missingness")
    if coverage < 0.7:
        reasons.append("limited_sensor_coverage")
    if irregularity > 0.2:
        reasons.append("timestamp_irregularity")
    if stability < 0.6:
        reasons.append("classification_volatility")
    if regime < 0.4:
        reasons.append("limited_regime_history")
    if not reasons:
        reasons.append("strong_structural_evidence_consistency")

    return ConfidenceResult(
        score=score,
        level=confidence_to_level(score),
        reasoning=reasons,
        quality_factor=quality,
        evidence_factor=evidence,
    )
