from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegimeSimilaritySummary:
    current_regime: str
    nearest_matches: list[dict[str, Any]]
    best_similarity: float
    confidence: float
    is_novel: bool


def summarize_regime_memory(
    *,
    current_regime: str,
    nearest_matches: list[dict[str, Any]],
    threshold: float,
) -> RegimeSimilaritySummary:
    matches = [dict(m) for m in nearest_matches]
    if not matches:
        return RegimeSimilaritySummary(
            current_regime=current_regime,
            nearest_matches=[],
            best_similarity=0.0,
            confidence=0.0,
            is_novel=True,
        )

    best = float(matches[0].get("similarity", 0.0))
    top_two = matches[:2]
    conf = float(sum(float(m.get("similarity", 0.0)) for m in top_two) / max(1, len(top_two)))
    is_novel = bool(best < 0.55)
    # Force novelty when best absolute distance exceeds threshold-derived scale.
    best_dist = float(matches[0].get("distance", 1e9))
    if best_dist > float(threshold):
        is_novel = True

    return RegimeSimilaritySummary(
        current_regime=current_regime,
        nearest_matches=matches,
        best_similarity=round(best, 4),
        confidence=round(max(0.0, min(1.0, conf)), 4),
        is_novel=is_novel,
    )
