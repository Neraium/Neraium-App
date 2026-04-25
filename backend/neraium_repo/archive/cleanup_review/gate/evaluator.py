from __future__ import annotations

from typing import Iterable

from neraium_core.doctrine import DoctrineAssessment, assess_assertion
from neraium_core.gate.schema import CriterionResult, GateInput, GateProfile


def _missing(name: str) -> CriterionResult:
    return CriterionResult(name=name, status="INSUFFICIENT", reason=f"{name} missing.")


def evaluate_drift(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.drift_score is None:
        return _missing("drift")
    status = "PASS" if gate_input.drift_score >= profile.min_drift_for_admit else "FAIL"
    return CriterionResult(
        name="drift",
        status=status,
        reason=f"drift_score={gate_input.drift_score:.3f}, threshold>={profile.min_drift_for_admit:.3f}",
    )


def evaluate_stability(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.stability_score is None:
        return _missing("stability")
    status = "PASS" if gate_input.stability_score <= profile.max_stability_for_admit else "FAIL"
    return CriterionResult(
        name="stability",
        status=status,
        reason=f"stability_score={gate_input.stability_score:.3f}, threshold<={profile.max_stability_for_admit:.3f}",
    )


def evaluate_coherence(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.coherence_score is None:
        return _missing("coherence")
    status = "PASS" if gate_input.coherence_score >= profile.min_coherence_for_admit else "FAIL"
    return CriterionResult(
        name="coherence",
        status=status,
        reason=f"coherence_score={gate_input.coherence_score:.3f}, threshold>={profile.min_coherence_for_admit:.3f}",
    )


def evaluate_snr(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.snr_score is None:
        return _missing("snr")
    status = "PASS" if gate_input.snr_score >= profile.min_snr_for_admit else "FAIL"
    return CriterionResult(
        name="snr",
        status=status,
        reason=f"snr_score={gate_input.snr_score:.3f}, threshold>={profile.min_snr_for_admit:.3f}",
    )


def evaluate_persistence(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.persistence_minutes is None:
        return _missing("persistence")
    status = "PASS" if gate_input.persistence_minutes >= profile.min_persistence_minutes_for_admit else "FAIL"
    return CriterionResult(
        name="persistence",
        status=status,
        reason=(
            f"persistence_minutes={gate_input.persistence_minutes:.2f}, "
            f"threshold>={profile.min_persistence_minutes_for_admit:.2f}"
        ),
    )


def evaluate_corroboration(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    if gate_input.corroborating_signal_count is None:
        return _missing("corroboration")
    status = "PASS" if gate_input.corroborating_signal_count >= profile.min_corroborating_signals_for_admit else "FAIL"
    return CriterionResult(
        name="corroboration",
        status=status,
        reason=(
            f"corroborating_signal_count={gate_input.corroborating_signal_count}, "
            f"threshold>={profile.min_corroborating_signals_for_admit}"
        ),
    )


def evaluate_context_exclusions(gate_input: GateInput) -> CriterionResult:
    context_flags = gate_input.context_flags if isinstance(gate_input.context_flags, dict) else {}
    flags = {k: bool(v) for k, v in context_flags.items()}
    active = sorted([k for k, v in flags.items() if v])
    exclusionary = {
        "maintenance_mode",
        "startup_transient",
        "instrumentation_compromised",
        "calibration_window",
        "known_false_positive_window",
    }
    active_exclusions = [name for name in active if name in exclusionary]
    if active_exclusions:
        return CriterionResult(
            name="context_exclusions",
            status="FAIL",
            reason=f"active exclusion flags: {', '.join(active_exclusions)}",
        )
    return CriterionResult(name="context_exclusions", status="PASS", reason="no exclusionary context flags active")


def evaluate_candidate_assertion(gate_input: GateInput) -> tuple[CriterionResult, DoctrineAssessment]:
    assessment = assess_assertion(gate_input.candidate_assertion)
    status = "PASS" if assessment.allowed else "FAIL"
    reason = assessment.reason or "No doctrine reason provided."
    return CriterionResult(name="candidate_assertion", status=status, reason=reason), assessment


def evaluate_metric_conflict(gate_input: GateInput, profile: GateProfile) -> CriterionResult:
    """Detect material metric conflicts that indicate evidence incoherence."""
    if gate_input.drift_score is None or gate_input.coherence_score is None:
        return _missing("metric_conflict")

    margin = gate_input.drift_score - gate_input.coherence_score
    if margin >= profile.void_if_conflict_margin:
        return CriterionResult(
            name="metric_conflict",
            status="FAIL",
            reason=(
                f"drift-coherence margin={margin:.3f} exceeds conflict threshold "
                f"{profile.void_if_conflict_margin:.3f}"
            ),
        )
    return CriterionResult(name="metric_conflict", status="PASS", reason=f"drift-coherence margin={margin:.3f}")


def summarize(results: Iterable[CriterionResult]) -> dict[str, str]:
    return {item.name: item.status for item in results}
