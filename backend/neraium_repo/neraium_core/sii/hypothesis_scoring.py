from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HypothesisScore:
    hypothesis: str
    evidence_strength: float
    confidence: float
    robustness: float
    score_breakdown: dict[str, float]


def score_structural_hypothesis(
    *,
    leading_sensor: str,
    localization: float,
    persistence: float,
    subsystem_coherence: float,
    robustness: float,
    multi_signal_agreement: float,
) -> HypothesisScore:
    evidence = max(
        0.0,
        min(
            1.0,
            0.28 * localization
            + 0.22 * persistence
            + 0.18 * subsystem_coherence
            + 0.18 * robustness
            + 0.14 * multi_signal_agreement,
        ),
    )
    confidence = max(0.0, min(1.0, 0.75 * evidence + 0.25 * robustness))
    return HypothesisScore(
        hypothesis=f"Localized structural drift centered on {leading_sensor}.",
        evidence_strength=round(evidence, 4),
        confidence=round(confidence, 4),
        robustness=round(max(0.0, min(1.0, robustness)), 4),
        score_breakdown={
            "localization": round(localization, 4),
            "persistence": round(persistence, 4),
            "subsystem_coherence": round(subsystem_coherence, 4),
            "robustness": round(robustness, 4),
            "multi_signal_agreement": round(multi_signal_agreement, 4),
        },
    )
