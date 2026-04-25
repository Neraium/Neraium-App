"""
PHASE 5: Specific Causal Narratives

Replaces generic language with system-specific, mechanistic explanations.

NOT:  "System operating normally"
BUT:  "All structural relationships remain within baseline coupling — no divergence detected"

NOT:  "High risk"
BUT:  "Drift velocity is accelerating. Instability will reach critical threshold
       in approximately X cycles without intervention."

All narratives are derived ONLY from:
- regime: STABLE, TRANSITION, UNSTABLE, LOCK_IN
- urgency: NOMINAL, WATCH, ALERT, CRITICAL
- velocity: drift_velocity (direction and acceleration)
"""

from __future__ import annotations

from typing import Any


class CausalNarrativeEngine:
    """Generates mechanistic, causal narratives from system state."""

    @staticmethod
    def build_narrative(
        regime: str,
        urgency: str,
        drift_velocity: float,
        instability_score: float,
        acceleration: float = 0.0,
        asset_id: str = "system",
    ) -> dict[str, str]:
        """
        Generate causal narrative explaining WHAT is happening and WHY.

        Args:
            regime: STABLE, TRANSITION, UNSTABLE, LOCK_IN
            urgency: NOMINAL, WATCH, ALERT, CRITICAL
            drift_velocity: Rate of structural deformation (dS/dt)
            instability_score: Current I_t [0, 1]
            acceleration: Second derivative (d²S/dt²)
            asset_id: Asset identifier for context

        Returns:
            Dict with:
            - structural_status: What is structurally happening?
            - velocity_status: How fast? Accelerating or decelerating?
            - failure_risk: What is the failure risk?
            - action_required: What action should be taken?
            - metric_context: Specific numeric context
        """
        # Determine if velocity is increasing
        accel_direction = (
            "accelerating"
            if acceleration > 0.01
            else ("decelerating" if acceleration < -0.01 else "stable")
        )

        velocity_sign = "increasing" if drift_velocity > 0 else "decreasing"

        # Primary structural status based on regime
        if regime == "STABLE":
            structural_status = (
                "All structural relationships remain within baseline coupling. "
                "No divergence in correlation patterns detected."
            )

        elif regime == "TRANSITION":
            structural_status = (
                f"Structural relationships are diverging from baseline at a "
                f"{velocity_sign} rate. Correlation matrix is deforming. "
                f"System transitioning to new operational regime."
            )

        elif regime == "UNSTABLE":
            structural_status = (
                f"Structural deformation is severe. Correlation relationships have "
                f"shifted substantially from baseline. Multiple sensor dependencies "
                f"are {velocity_sign}. System approaching critical state."
            )

        elif regime == "LOCK_IN":
            structural_status = (
                "Critical structural lock-in detected. Correlation structure "
                "severely degraded. Failure mechanisms are engaged. Recovery "
                "not possible under current operating conditions."
            )

        else:
            structural_status = "System status unknown."

        # Velocity dynamics
        if abs(drift_velocity) < 0.01:
            velocity_status = "Structural deformation rate is minimal. System is stable."

        elif abs(drift_velocity) < 0.05:
            velocity_status = (
                f"Structural deformation rate is low ({drift_velocity:.4f} per cycle). "
                f"Change is {velocity_sign} and {accel_direction}. "
                "Gradual transition in progress."
            )

        elif abs(drift_velocity) < 0.15:
            velocity_status = (
                f"Structural deformation rate is moderate ({drift_velocity:.4f} per cycle). "
                f"Correlation structure {velocity_sign} at measurable pace. "
                f"Velocity is {accel_direction}. Attention required."
            )

        else:
            velocity_status = (
                f"Structural deformation rate is high ({drift_velocity:.4f} per cycle). "
                f"System {velocity_sign} rapidly. Velocity is {accel_direction}. "
                "Urgent intervention needed."
            )

        # Failure risk estimation
        if regime == "STABLE":
            if urgency == "NOMINAL":
                failure_risk = (
                    f"[{asset_id}] Failure risk is LOW. Instability metric I_t = {instability_score:.3f} "
                    "is well within safe bounds (I_t ≤ 0.30). "
                    "No accelerating trends detected."
                )
            else:  # WATCH
                failure_risk = (
                    f"[{asset_id}] Failure risk is ELEVATED. Instability I_t = {instability_score:.3f}. "
                    "Although regime is stable, elevated velocity indicates "
                    "system activity. Trend reversal possible."
                )

        elif regime == "TRANSITION":
            if urgency == "WATCH":
                eta_text = (
                    f"Estimated time to UNSTABLE regime: {int((0.65 - instability_score) / drift_velocity)} cycles."
                    if drift_velocity > 0.001
                    else "System stabilizing or drifting slowly; no imminent threshold crossing expected."
                )
                failure_risk = (
                    f"[{asset_id}] Failure risk is MODERATE. System transitioning (I_t = {instability_score:.3f}). "
                    "Operator intervention can still redirect system state. "
                    f"{eta_text}"
                )
            else:  # ALERT
                eta_text = (
                    f"At current velocity, system will reach UNSTABLE regime in ~{int((0.65 - instability_score) / drift_velocity)} cycles."
                    if drift_velocity > 0.001
                    else "Velocity is negative/near-zero; reassess drift direction."
                )
                failure_risk = (
                    f"[{asset_id}] Failure risk is HIGH. Rapid transition in progress (I_t = {instability_score:.3f}, "
                    f"V_t = {drift_velocity:.4f}). "
                    f"{eta_text}"
                )

        elif regime == "UNSTABLE":
            time_to_critical = (
                int((0.85 - instability_score) / drift_velocity)
                if drift_velocity > 0.001
                else int(abs((0.85 - instability_score) / max(drift_velocity, 0.001)))
            )
            failure_risk = (
                f"[{asset_id}] Failure risk is CRITICAL. System in UNSTABLE regime (I_t = {instability_score:.3f}). "
                f"Structural degradation is severe. Failure expected within ~{max(1, time_to_critical)} cycles. "
                "Immediate corrective action required or controlled shutdown necessary."
            )

        elif regime == "LOCK_IN":
            failure_risk = (
                f"[{asset_id}] Failure risk is IMMINENT. System in LOCK_IN regime (I_t = {instability_score:.3f}). "
                "Structural failure is occurring NOW. Recovery not possible. "
                "Activate emergency procedures immediately."
            )

        else:
            failure_risk = "System status unknown."

        # Action recommendations tied to structural variables
        if regime == "STABLE":
            if urgency == "NOMINAL":
                action_required = (
                    "CONTINUE NORMAL OPERATIONS. No action required. "
                    "Maintain standard monitoring schedule. "
                    "Instability metric within safe operating envelope."
                )
            else:  # WATCH
                action_required = (
                    "INCREASE MONITORING FREQUENCY. Investigate source of elevated velocity. "
                    "Check for: (1) recent configuration changes, (2) load variations, "
                    "(3) environmental factors affecting sensor baselines. "
                    "Prepare contingency if trend continues."
                )

        elif regime == "TRANSITION":
            if urgency == "WATCH":
                action_required = (
                    "IDENTIFY TRANSITION DRIVER. Analyze which structural relationships "
                    "are deforming (examine covariance matrix). Determine if transition is "
                    "intentional or fault-induced. Monitor velocity continuously. "
                    "Be prepared to escalate if velocity increases or transition accelerates."
                )
            else:  # ALERT
                action_required = (
                    "EXECUTE STABILIZATION PROTOCOL IMMEDIATELY. "
                    "(1) Identify and mitigate root cause (check which sensors/subsystems "
                    "are driving structural drift). "
                    "(2) Implement load reduction or configuration adjustment. "
                    "(3) Monitor instability score real-time. If continues toward I_t=0.65, "
                    "escalate to emergency procedures."
                )

        elif regime == "UNSTABLE":
            action_required = (
                "ACTIVATE EMERGENCY RESPONSE. System is at imminent failure point. "
                "(1) PRIORITY: Execute prepared stabilization measures without delay. "
                "(2) If stabilization fails, initiate controlled shutdown or failover. "
                "(3) Monitor every cycle (real-time sampling). "
                "(4) Alert all stakeholders. Failure is likely within hours."
            )

        elif regime == "LOCK_IN":
            action_required = (
                "ACTIVATE EMERGENCY PROCEDURES NOW. "
                "Failure is occurring. Recovery not possible. "
                "(1) Initiate immediate failover to backup systems if available. "
                "(2) Begin graceful service degradation. "
                "(3) Prepare disaster recovery procedures. "
                "(4) Preserve system state for post-mortem analysis."
            )

        else:
            action_required = "Unknown system state. Escalate to engineering review."

        # Metric context for instrumentation teams
        metric_context = (
            f"I_t = {instability_score:.4f} | "
            f"V_t = {drift_velocity:+.5f} cycles⁻¹ | "
            f"Accel = {acceleration:+.5f} cycles⁻² | "
            f"Regime: {regime} | "
            f"Urgency: {urgency}"
        )

        return {
            "asset_id": asset_id,
            "regime": regime,
            "urgency": urgency,
            "structural_status": structural_status,
            "velocity_status": velocity_status,
            "failure_risk": failure_risk,
            "action_required": action_required,
            "metric_context": metric_context,
        }

    @staticmethod
    def format_for_operator(narrative: dict[str, str]) -> str:
        """Format narrative for operator display."""
        lines = [
            f"\n{'='*70}",
            f"SYSTEM STATUS REPORT: {narrative['asset_id']}",
            f"Regime: {narrative['regime']} | Urgency: {narrative['urgency']}",
            f"{'='*70}\n",
            f"STRUCTURAL STATUS:",
            f"{narrative['structural_status']}\n",
            f"VELOCITY DYNAMICS:",
            f"{narrative['velocity_status']}\n",
            f"FAILURE RISK ASSESSMENT:",
            f"{narrative['failure_risk']}\n",
            f"REQUIRED ACTION:",
            f"{narrative['action_required']}\n",
            f"METRIC CONTEXT (for analysis):",
            f"{narrative['metric_context']}\n",
            f"{'='*70}\n",
        ]

        return "\n".join(lines)


__all__ = ["CausalNarrativeEngine"]
