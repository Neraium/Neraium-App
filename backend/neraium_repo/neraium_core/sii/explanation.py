from __future__ import annotations

from typing import Mapping


def dominant_drivers(components: Mapping[str, float], top_k: int = 3) -> list[str]:
    ranked = sorted(components.items(), key=lambda kv: float(kv[1]), reverse=True)
    return [name for name, _ in ranked[: max(1, int(top_k))]]


def build_explanation_text(
    *,
    interpreted_state: str,
    decision_state: str,
    dominant: list[str],
    confidence_reasoning: list[str],
) -> str:
    driver_text = ", ".join(dominant) if dominant else "no dominant structural drivers"
    reason_text = ", ".join(confidence_reasoning) if confidence_reasoning else "no confidence factors"
    return (
        f"{interpreted_state} / {decision_state}: multivariate relational geometry and graph topology "
        f"indicate structural regime departure characteristics. Dominant contributors: {driver_text}. "
        f"Confidence evidence: {reason_text}. Read-only instrumentation output."
    )


# Backward-compatible alias
build_explanation = build_explanation_text

