"""Action-type governance on top of decision validity."""

from __future__ import annotations

from dataclasses import dataclass, field


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(slots=True)
class ActionValidityAssessment:
    action_type: str
    validity: bool
    confidence: float
    fragility: float
    reason: str
    invalidation_conditions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "action_type": self.action_type,
            "validity": self.validity,
            "confidence": self.confidence,
            "fragility": self.fragility,
            "reason": self.reason,
            "invalidation_conditions": self.invalidation_conditions,
        }


@dataclass(slots=True)
class ActionGovernanceInput:
    regime: str
    state: str
    action_permission: str
    validity_score: float
    confidence_score: float
    fragility_score: float
    structural_drift_score: float
    instability_score: float
    transition_state: str
    abstain: bool
    invalidation_conditions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionGovernanceResult:
    allowed_actions: list[dict[str, object]]
    blocked_actions: list[dict[str, object]]
    best_action: str
    action_quality: dict[str, float]
    action_notes: dict[str, str]


def _score_action(base_score: float, fragility_score: float, extra_penalty: float = 0.0) -> tuple[float, float]:
    quality = _clamp(base_score - 0.35 * fragility_score - extra_penalty)
    confidence = _clamp(0.55 * base_score + 0.45 * (1.0 - fragility_score) - extra_penalty)
    return quality, confidence


def evaluate_action_governance(data: ActionGovernanceInput) -> ActionGovernanceResult:
    invalidators = data.invalidation_conditions
    assessments: list[ActionValidityAssessment] = []
    action_quality: dict[str, float] = {}
    action_notes: dict[str, str] = {}

    aggressive_block = data.transition_state == "transition" or data.action_permission in {"REDUCE", "AVOID"}
    trend_friendly = data.regime in {"trend", "crowded_trend"} and data.state in {"stable", "drifting", "restabilizing"}
    mean_reverting = data.regime == "mean_reversion" and data.state in {"stable", "restabilizing"}
    defensive = data.regime in {"risk_off_transition", "liquidity_stress", "high_vol_transition", "fragile_rally"}

    def register(action_type: str, validity: bool, base_score: float, reason: str, extra_penalty: float = 0.0) -> None:
        quality, confidence = _score_action(base_score, data.fragility_score, extra_penalty=extra_penalty)
        if not validity:
            quality = min(quality, 0.35)
            confidence = min(confidence, 0.45)
        action_quality[action_type] = quality
        action_notes[action_type] = reason
        assessments.append(
            ActionValidityAssessment(
                action_type=action_type,
                validity=validity,
                confidence=confidence,
                fragility=data.fragility_score,
                reason=reason,
                invalidation_conditions=invalidators[:4],
            )
        )

    register(
        "breakout_entry",
        validity=(not aggressive_block and trend_friendly and data.confidence_score > 0.60 and data.validity_score > 0.58),
        base_score=0.80 if trend_friendly else 0.35,
        reason="Best when the market is coherent, stable, and trend-backed.",
        extra_penalty=0.20 if aggressive_block else 0.0,
    )
    register(
        "trend_continuation",
        validity=(not aggressive_block and trend_friendly and data.confidence_score > 0.55),
        base_score=0.76 if trend_friendly else 0.30,
        reason="Valid when trend structure persists without active transition stress.",
        extra_penalty=0.10 if data.state == "drifting" else 0.0,
    )
    register(
        "mean_reversion",
        validity=(not aggressive_block and mean_reverting and data.structural_drift_score < 0.42),
        base_score=0.72 if mean_reverting else 0.25,
        reason="Requires contained drift and a stable mean-reverting regime.",
        extra_penalty=0.12 if data.structural_drift_score > 0.35 else 0.0,
    )
    register(
        "add_to_position",
        validity=(data.action_permission == "ACT" and not aggressive_block and data.fragility_score < 0.45),
        base_score=0.70 if data.action_permission == "ACT" else 0.20,
        reason="Only justified when the original edge remains robust enough to scale.",
        extra_penalty=0.25 if data.fragility_score > 0.45 else 0.0,
    )
    register(
        "reduce_position",
        validity=(data.action_permission in {"REDUCE", "AVOID"} or data.fragility_score > 0.58 or defensive),
        base_score=0.82 if (defensive or data.fragility_score > 0.58) else 0.40,
        reason="Useful when fragility rises or the system shifts into defensive conditions.",
    )
    register(
        "exit_position",
        validity=(data.action_permission == "AVOID" or defensive or data.instability_score > 0.72),
        base_score=0.88 if (data.action_permission == "AVOID" or defensive) else 0.45,
        reason="Reserved for invalid, stressed, or clearly breaking structures.",
    )
    register(
        "hold_only",
        validity=(data.action_permission == "WAIT" and not defensive),
        base_score=0.66 if data.action_permission == "WAIT" else 0.25,
        reason="Appropriate when structure is not invalid, but not actionable enough to expand risk.",
    )
    register(
        "no_action",
        validity=(data.abstain or data.action_permission in {"WAIT", "AVOID"}),
        base_score=0.90 if data.abstain else 0.40,
        reason="The default safe action whenever the engine does not grant valid exposure.",
    )

    allowed = [assessment.as_dict() for assessment in assessments if assessment.validity]
    blocked = [assessment.as_dict() for assessment in assessments if not assessment.validity]
    best_action = "no_action"
    if allowed:
        best_action = max(allowed, key=lambda item: float(action_quality[item["action_type"]]))["action_type"]  # type: ignore[arg-type]

    return ActionGovernanceResult(
        allowed_actions=allowed,
        blocked_actions=blocked,
        best_action=best_action,
        action_quality=action_quality,
        action_notes=action_notes,
    )
