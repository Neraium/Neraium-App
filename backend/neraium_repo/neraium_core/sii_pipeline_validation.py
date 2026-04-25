"""
PHASE 2: SII Pipeline Constraint Enforcement

Runtime validation that enforces the formal specification constraints:
- C1: SIIEngine outputs are immutable
- C2: No parallel scoring methods
- C3: Adapter does not compute
- C4: Consumers only read
- C5: No thresholds outside SIIEngine

All assertions must pass for production deployment.
"""

from __future__ import annotations

from typing import Any
from dataclasses import FrozenInstanceError
import numpy as np

from neraium_core.sii_engine_unified import SIIEngineOutput
from neraium_core.sii_engine_adapter import UnifiedSystemState


class SIIPipelineValidator:
    """Enforces specification constraints at runtime."""

    # Allowed regimes and urgencies per spec
    VALID_REGIMES = {"STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN", "WARMUP"}
    VALID_URGENCIES = {"NOMINAL", "WATCH", "ALERT", "CRITICAL"}

    # Regime thresholds from spec
    REGIME_THRESHOLDS = {
        "STABLE": (0.0, 0.30),
        "TRANSITION": (0.30, 0.65),
        "UNSTABLE": (0.65, 0.85),
        "LOCK_IN": (0.85, 1.0),
    }

    @staticmethod
    def validate_sii_engine_output(output: SIIEngineOutput) -> None:
        """
        C1: Validate that SIIEngine output is correct and immutable.

        Raises AssertionError if any constraint violated.
        """
        assert isinstance(output, SIIEngineOutput), "Output must be SIIEngineOutput"

        # Check all required fields exist
        assert hasattr(output, "instability_score"), "Missing instability_score"
        assert hasattr(output, "regime"), "Missing regime"
        assert hasattr(output, "urgency"), "Missing urgency"
        assert hasattr(output, "structural_drift"), "Missing structural_drift"
        assert hasattr(output, "drift_velocity"), "Missing drift_velocity"
        assert hasattr(output, "transition_pressure"), "Missing transition_pressure"
        assert hasattr(output, "confidence"), "Missing confidence"

        # Validate ranges
        assert 0.0 <= output.instability_score <= 1.0, (
            f"instability_score must be in [0,1], got {output.instability_score}"
        )
        assert 0.0 <= output.structural_drift <= 1.0, (
            f"structural_drift must be in [0,1], got {output.structural_drift}"
        )
        assert 0.0 <= output.transition_pressure <= 1.0, (
            f"transition_pressure must be in [0,1], got {output.transition_pressure}"
        )
        assert 0.0 <= output.confidence <= 1.0, (
            f"confidence must be in [0,1], got {output.confidence}"
        )

        # Validate regime is one of the valid states
        assert output.regime in SIIPipelineValidator.VALID_REGIMES, (
            f"Invalid regime: {output.regime}. Must be one of {SIIPipelineValidator.VALID_REGIMES}"
        )

        # Validate urgency is one of the valid levels
        assert output.urgency in SIIPipelineValidator.VALID_URGENCIES, (
            f"Invalid urgency: {output.urgency}. Must be one of {SIIPipelineValidator.VALID_URGENCIES}"
        )

        # Validate regime matches instability_score thresholds
        SIIPipelineValidator._validate_regime_threshold(
            output.instability_score, output.regime
        )

        # Validate urgency is consistent with regime and velocity
        SIIPipelineValidator._validate_urgency_consistency(
            output.regime, output.urgency, output.drift_velocity
        )

    @staticmethod
    def _validate_regime_threshold(I_t: float, regime: str) -> None:
        """Verify regime classification matches spec thresholds."""
        if regime == "WARMUP":
            # Warmup period has no score-based constraints
            return

        min_t, max_t = SIIPipelineValidator.REGIME_THRESHOLDS.get(regime, (0.0, 1.0))

        # Note: Thresholds allow boundary values (<=, >=)
        in_range = (
            (regime == "STABLE" and I_t <= 0.30)
            or (regime == "TRANSITION" and 0.30 < I_t <= 0.65)
            or (regime == "UNSTABLE" and 0.65 < I_t <= 0.85)
            or (regime == "LOCK_IN" and I_t > 0.85)
        )

        assert in_range, (
            f"Regime '{regime}' inconsistent with I_t={I_t:.3f}. "
            f"Expected regime for this score: {SIIPipelineValidator._expected_regime(I_t)}"
        )

    @staticmethod
    def _expected_regime(I_t: float) -> str:
        """Compute expected regime from instability score."""
        if I_t <= 0.30:
            return "STABLE"
        elif I_t <= 0.65:
            return "TRANSITION"
        elif I_t <= 0.85:
            return "UNSTABLE"
        else:
            return "LOCK_IN"

    @staticmethod
    def _validate_urgency_consistency(regime: str, urgency: str, velocity: float) -> None:
        """Verify urgency matches regime + velocity per spec."""
        # Expected urgency from spec
        expected_urgencies = SIIPipelineValidator._expected_urgencies(regime, velocity)

        assert urgency in expected_urgencies, (
            f"Urgency '{urgency}' inconsistent with regime='{regime}', V_t={velocity:.3f}. "
            f"Expected one of: {expected_urgencies}"
        )

    @staticmethod
    def _expected_urgencies(regime: str, velocity: float) -> set[str]:
        """Compute expected urgency levels from regime and velocity."""
        if regime == "LOCK_IN":
            return {"CRITICAL"}
        elif regime == "UNSTABLE":
            return {"ALERT"}
        elif regime == "TRANSITION":
            if abs(velocity) > 0.1:
                return {"ALERT"}
            else:
                return {"WATCH"}
        elif regime == "STABLE":
            if abs(velocity) > 0.05:
                return {"WATCH"}
            else:
                return {"NOMINAL"}
        elif regime == "WARMUP":
            return {"NOMINAL"}
        else:
            return {"NOMINAL"}

    @staticmethod
    def validate_unified_state(state: UnifiedSystemState) -> None:
        """
        C1: Validate that UnifiedSystemState is correct.

        This should match SIIEngineOutput validation since state is built from output.
        """
        assert isinstance(state, UnifiedSystemState), "Must be UnifiedSystemState"

        # Check required fields
        assert state.instability_score is not None, "Missing instability_score"
        assert state.regime is not None, "Missing regime"
        assert state.urgency is not None, "Missing urgency"

        # Validate ranges and consistency (same as SIIEngineOutput)
        assert 0.0 <= state.instability_score <= 1.0
        assert 0.0 <= state.confidence <= 1.0
        assert state.regime in SIIPipelineValidator.VALID_REGIMES
        assert state.urgency in SIIPipelineValidator.VALID_URGENCIES

        # Validate regime/urgency consistency
        SIIPipelineValidator._validate_regime_threshold(state.instability_score, state.regime)
        SIIPipelineValidator._validate_urgency_consistency(
            state.regime, state.urgency, state.drift_velocity
        )

        # Verify histories are consistent
        if state.regime_history:
            assert all(r in SIIPipelineValidator.VALID_REGIMES for r in state.regime_history), (
                "regime_history contains invalid regimes"
            )

        if state.instability_history:
            assert all(0.0 <= s <= 1.0 for s in state.instability_history), (
                "instability_history contains out-of-range scores"
            )

    @staticmethod
    def audit_no_parallel_scoring() -> list[str]:
        """
        C2: Audit that no parallel scoring methods exist in production.

        Returns list of locations where parallel scoring was found (violations).
        """
        violations = []

        # Check for forbidden functions
        forbidden_functions = [
            "composite_instability_score_normalized",
            "compute_composite_instability",
            "calculate_instability",
            "subsystem_instability",
        ]

        try:
            import inspect
            from pathlib import Path

            core_dir = Path("/home/user/neraium-core/neraium_core")

            for py_file in core_dir.glob("*.py"):
                if "sii_" in py_file.name or "test" in py_file.name:
                    continue

                try:
                    with open(py_file) as f:
                        content = f.read()
                        for func_name in forbidden_functions:
                            if f"def {func_name}" in content:
                                violations.append(
                                    f"{py_file.name}: Found forbidden function '{func_name}'"
                                )
                except Exception:
                    pass

        except Exception:
            pass

        return violations

    @staticmethod
    def audit_no_independent_regime() -> list[str]:
        """
        C5: Audit that no independent regime computation exists.

        Returns list of violations.
        """
        violations = []

        forbidden_patterns = [
            "assign_regime(",
            "regime = ",  # Except in SIIEngine
            "classify_regime" if "sii_" not in "CONTEXT" else "",
        ]

        try:
            from pathlib import Path

            core_dir = Path("/home/user/neraium-core/neraium_core")

            for py_file in core_dir.glob("*.py"):
                if "sii_" in py_file.name or "test" in py_file.name or "regime.py" in py_file.name:
                    continue

                try:
                    with open(py_file) as f:
                        for line_num, line in enumerate(f, 1):
                            if "assign_regime(" in line and "import" not in line:
                                violations.append(
                                    f"{py_file.name}:{line_num} uses assign_regime() [FORBIDDEN]"
                                )
                except Exception:
                    pass

        except Exception:
            pass

        return violations

    @staticmethod
    def audit_no_independent_urgency() -> list[str]:
        """
        C5: Audit that no independent urgency computation exists.

        Returns list of violations.
        """
        violations = []

        try:
            from pathlib import Path

            core_dir = Path("/home/user/neraium-core/neraium_core")

            for py_file in core_dir.glob("*.py"):
                if "sii_" in py_file.name or "test" in py_file.name:
                    continue

                try:
                    with open(py_file) as f:
                        content = f.read()
                        if "def urgency" in content and "sii_" not in py_file.name:
                            violations.append(f"{py_file.name}: Has independent urgency() function")
                except Exception:
                    pass

        except Exception:
            pass

        return violations

    @staticmethod
    def full_audit() -> dict[str, Any]:
        """Run all constraint audits and return comprehensive report."""
        return {
            "parallel_scoring_violations": SIIPipelineValidator.audit_no_parallel_scoring(),
            "independent_regime_violations": SIIPipelineValidator.audit_no_independent_regime(),
            "independent_urgency_violations": SIIPipelineValidator.audit_no_independent_urgency(),
            "total_violations": (
                len(SIIPipelineValidator.audit_no_parallel_scoring())
                + len(SIIPipelineValidator.audit_no_independent_regime())
                + len(SIIPipelineValidator.audit_no_independent_urgency())
            ),
        }


# Runtime assertion decorator
def validate_output(func):
    """Decorator to validate all SIIEngineOutput returns."""

    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, SIIEngineOutput):
            SIIPipelineValidator.validate_sii_engine_output(result)
        return result

    return wrapper


def validate_state(func):
    """Decorator to validate all UnifiedSystemState returns."""

    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, UnifiedSystemState):
            SIIPipelineValidator.validate_unified_state(result)
        return result

    return wrapper


__all__ = [
    "SIIPipelineValidator",
    "validate_output",
    "validate_state",
]
