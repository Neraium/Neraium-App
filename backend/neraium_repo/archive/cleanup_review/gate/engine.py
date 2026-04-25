from __future__ import annotations


from neraium_core.gate.evaluator import (
    evaluate_candidate_assertion,
    evaluate_coherence,
    evaluate_context_exclusions,
    evaluate_corroboration,
    evaluate_drift,
    evaluate_metric_conflict,
    evaluate_persistence,
    evaluate_snr,
    evaluate_stability,
    summarize,
)
from neraium_core.gate.schema import CriterionResult, GateDecision, GateInput, GateProfile


class AletheiasGate:
    """Deterministic admissibility boundary for candidate observations."""

    def __init__(self, profile: GateProfile | None = None) -> None:
        self.profile = profile or GateProfile()

    def evaluate(self, gate_input: GateInput) -> GateDecision:
        results: list[CriterionResult] = [
            evaluate_drift(gate_input, self.profile),
            evaluate_stability(gate_input, self.profile),
            evaluate_coherence(gate_input, self.profile),
            evaluate_snr(gate_input, self.profile),
            evaluate_persistence(gate_input, self.profile),
            evaluate_corroboration(gate_input, self.profile),
            evaluate_context_exclusions(gate_input),
            evaluate_metric_conflict(gate_input, self.profile),
        ]
        candidate_result, doctrine_assessment = evaluate_candidate_assertion(gate_input)
        results.append(candidate_result)

        decision, refusal_reason = self._decide(results=results, gate_input=gate_input, doctrine_allowed=doctrine_assessment.allowed)

        observed_facts = [result.reason for result in results]
        uncertainty_notes = [
            f"{result.name}: {result.reason}"
            for result in results
            if result.status == "INSUFFICIENT"
        ]
        explanation = self._build_explanation(decision=decision, refusal_reason=refusal_reason)
        confidence_label = self._confidence_label(decision=decision, results=results)

        return GateDecision(
            decision=decision,
            doctrine_version=doctrine_assessment.doctrine_version,
            criteria_results=summarize(results),
            refusal_reason=refusal_reason,
            explanation=explanation,
            observed_facts=observed_facts,
            uncertainty_notes=uncertainty_notes,
            candidate_assertion_allowed=doctrine_assessment.allowed,
            confidence_label=confidence_label,
        )

    def _decide(self, *, results: list[CriterionResult], gate_input: GateInput, doctrine_allowed: bool) -> tuple[str, str | None]:
        by_name = {result.name: result for result in results}

        if not doctrine_allowed:
            return "ADMISSIBILITY_VOID", "Candidate assertion is not doctrine-allowed."

        if by_name["context_exclusions"].status == "FAIL":
            if bool(gate_input.context_flags.get("instrumentation_compromised")):
                return "ADMISSIBILITY_VOID", "Instrumentation compromise flag active."
            return "SUPPRESS", by_name["context_exclusions"].reason

        coherence = gate_input.coherence_score
        snr = gate_input.snr_score
        corroboration = gate_input.corroborating_signal_count

        if coherence is not None and coherence < self.profile.void_if_coherence_below:
            return "ADMISSIBILITY_VOID", "Coherence is materially too low for defensible acknowledgment."
        if snr is not None and snr < self.profile.void_if_snr_below:
            return "ADMISSIBILITY_VOID", "Signal-to-noise indicates materially incoherent telemetry."
        if corroboration is not None and corroboration <= 0:
            return "ADMISSIBILITY_VOID", "No corroborating signal present."
        if by_name["metric_conflict"].status == "FAIL":
            return "ADMISSIBILITY_VOID", by_name["metric_conflict"].reason

        required_for_admit = ["drift", "stability", "coherence", "snr", "persistence", "corroboration", "context_exclusions", "candidate_assertion"]
        if all(by_name[name].status == "PASS" for name in required_for_admit):
            return "ADMIT", None

        return "SUPPRESS", "Evidence present but insufficient for deterministic admission."

    @staticmethod
    def _build_explanation(*, decision: str, refusal_reason: str | None) -> str:
        if decision == "ADMIT":
            return "Admitted: defensible, coherent, and doctrine-conformant observation criteria were met."
        if decision == "SUPPRESS":
            return f"Suppressed: {refusal_reason or 'observation did not meet surfacing thresholds.'}"
        return f"Admissibility void: {refusal_reason or 'evidence is materially incoherent or non-defensible.'}"

    @staticmethod
    def _confidence_label(*, decision: str, results: list[CriterionResult]) -> str:
        pass_count = sum(1 for result in results if result.status == "PASS")
        insufficient_count = sum(1 for result in results if result.status == "INSUFFICIENT")
        if decision == "ADMIT" and insufficient_count == 0:
            return "high"
        if decision == "ADMISSIBILITY_VOID":
            return "high" if pass_count <= 3 else "medium"
        if insufficient_count >= 3:
            return "low"
        return "medium"
