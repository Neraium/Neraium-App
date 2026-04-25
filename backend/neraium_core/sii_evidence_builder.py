"""
Evidence Panel Builder: Constructs evidence blocks from SIIEngine outputs.

Generates operator-facing evidence that explains:
1. When instability was first detected relative to current state
2. How many cycles of lead time we have before crossing thresholds
3. Confidence in the detection
4. Historical regime transitions and their timing
5. Recovery vectors (direction toward stability)

All evidence derived exclusively from SIIEngine outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime

from neraium_core.sii_engine_adapter import UnifiedSystemState


@dataclass
class TransitionEvent:
    """Records a regime transition."""
    cycle: int
    from_regime: str
    to_regime: str
    timestamp: float
    instability_score: float


@dataclass
class TimelineEvent:
    """Timeline event for evidence narrative."""
    cycle: int
    event_type: str  # "divergence", "detection", "acceleration", "failure"
    instability_score: float
    description: str


@dataclass
class EvidenceBlock:
    """Evidence panel content for operator display."""
    timestamp: str
    cycle: int

    # PHASE 4: Timeline-based evidence
    timeline_events: list[TimelineEvent]
    divergence_cycle: Optional[int]  # When did structure begin changing?
    detection_cycle: Optional[int]   # When was it detected?
    acceleration_detected: bool      # Is V_t increasing?
    acceleration_rate: float         # d²S_t/dt² (second derivative)

    # Detection lead time for evidence panel
    detection_summary: str
    lead_time_message: Optional[str]
    lead_time_cycles: Optional[int]

    # Regime transition history
    recent_transitions: list[TransitionEvent]
    transition_count_24h: int

    # Confidence indicators
    detection_confidence: float
    baseline_novelty: float

    # Recovery direction
    recovery_vector_message: Optional[str]
    gradient_norm: float
    recovery_alignment: float

    # Historical context
    instability_trend: str  # "rising", "falling", "stable"
    velocity_trend: str  # "accelerating", "decelerating", "stable"

    # Actionable recommendations
    recommended_observations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "timestamp": self.timestamp,
            "cycle": self.cycle,
            "timeline_events": [
                {
                    "cycle": e.cycle,
                    "event_type": e.event_type,
                    "instability_score": float(e.instability_score),
                    "description": e.description,
                }
                for e in self.timeline_events
            ],
            "divergence_cycle": self.divergence_cycle,
            "detection_cycle": self.detection_cycle,
            "acceleration_detected": self.acceleration_detected,
            "acceleration_rate": float(self.acceleration_rate),
            "detection_summary": self.detection_summary,
            "lead_time_message": self.lead_time_message,
            "lead_time_cycles": self.lead_time_cycles,
            "recent_transitions": [
                {
                    "cycle": t.cycle,
                    "from_regime": t.from_regime,
                    "to_regime": t.to_regime,
                    "timestamp": t.timestamp,
                    "instability_score": float(t.instability_score),
                }
                for t in self.recent_transitions
            ],
            "transition_count_24h": self.transition_count_24h,
            "detection_confidence": float(self.detection_confidence),
            "baseline_novelty": float(self.baseline_novelty),
            "recovery_vector_message": self.recovery_vector_message,
            "gradient_norm": float(self.gradient_norm),
            "recovery_alignment": float(self.recovery_alignment),
            "instability_trend": self.instability_trend,
            "velocity_trend": self.velocity_trend,
            "recommended_observations": self.recommended_observations,
        }

    @staticmethod
    def _build_timeline(state: UnifiedSystemState) -> list[TimelineEvent]:
        """Build timeline of key events."""
        events: list[TimelineEvent] = []

        if not state.instability_history or len(state.instability_history) < 2:
            return events

        # Find divergence point (sustained increase in instability)
        for i in range(1, len(state.instability_history)):
            prev_score = state.instability_history[i - 1]
            curr_score = state.instability_history[i]

            # Divergence: when score starts sustained increase (threshold 0.05)
            if (
                prev_score < 0.1
                and curr_score >= 0.1
            ):
                approx_cycle = state.cycle - (len(state.instability_history) - i)
                events.append(
                    TimelineEvent(
                        cycle=approx_cycle,
                        event_type="divergence",
                        instability_score=curr_score,
                        description=f"Structural divergence began (I_t={curr_score:.3f})",
                    )
                )

            # Detection: when reaching threshold
            if (
                prev_score < 0.65
                and curr_score >= 0.65
            ):
                approx_cycle = state.cycle - (len(state.instability_history) - i)
                events.append(
                    TimelineEvent(
                        cycle=approx_cycle,
                        event_type="detection",
                        instability_score=curr_score,
                        description=f"Instability detected (I_t={curr_score:.3f})",
                    )
                )

        return events[-5:]  # Last 5 events

    @staticmethod
    def _find_divergence_cycle(state: UnifiedSystemState) -> Optional[int]:
        """Find the cycle where structural divergence began."""
        if not state.instability_history or len(state.instability_history) < 2:
            return None

        # Divergence: first sustained increase above baseline
        for i in range(1, len(state.instability_history)):
            if state.instability_history[i] >= 0.1 and state.instability_history[i - 1] < 0.1:
                return state.cycle - (len(state.instability_history) - i)

        return None

    @staticmethod
    def _analyze_acceleration(state: UnifiedSystemState) -> tuple[bool, float]:
        """Analyze acceleration of drift velocity (is instability accelerating?)."""
        if not state.velocity_history or len(state.velocity_history) < 3:
            return False, 0.0

        recent = state.velocity_history[-5:]

        # Compute second derivative (acceleration of velocity)
        if len(recent) >= 3:
            # Approximate d²S/dt² as change in velocity over recent window
            accel = 0.0
            count = 0
            for i in range(1, len(recent)):
                delta_v = recent[i] - recent[i - 1]
                accel += delta_v
                count += 1

            if count > 0:
                accel = accel / count

            is_accelerating = accel > 0.005  # Threshold for meaningful acceleration

            return is_accelerating, accel

        return False, 0.0


class EvidenceBuilder:
    """Constructs evidence blocks from SIIEngine state."""

    @staticmethod
    def build(state: UnifiedSystemState) -> EvidenceBlock:
        """Build evidence block from unified system state."""
        # PHASE 4: Timeline analysis
        timeline_events = EvidenceBuilder._build_timeline(state)
        divergence_cycle = EvidenceBuilder._find_divergence_cycle(state)
        detection_cycle = state.detection_context.first_detection_cycle

        # Acceleration analysis
        acceleration_detected, acceleration_rate = EvidenceBuilder._analyze_acceleration(state)

        # Detection summary
        detection_summary = EvidenceBuilder._build_detection_summary(state)

        # Lead time calculation
        lead_time_msg, lead_time = EvidenceBuilder._compute_lead_time(state)

        # Regime transitions
        recent_transitions = EvidenceBuilder._extract_regime_transitions(state)
        transition_count = len(recent_transitions)

        # Trend analysis
        instability_trend = EvidenceBuilder._analyze_instability_trend(state)
        velocity_trend = EvidenceBuilder._analyze_velocity_trend(state)

        # Recovery vector
        recovery_msg = EvidenceBuilder._build_recovery_message(state)

        # Recommendations
        observations = EvidenceBuilder._generate_observations(state, instability_trend)

        timestamp = datetime.utcfromtimestamp(state.timestamp).isoformat() + "Z"

        return EvidenceBlock(
            timestamp=timestamp,
            cycle=state.cycle,
            timeline_events=timeline_events,
            divergence_cycle=divergence_cycle,
            detection_cycle=detection_cycle,
            acceleration_detected=acceleration_detected,
            acceleration_rate=acceleration_rate,
            detection_summary=detection_summary,
            lead_time_message=lead_time_msg,
            lead_time_cycles=lead_time,
            recent_transitions=recent_transitions,
            transition_count_24h=transition_count,
            detection_confidence=state.detection_context.detection_confidence,
            baseline_novelty=state.detection_context.novelty_vs_baseline,
            recovery_vector_message=recovery_msg,
            gradient_norm=state.gradient_norm,
            recovery_alignment=state.recovery_alignment,
            instability_trend=instability_trend,
            velocity_trend=velocity_trend,
            recommended_observations=observations,
        )

    @staticmethod
    def _build_detection_summary(state: UnifiedSystemState) -> str:
        """Build human-readable detection summary."""
        ctx = state.detection_context

        if ctx.first_detection_cycle is None:
            return "No anomalies detected. System operating within baseline."

        cycles_since = state.cycle - ctx.first_detection_cycle
        confidence_pct = int(ctx.detection_confidence * 100)

        return (
            f"Instability first detected {cycles_since} cycles ago "
            f"(cycle {ctx.first_detection_cycle}). "
            f"Detection confidence: {confidence_pct}%."
        )

    @staticmethod
    def _compute_lead_time(state: UnifiedSystemState) -> tuple[Optional[str], Optional[int]]:
        """Compute lead time before reaching critical threshold."""
        score = state.instability_score
        velocity = state.drift_velocity

        # If already critical, no lead time
        if state.regime == "LOCK_IN":
            return "System in critical state. Intervention required immediately.", None

        # If unstable, compute time to lock-in
        if state.regime == "UNSTABLE":
            # Rough estimate: if velocity continues, how many cycles to LOCK_IN threshold (0.85)?
            if velocity > 0.001:
                cycles_remaining = int((0.85 - score) / velocity)
                if cycles_remaining > 0:
                    return (
                        f"Approximately {cycles_remaining} cycles before critical threshold.",
                        cycles_remaining,
                    )
            return "System unstable. Transition to critical could be imminent.", None

        # If transitioning, estimate time to unstable
        if state.regime == "TRANSITION":
            if velocity > 0.001:
                cycles_remaining = int((0.65 - score) / velocity)
                if cycles_remaining > 0:
                    return (
                        f"Estimated {cycles_remaining} cycles before reaching high-risk state.",
                        cycles_remaining,
                    )
            return "System transitioning. Close monitoring recommended.", None

        # If stable, report velocity for context
        if velocity > 0.05:
            return "System stable but velocity elevated. Monitor for trends.", None

        return None, None

    @staticmethod
    def _extract_regime_transitions(state: UnifiedSystemState) -> list[TransitionEvent]:
        """Extract regime transitions from history."""
        transitions: list[TransitionEvent] = []

        if not state.regime_history or len(state.regime_history) < 2:
            return transitions

        prev_regime = None
        for idx, regime in enumerate(state.regime_history):
            if prev_regime is not None and regime != prev_regime:
                cycle_idx = len(state.regime_history) - len(state.regime_history) + idx
                # Approximate cycle number
                approx_cycle = state.cycle - (len(state.regime_history) - idx)
                # Approximate instability score at transition
                if idx < len(state.instability_history):
                    instability_at_transition = state.instability_history[idx]
                else:
                    instability_at_transition = state.instability_score

                transitions.append(
                    TransitionEvent(
                        cycle=approx_cycle,
                        from_regime=prev_regime,
                        to_regime=regime,
                        timestamp=state.timestamp,
                        instability_score=instability_at_transition,
                    )
                )
            prev_regime = regime

        return transitions[-5:]  # Return last 5 transitions

    @staticmethod
    def _analyze_instability_trend(state: UnifiedSystemState) -> str:
        """Analyze instability score trend."""
        if not state.instability_history or len(state.instability_history) < 3:
            return "insufficient_data"

        recent = state.instability_history[-10:]
        if len(recent) < 2:
            return "insufficient_data"

        # Simple trend: compare last 5 to previous 5
        if len(recent) >= 5:
            last_5 = recent[-5:]
            prev_5 = recent[:5]
            recent_avg = sum(last_5) / len(last_5)
            prev_avg = sum(prev_5) / len(prev_5)

            if recent_avg > prev_avg + 0.05:
                return "rising"
            elif recent_avg < prev_avg - 0.05:
                return "falling"
            else:
                return "stable"

        # Single comparison
        if recent[-1] > recent[0] + 0.05:
            return "rising"
        elif recent[-1] < recent[0] - 0.05:
            return "falling"
        else:
            return "stable"

    @staticmethod
    def _analyze_velocity_trend(state: UnifiedSystemState) -> str:
        """Analyze drift velocity trend."""
        if not state.velocity_history or len(state.velocity_history) < 3:
            return "insufficient_data"

        recent = state.velocity_history[-10:]

        # Compute second derivative (acceleration of velocity)
        if len(recent) >= 3:
            last_3_deltas = [recent[i + 1] - recent[i] for i in range(len(recent) - 3, len(recent) - 1)]
            avg_accel = sum(last_3_deltas) / len(last_3_deltas) if last_3_deltas else 0.0

            if avg_accel > 0.01:
                return "accelerating"
            elif avg_accel < -0.01:
                return "decelerating"
            else:
                return "stable"

        return "stable"

    @staticmethod
    def _build_recovery_message(state: UnifiedSystemState) -> Optional[str]:
        """Build message about recovery direction (moving toward baseline)."""
        alignment = state.recovery_alignment

        if alignment > 0.7:
            return "System moving toward stability (high recovery alignment)."
        elif alignment > 0.3:
            return "System has some stability recovery component."
        elif alignment < -0.5:
            return "System moving away from stability. Intervention recommended."
        elif alignment < -0.2:
            return "System drifting away from baseline."
        else:
            return None

    @staticmethod
    def _generate_observations(state: UnifiedSystemState, trend: str) -> list[str]:
        """Generate actionable observation recommendations."""
        obs: list[str] = []

        # Regime-based observations
        if state.regime == "LOCK_IN":
            obs.append("CRITICAL: Immediate intervention required.")
            obs.append("Review recent configuration changes.")
            obs.append("Check for resource exhaustion or component failures.")
        elif state.regime == "UNSTABLE":
            obs.append("ALERT: System at high risk of failure.")
            obs.append("Prioritize stabilization measures.")
            obs.append("Increase monitoring frequency.")
        elif state.regime == "TRANSITION":
            obs.append("WATCH: System behavior shifting. Identify drivers.")
            obs.append("Monitor key metrics for acceleration trends.")
            obs.append("Prepare contingency procedures.")
        elif state.regime == "STABLE" and state.urgency == "WATCH":
            obs.append("System stable but elevated velocity detected.")
            obs.append("Investigate recent changes in load or configuration.")

        # Trend-based observations
        if trend == "rising":
            obs.append("Instability is rising. Trend analysis suggests worsening conditions.")
        elif trend == "falling":
            obs.append("Instability is declining. Continue monitoring for sustained improvement.")

        # Velocity observations
        if state.drift_velocity > 0.1:
            obs.append(f"High drift velocity ({state.drift_velocity:.3f}). System changing rapidly.")
        elif state.drift_velocity < -0.1:
            obs.append(f"Negative velocity: structural relaxation detected.")

        # Recovery alignment
        if state.recovery_alignment < -0.5:
            obs.append("System moving away from baseline. Corrective action needed.")

        return obs[:5]  # Limit to 5 observations


__all__ = [
    "EvidenceBuilder",
    "EvidenceBlock",
    "TransitionEvent",
]
