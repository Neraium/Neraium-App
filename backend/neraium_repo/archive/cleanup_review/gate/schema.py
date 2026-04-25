from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CriterionStatus = Literal["PASS", "FAIL", "INSUFFICIENT"]
GateDecisionLabel = Literal["ADMIT", "SUPPRESS", "ADMISSIBILITY_VOID"]


@dataclass(frozen=True)
class CriterionResult:
    name: str
    status: CriterionStatus
    reason: str


@dataclass(frozen=True)
class GateInput:
    timestamp: float | str
    asset_id: str
    site_id: str | None = None
    drift_score: float | None = None
    stability_score: float | None = None
    coherence_score: float | None = None
    snr_score: float | None = None
    persistence_minutes: float | None = None
    corroborating_signal_count: int | None = None
    context_flags: dict[str, bool] = field(default_factory=dict)
    candidate_assertion: str | None = None
    raw_metrics: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    current: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None
    system_state: dict[str, Any] | None = None


@dataclass(frozen=True)
class GateDecision:
    decision: GateDecisionLabel
    doctrine_version: str
    criteria_results: dict[str, str]
    refusal_reason: str | None
    explanation: str
    observed_facts: list[str]
    uncertainty_notes: list[str]
    candidate_assertion_allowed: bool
    confidence_label: str


@dataclass(frozen=True)
class GateProfile:
    min_drift_for_admit: float = 0.60
    max_stability_for_admit: float = 0.40
    min_coherence_for_admit: float = 0.65
    min_snr_for_admit: float = 1.50
    min_persistence_minutes_for_admit: float = 15.0
    min_corroborating_signals_for_admit: int = 2
    void_if_coherence_below: float = 0.25
    void_if_snr_below: float = 0.45
    void_if_conflict_margin: float = 0.50
