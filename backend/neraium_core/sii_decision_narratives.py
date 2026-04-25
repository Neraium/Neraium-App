"""
SII Decision Narratives: Generate copy from regime + urgency ONLY.

Ensures decision chain copy is derived entirely from:
- regime: STABLE, TRANSITION, UNSTABLE, LOCK_IN
- urgency: NOMINAL, WATCH, ALERT, CRITICAL

No independent thresholds, no subsystem-specific logic, no legacy scoring.
All narratives are deterministic mappings from (regime, urgency) → operator message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DecisionNarrative:
    """Operator-facing decision narrative."""
    state: str
    urgency_level: str
    primary_message: str
    guidance: str
    recommended_action: str
    escalation_threshold: str
    operator_note: str


class DecisionNarrativeEngine:
    """Generates decision narratives from regime + urgency ONLY."""

    @staticmethod
    def build_narrative(
        regime: str,
        urgency: str,
        asset_id: str = "asset",
        cycle: int = 0,
    ) -> DecisionNarrative:
        """
        Build decision narrative from regime and urgency.

        This is the ONLY place where decision copy is generated.
        No UI, no API endpoint, no decision layer should compute
        narratives independently.

        Args:
            regime: One of STABLE, TRANSITION, UNSTABLE, LOCK_IN
            urgency: One of NOMINAL, WATCH, ALERT, CRITICAL
            asset_id: Asset identifier for context
            cycle: Current cycle for reference

        Returns:
            DecisionNarrative with operator-facing messages
        """
        # Validate inputs
        regimes = {"STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN", "WARMUP"}
        urgencies = {"NOMINAL", "WATCH", "ALERT", "CRITICAL"}

        if regime not in regimes:
            regime = "STABLE"
        if urgency not in urgencies:
            urgency = "NOMINAL"

        # Generate narrative based on (regime, urgency) pair
        if regime == "WARMUP":
            return DecisionNarrativeEngine._narrative_warmup()

        elif regime == "STABLE":
            if urgency == "NOMINAL":
                return DecisionNarrativeEngine._narrative_stable_nominal(asset_id)
            elif urgency == "WATCH":
                return DecisionNarrativeEngine._narrative_stable_watch(asset_id)
            else:
                return DecisionNarrativeEngine._narrative_stable_nominal(asset_id)

        elif regime == "TRANSITION":
            if urgency == "NOMINAL":
                return DecisionNarrativeEngine._narrative_transition_nominal(asset_id)
            elif urgency == "WATCH":
                return DecisionNarrativeEngine._narrative_transition_watch(asset_id)
            elif urgency == "ALERT":
                return DecisionNarrativeEngine._narrative_transition_alert(asset_id)
            else:
                return DecisionNarrativeEngine._narrative_transition_alert(asset_id)

        elif regime == "UNSTABLE":
            if urgency == "ALERT":
                return DecisionNarrativeEngine._narrative_unstable_alert(asset_id)
            else:
                return DecisionNarrativeEngine._narrative_unstable_alert(asset_id)

        elif regime == "LOCK_IN":
            return DecisionNarrativeEngine._narrative_lock_in(asset_id)

        else:
            return DecisionNarrativeEngine._narrative_stable_nominal(asset_id)

    @staticmethod
    def _narrative_warmup() -> DecisionNarrative:
        return DecisionNarrative(
            state="WARMUP",
            urgency_level="NOMINAL",
            primary_message="System baseline collection in progress.",
            guidance=(
                "Initial structural profile is being established. "
                "Normal operation will be detected after sufficient data collection."
            ),
            recommended_action="Continue normal operations. No action required.",
            escalation_threshold="None (warmup phase)",
            operator_note=(
                "This is expected during system startup or when switching to a new asset. "
                "The system will be ready to detect anomalies once baseline computation completes."
            ),
        )

    @staticmethod
    def _narrative_stable_nominal(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="STABLE (NOMINAL)",
            urgency_level="NOMINAL",
            primary_message=f"[{asset_id}] System operating normally.",
            guidance=(
                "Structural integrity is within baseline. "
                "No anomalies detected. Continue routine operations."
            ),
            recommended_action="No action required. Continue standard monitoring.",
            escalation_threshold="Escalates if system enters TRANSITION regime.",
            operator_note=(
                "This is the expected state during normal operation. "
                "The system is stable and meeting all defined baselines."
            ),
        )

    @staticmethod
    def _narrative_stable_watch(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="STABLE (WATCH)",
            urgency_level="WATCH",
            primary_message=f"[{asset_id}] System stable but elevated activity detected.",
            guidance=(
                "Structural drift is low, but drift velocity is elevated. "
                "Changes are occurring faster than normal. "
                "Investigate recent operational or environmental changes."
            ),
            recommended_action=(
                "1. Review recent configuration changes or load variations. "
                "2. Check for unusual operational patterns. "
                "3. Increase monitoring frequency to daily checks."
            ),
            escalation_threshold="Escalates to ALERT if regime shifts to TRANSITION with high velocity.",
            operator_note=(
                "The system is still within normal operating bounds, but watch for sustained trends. "
                "This state often precedes more significant transitions."
            ),
        )

    @staticmethod
    def _narrative_transition_nominal(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="TRANSITION (NOMINAL)",
            urgency_level="NOMINAL",
            primary_message=f"[{asset_id}] System undergoing gradual structural change.",
            guidance=(
                "The system is shifting from one operating state to another, "
                "but the change is slow and predictable. "
                "Structural integrity remains acceptable."
            ),
            recommended_action="Continue monitoring. Document the transition driver.",
            escalation_threshold="Escalates if velocity increases or transition persists beyond normal window.",
            operator_note=(
                "Gradual transitions are normal in many systems. "
                "Monitor to ensure the transition is intentional and completes."
            ),
        )

    @staticmethod
    def _narrative_transition_watch(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="TRANSITION (WATCH)",
            urgency_level="WATCH",
            primary_message=f"[{asset_id}] System transitioning. Close monitoring required.",
            guidance=(
                "The system is in a regime shift. Structural relationships are deforming. "
                "The change appears manageable but requires close attention. "
                "Transition velocity is moderate."
            ),
            recommended_action=(
                "1. Identify the root cause of the transition. "
                "2. Monitor key driver metrics for acceleration. "
                "3. Prepare contingency procedures if transition continues. "
                "4. Increase monitoring to hourly checks."
            ),
            escalation_threshold="Escalates to ALERT if velocity increases or instability crosses 0.65.",
            operator_note=(
                "Transitions are dynamic periods. Early identification of drivers "
                "enables proactive intervention."
            ),
        )

    @staticmethod
    def _narrative_transition_alert(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="TRANSITION (ALERT)",
            urgency_level="ALERT",
            primary_message=f"[{asset_id}] Rapid transition detected. Intervention required.",
            guidance=(
                "The system is undergoing a rapid regime shift with elevated velocity. "
                "Structural deformation is accelerating. "
                "Without intervention, the system will enter HIGH-RISK state within hours."
            ),
            recommended_action=(
                "1. PRIORITY: Identify and mitigate the transition driver immediately. "
                "2. Implement corrective actions to slow the transition. "
                "3. Increase monitoring to continuous real-time checks. "
                "4. Alert operations team and prepare escalation procedures. "
                "5. Consider controlled shutdown or staged recovery procedures."
            ),
            escalation_threshold=(
                "Escalates to CRITICAL if system enters UNSTABLE or LOCK_IN regime."
            ),
            operator_note=(
                "This state indicates the system is at a critical decision point. "
                "Timely intervention can prevent failure."
            ),
        )

    @staticmethod
    def _narrative_unstable_alert(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="UNSTABLE (ALERT)",
            urgency_level="ALERT",
            primary_message=f"[{asset_id}] System at HIGH RISK. Immediate intervention required.",
            guidance=(
                "The system has entered an unstable state with significant structural degradation. "
                "Failure is likely within hours if current trajectory continues. "
                "All safety margins are compromised."
            ),
            recommended_action=(
                "1. IMMEDIATE: Initiate emergency response procedures. "
                "2. Execute prepared stabilization measures without delay. "
                "3. Implement load shedding, resource reallocation, or service degradation as needed. "
                "4. Establish continuous monitoring (sample every minute). "
                "5. Brief management on failure risk and recovery timeline. "
                "6. Prepare contingency systems and failover protocols."
            ),
            escalation_threshold="CRITICAL state possible within hours.",
            operator_note=(
                "At this urgency level, every action taken now significantly "
                "improves the probability of maintaining service continuity."
            ),
        )

    @staticmethod
    def _narrative_lock_in(asset_id: str) -> DecisionNarrative:
        return DecisionNarrative(
            state="LOCK_IN (CRITICAL)",
            urgency_level="CRITICAL",
            primary_message=f"[{asset_id}] CRITICAL STATE. Imminent failure.",
            guidance=(
                "The system is in a locked-in degraded state. "
                "Structural integrity is critically compromised. "
                "Failure is imminent (minutes to hours). "
                "Recovery may not be possible; focus shifts to mitigation and failover."
            ),
            recommended_action=(
                "1. ACTIVATE EMERGENCY PROTOCOLS IMMEDIATELY. "
                "2. If service continuity is critical, initiate failover to backup system NOW. "
                "3. Begin graceful service shutdown if failover is not available. "
                "4. Notify all stakeholders of service risk. "
                "5. Preserve system state for post-mortem analysis. "
                "6. Execute disaster recovery plan."
            ),
            escalation_threshold="System failure expected imminently.",
            operator_note=(
                "CRITICAL state leaves minimal time for corrective action. "
                "Prevention through earlier intervention is essential. "
                "Focus now is on damage control and recovery planning."
            ),
        )

    @staticmethod
    def to_decision_dict(
        regime: str,
        urgency: str,
        asset_id: str = "asset",
    ) -> dict[str, Any]:
        """
        Convert decision narrative to API-compatible dictionary.

        Suitable for embedding in canonical output contracts.
        """
        narrative = DecisionNarrativeEngine.build_narrative(
            regime, urgency, asset_id
        )

        return {
            "state": narrative.state,
            "urgency_level": narrative.urgency_level,
            "primary_message": narrative.primary_message,
            "guidance": narrative.guidance,
            "recommended_action": narrative.recommended_action,
            "escalation_threshold": narrative.escalation_threshold,
            "operator_note": narrative.operator_note,
        }


__all__ = [
    "DecisionNarrativeEngine",
    "DecisionNarrative",
]
