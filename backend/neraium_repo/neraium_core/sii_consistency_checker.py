"""
PHASE 6: Runtime Consistency Checks and Debug Output

Ensures mathematical and architectural consistency at runtime.
Provides detailed debug information showing all intermediate calculations.

When enabled, produces audit trail:
- S_t (structural drift)
- V_t (drift velocity)
- P_t (transition pressure)
- R_t (recovery alignment) [diagnostic]
- I_t (instability score)
- regime classification
- urgency mapping
- All intermediate calculations and decisions
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any, Optional
from datetime import datetime

from neraium_core.sii_engine_unified import SIIEngineOutput
from neraium_core.sii_engine_adapter import UnifiedSystemState


@dataclass
class DebugFrame:
    """Complete debug output for a single frame."""
    timestamp: float
    cycle: int

    # Input
    sensor_vector_size: int
    sensor_norm: float

    # Intermediate computations (S_t, V_t, P_t)
    structural_drift: float
    drift_velocity: float
    transition_pressure: float
    recovery_alignment: float

    # Unified score and classification
    instability_score: float
    instability_score_breakdown: dict[str, float]

    # State classification
    regime: str
    regime_threshold_range: dict[str, float]
    regime_match: bool

    # Urgency mapping
    urgency: str
    urgency_criteria: dict[str, bool]
    urgency_match: bool

    # Confidence and auxiliary
    confidence: float
    gradient_norm: float

    # State transitions (if any)
    regime_changed: bool
    urgency_changed: bool
    previous_regime: Optional[str]
    previous_urgency: Optional[str]

    # Validation results
    all_constraints_satisfied: bool
    constraint_violations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_human_readable(self) -> str:
        """Format for human review."""
        lines = []

        lines.append(f"\n{'='*70}")
        lines.append(f"DEBUG FRAME - Cycle {self.cycle} (t={self.timestamp:.2f})")
        lines.append(f"{'='*70}\n")

        lines.append(f"INPUT:")
        lines.append(f"  Sensor vector size: {self.sensor_vector_size} dimensions")
        lines.append(f"  Sensor norm: {self.sensor_norm:.6f}\n")

        lines.append(f"CORE COMPUTATIONS:")
        lines.append(f"  S_t (structural drift):     {self.structural_drift:.6f} [0, 1]")
        lines.append(f"  V_t (drift velocity):       {self.drift_velocity:+.6f} cycles⁻¹")
        lines.append(f"  P_t (transition pressure):  {self.transition_pressure:.6f} [0, 1]")
        lines.append(f"  R_t (recovery alignment):   {self.recovery_alignment:+.6f} [-1, 1] [DIAGNOSTIC]")

        lines.append(f"\nUNIFIED INSTABILITY SCORE:")
        lines.append(f"  I_t = {self.instability_score:.6f} [0, 1]")
        lines.append(f"  Breakdown:")
        lines.append(f"    α × S_t = {self.instability_score_breakdown.get('drift_contribution', 0.0):.6f}")
        lines.append(f"    β × |tanh(V_t)| = {self.instability_score_breakdown.get('velocity_contribution', 0.0):.6f}")
        lines.append(f"    γ × P_t = {self.instability_score_breakdown.get('pressure_contribution', 0.0):.6f}")
        lines.append(f"    Sum = {self.instability_score:.6f}")

        lines.append(f"\nREGIME CLASSIFICATION:")
        lines.append(f"  Regime: {self.regime}")
        lines.append(f"  I_t threshold range for {self.regime}:")
        for key, val in self.regime_threshold_range.items():
            lines.append(f"    {key}: {val}")
        lines.append(f"  Match: {'✓ PASS' if self.regime_match else '✗ FAIL'}")

        lines.append(f"\nURGENCY MAPPING:")
        lines.append(f"  Urgency: {self.urgency}")
        lines.append(f"  Criteria:")
        for key, val in self.urgency_criteria.items():
            lines.append(f"    {key}: {val}")
        lines.append(f"  Match: {'✓ PASS' if self.urgency_match else '✗ FAIL'}")

        lines.append(f"\nAUXILIARY METRICS:")
        lines.append(f"  Confidence: {self.confidence:.6f}")
        lines.append(f"  Gradient norm: {self.gradient_norm:.6f}")

        if self.regime_changed or self.urgency_changed:
            lines.append(f"\nSTATE TRANSITIONS:")
            if self.regime_changed:
                lines.append(f"  Regime: {self.previous_regime} → {self.regime}")
            if self.urgency_changed:
                lines.append(f"  Urgency: {self.previous_urgency} → {self.urgency}")

        lines.append(f"\nCONSISTENCY CHECK:")
        lines.append(f"  All constraints satisfied: {'✓ YES' if self.all_constraints_satisfied else '✗ NO'}")
        if self.constraint_violations:
            lines.append(f"  Violations:")
            for violation in self.constraint_violations:
                lines.append(f"    - {violation}")

        lines.append(f"\n{'='*70}\n")

        return "\n".join(lines)


class ConsistencyChecker:
    """Runtime consistency validation."""

    @staticmethod
    def validate_sii_output(
        output: SIIEngineOutput,
        previous_output: Optional[SIIEngineOutput] = None,
    ) -> tuple[bool, list[str]]:
        """
        Validate SIIEngineOutput for consistency.

        Returns: (is_valid, list_of_violations)
        """
        violations = []

        # Check ranges
        if not (0.0 <= output.instability_score <= 1.0):
            violations.append(
                f"instability_score out of range: {output.instability_score}"
            )

        if not (0.0 <= output.structural_drift <= 1.0):
            violations.append(f"structural_drift out of range: {output.structural_drift}")

        if not (0.0 <= output.transition_pressure <= 1.0):
            violations.append(
                f"transition_pressure out of range: {output.transition_pressure}"
            )

        if not (0.0 <= output.confidence <= 1.0):
            violations.append(f"confidence out of range: {output.confidence}")

        if not (-1.0 <= output.recovery_alignment <= 1.0):
            violations.append(
                f"recovery_alignment out of range: {output.recovery_alignment}"
            )

        # Check regime/urgency validity
        valid_regimes = {"STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN", "WARMUP"}
        if output.regime not in valid_regimes:
            violations.append(f"Invalid regime: {output.regime}")

        valid_urgencies = {"NOMINAL", "WATCH", "ALERT", "CRITICAL"}
        if output.urgency not in valid_urgencies:
            violations.append(f"Invalid urgency: {output.urgency}")

        # Check regime/I_t consistency
        regime_match = ConsistencyChecker._check_regime_threshold(
            output.instability_score, output.regime
        )
        if not regime_match:
            violations.append(
                f"regime '{output.regime}' inconsistent with I_t={output.instability_score:.3f}"
            )

        # Check urgency/regime/velocity consistency
        urgency_match = ConsistencyChecker._check_urgency_consistency(
            output.regime, output.urgency, output.drift_velocity
        )
        if not urgency_match:
            violations.append(
                f"urgency '{output.urgency}' inconsistent with regime='{output.regime}', V_t={output.drift_velocity:.4f}"
            )

        return len(violations) == 0, violations

    @staticmethod
    def _check_regime_threshold(I_t: float, regime: str) -> bool:
        """Check if regime matches I_t thresholds."""
        if regime == "WARMUP":
            return True

        return (
            (regime == "STABLE" and I_t <= 0.30)
            or (regime == "TRANSITION" and 0.30 < I_t <= 0.65)
            or (regime == "UNSTABLE" and 0.65 < I_t <= 0.85)
            or (regime == "LOCK_IN" and I_t > 0.85)
        )

    @staticmethod
    def _check_urgency_consistency(regime: str, urgency: str, velocity: float) -> bool:
        """Check if urgency matches regime + velocity."""
        abs_v = abs(velocity)

        if regime == "LOCK_IN":
            return urgency == "CRITICAL"
        elif regime == "UNSTABLE":
            return urgency == "ALERT"
        elif regime == "TRANSITION":
            return (abs_v > 0.1 and urgency == "ALERT") or (abs_v <= 0.1 and urgency == "WATCH")
        elif regime == "STABLE":
            return (abs_v > 0.05 and urgency == "WATCH") or (abs_v <= 0.05 and urgency == "NOMINAL")
        elif regime == "WARMUP":
            return urgency == "NOMINAL"

        return False

    @staticmethod
    def build_debug_frame(
        sii_output: SIIEngineOutput,
        previous_output: Optional[SIIEngineOutput] = None,
        sensor_vector_size: int = 0,
        sensor_norm: float = 0.0,
    ) -> DebugFrame:
        """Build a debug frame from SIIEngineOutput."""
        is_valid, violations = ConsistencyChecker.validate_sii_output(
            sii_output, previous_output
        )

        regime_threshold = {
            "min": 0.0,
            "max": 1.0,
        }
        if sii_output.regime == "STABLE":
            regime_threshold = {"min": 0.0, "max": 0.30}
        elif sii_output.regime == "TRANSITION":
            regime_threshold = {"min": 0.30, "max": 0.65}
        elif sii_output.regime == "UNSTABLE":
            regime_threshold = {"min": 0.65, "max": 0.85}
        elif sii_output.regime == "LOCK_IN":
            regime_threshold = {"min": 0.85, "max": 1.0}

        abs_v = abs(sii_output.drift_velocity)
        urgency_criteria = {
            f"regime == 'LOCK_IN'": sii_output.regime == "LOCK_IN",
            f"regime == 'UNSTABLE'": sii_output.regime == "UNSTABLE",
            f"regime == 'TRANSITION' and |V_t| > 0.1": (
                sii_output.regime == "TRANSITION" and abs_v > 0.1
            ),
            f"regime == 'TRANSITION' and |V_t| <= 0.1": (
                sii_output.regime == "TRANSITION" and abs_v <= 0.1
            ),
            f"regime == 'STABLE' and |V_t| > 0.05": (
                sii_output.regime == "STABLE" and abs_v > 0.05
            ),
            f"regime == 'STABLE' and |V_t| <= 0.05": (
                sii_output.regime == "STABLE" and abs_v <= 0.05
            ),
        }

        regime_match = ConsistencyChecker._check_regime_threshold(
            sii_output.instability_score, sii_output.regime
        )
        urgency_match = ConsistencyChecker._check_urgency_consistency(
            sii_output.regime, sii_output.urgency, sii_output.drift_velocity
        )

        # Breakdown using exact engine formula: I_t = α·S_t + β·|tanh(V_t)| + γ·P_t
        import math
        weights = {
            "drift_weight": 0.40,
            "velocity_weight": 0.35,
            "pressure_weight": 0.25,
        }
        breakdown = {
            "drift_contribution": weights["drift_weight"] * sii_output.structural_drift,
            "velocity_contribution": weights["velocity_weight"]
            * abs(math.tanh(sii_output.drift_velocity)),
            "pressure_contribution": weights["pressure_weight"]
            * sii_output.transition_pressure,
        }

        return DebugFrame(
            timestamp=sii_output.timestamp,
            cycle=0,  # Will be filled by caller if needed
            sensor_vector_size=sensor_vector_size,
            sensor_norm=sensor_norm,
            structural_drift=sii_output.structural_drift,
            drift_velocity=sii_output.drift_velocity,
            transition_pressure=sii_output.transition_pressure,
            recovery_alignment=sii_output.recovery_alignment,
            instability_score=sii_output.instability_score,
            instability_score_breakdown=breakdown,
            regime=sii_output.regime,
            regime_threshold_range=regime_threshold,
            regime_match=regime_match,
            urgency=sii_output.urgency,
            urgency_criteria=urgency_criteria,
            urgency_match=urgency_match,
            confidence=sii_output.confidence,
            gradient_norm=sii_output.gradient_norm,
            regime_changed=(
                previous_output is not None and previous_output.regime != sii_output.regime
            ),
            urgency_changed=(
                previous_output is not None and previous_output.urgency != sii_output.urgency
            ),
            previous_regime=previous_output.regime if previous_output else None,
            previous_urgency=previous_output.urgency if previous_output else None,
            all_constraints_satisfied=is_valid,
            constraint_violations=violations,
        )


class DebugLogger:
    """Manages debug logging."""

    def __init__(self, enabled: bool = False, log_file: Optional[str] = None):
        self.enabled = enabled
        self.frames: list[DebugFrame] = []
        self.log_file = log_file

        if log_file:
            self.logger = logging.getLogger("sii_debug")
            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger = None

    def log_frame(self, frame: DebugFrame) -> None:
        """Log a debug frame."""
        if not self.enabled:
            return

        self.frames.append(frame)

        if self.logger:
            self.logger.debug(frame.to_json())

    def export_audit_trail(self, output_path: str) -> None:
        """Export complete audit trail."""
        with open(output_path, "w") as f:
            for frame in self.frames:
                f.write(frame.to_human_readable())
                f.write("\n")

        print(f"Audit trail exported to {output_path}")

    def summary(self) -> str:
        """Generate summary of all logged frames."""
        if not self.frames:
            return "No frames logged."

        total = len(self.frames)
        violations = sum(
            1 for f in self.frames if not f.all_constraints_satisfied
        )

        return (
            f"Debug Summary: {total} frames logged, "
            f"{violations} constraint violations found"
        )


__all__ = [
    "ConsistencyChecker",
    "DebugFrame",
    "DebugLogger",
]
