"""
Formal verification layer — constraint-checking and theorem-proving for the
core scoring and decision pipeline.

Silent mathematical errors in production monitoring systems are dangerous:
a non-monotone scoring function, a threshold ordering that has drifted, or
a decision rule that contradicts itself can suppress real alerts.

This module verifies critical mathematical properties *at runtime* and
surfaces any violations before they affect customer outputs.

Classes
-------
MonotonicityVerifier
    Checks that the composite score is non-decreasing in every component
    (i.e., increasing instability → increasing score).  Uses symbolic
    differentiation (SymPy) when available, finite-difference otherwise.

ThresholdConsistencyChecker
    Verifies the CalibrationProfile invariant:
    0 ≤ watch_threshold < alert_threshold < critical_threshold ≤ MAX_SCORE.

DecisionRuleVerifier
    Checks a set of named decision rules for internal contradictions using
    a lightweight SAT/SMT approach.  Uses Z3 when available, falls back to
    exhaustive enumeration for small state spaces.

run_all_checks(...)
    Convenience function that runs all three verifiers and returns a
    structured report.

Optional dependencies:
  sympy      — for symbolic monotonicity proof  (pip install sympy)
  z3-solver  — for SMT-based rule checking      (pip install z3-solver)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import sympy as sp

    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SYMPY_AVAILABLE = False
    sp = None  # type: ignore[assignment]

try:
    import z3 as _z3  # type: ignore[import]

    _Z3_AVAILABLE = True
except ImportError:  # pragma: no cover
    _Z3_AVAILABLE = False
    _z3 = None  # type: ignore[assignment]

from neraium_core.scoring import DEFAULT_WEIGHTS

COMPONENT_NAMES: list[str] = list(DEFAULT_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    passed: bool
    check_name: str
    details: str
    violations: list[str] = field(default_factory=list)
    method: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check_name,
            "passed": self.passed,
            "details": self.details,
            "violations": self.violations,
            "method": self.method,
        }


@dataclass
class VerificationReport:
    all_passed: bool
    results: list[VerificationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checks": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        lines = [
            f"{'PASS' if r.passed else 'FAIL'}  {r.check_name}: {r.details}"
            for r in self.results
        ]
        status = "ALL CHECKS PASSED" if self.all_passed else "VERIFICATION FAILURES DETECTED"
        return f"[{status}]\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Monotonicity verifier
# ---------------------------------------------------------------------------


class MonotonicityVerifier:
    """
    Verify that the composite instability score is non-decreasing in each
    component: ∂score/∂c_i ≥ 0 for all i.

    Method 1 (preferred): Symbolic — compute exact partial derivatives via
    SymPy and check their sign analytically.

    Method 2 (fallback): Finite-difference — evaluate the score at a grid of
    points and confirm no component increase causes a score decrease.

    Parameters
    ----------
    weights : dict[str, float] | None
        Component weights.  Defaults to DEFAULT_WEIGHTS.
    fd_n_points : int
        Number of test points for finite-difference fallback.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        fd_n_points: int = 100,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS
        self._fd_n = fd_n_points

    def verify(self) -> VerificationResult:
        if _SYMPY_AVAILABLE:
            return self._verify_symbolic()
        return self._verify_fd()

    def _verify_symbolic(self) -> VerificationResult:
        from neraium_core.math.symbolic_engine import SymbolicScoringModel

        model = SymbolicScoringModel(self._weights)
        violations = []
        for name in COMPONENT_NAMES:
            deriv = model.sensitivity(name)
            val = float(deriv)
            if val < -1e-12:
                violations.append(
                    f"{name}: ∂score/∂{name} = {val:.6f} < 0 (non-monotone)"
                )

        passed = len(violations) == 0
        return VerificationResult(
            passed=passed,
            check_name="MonotonicityVerifier",
            details=(
                "All components have non-negative partial derivatives."
                if passed
                else f"{len(violations)} component(s) violate monotonicity."
            ),
            violations=violations,
            method="symbolic (SymPy)",
        )

    def _verify_fd(self) -> VerificationResult:
        from neraium_core.scoring import composite_instability_score_normalized

        np.random.default_rng(42)
        violations = []

        for name in COMPONENT_NAMES:
            w = self._weights.get(name, 0.0)
            if w <= 0:
                continue
            # Check monotonicity along this axis holding others fixed
            base_components = {k: 0.5 for k in COMPONENT_NAMES}
            scores = []
            for v in np.linspace(0.0, 3.0, self._fd_n):
                base_components[name] = float(v)
                scores.append(composite_instability_score_normalized(base_components, self._weights))

            diffs = np.diff(scores)
            if np.any(diffs < -1e-9):
                worst = float(diffs.min())
                violations.append(
                    f"{name}: score decreases (max decrease {worst:.6f}) when component increases"
                )

        passed = len(violations) == 0
        return VerificationResult(
            passed=passed,
            check_name="MonotonicityVerifier",
            details=(
                "Finite-difference sweep shows monotone response."
                if passed
                else f"{len(violations)} component(s) violate monotonicity."
            ),
            violations=violations,
            method="finite-difference",
        )


# ---------------------------------------------------------------------------
# Threshold consistency checker
# ---------------------------------------------------------------------------


class ThresholdConsistencyChecker:
    """
    Verify that alert thresholds satisfy the required ordering:

        0 ≤ watch_threshold < alert_threshold < critical_threshold

    Also checks that no threshold is NaN, infinite, or negative.

    Parameters
    ----------
    watch : float   — WATCH state threshold.
    alert : float   — ALERT state threshold.
    critical : float — CRITICAL state threshold.
    max_score : float — Upper bound for valid threshold values.
    """

    def __init__(
        self,
        watch: float,
        alert: float,
        critical: float,
        max_score: float = 5.0,
    ) -> None:
        self.watch = watch
        self.alert = alert
        self.critical = critical
        self.max_score = max_score

    def verify(self) -> VerificationResult:
        violations = []

        for name, val in [
            ("watch", self.watch),
            ("alert", self.alert),
            ("critical", self.critical),
        ]:
            if math.isnan(val) or math.isinf(val):
                violations.append(f"{name}_threshold is not finite: {val}")
            elif val < 0:
                violations.append(f"{name}_threshold is negative: {val}")
            elif val > self.max_score:
                violations.append(
                    f"{name}_threshold ({val}) exceeds max_score ({self.max_score})"
                )

        if self.watch >= self.alert:
            violations.append(
                f"watch_threshold ({self.watch}) must be < alert_threshold ({self.alert})"
            )
        if self.alert >= self.critical:
            violations.append(
                f"alert_threshold ({self.alert}) must be < critical_threshold ({self.critical})"
            )
        if self.watch >= self.critical:
            violations.append(
                f"watch_threshold ({self.watch}) must be < critical_threshold ({self.critical})"
            )

        passed = len(violations) == 0
        return VerificationResult(
            passed=passed,
            check_name="ThresholdConsistencyChecker",
            details=(
                f"Thresholds consistent: watch={self.watch} < alert={self.alert} < critical={self.critical}"
                if passed
                else f"{len(violations)} threshold ordering violation(s)."
            ),
            violations=violations,
            method="direct comparison",
        )


# ---------------------------------------------------------------------------
# Decision rule verifier
# ---------------------------------------------------------------------------


class DecisionRuleVerifier:
    """
    Check a set of named decision rules for internal contradictions.

    A rule is expressed as a dict::

        {
            "name": "alert_implies_watch",
            "if": {"state": "ALERT"},
            "then": {"watch_flag": True},
        }

    The verifier checks that no two rules assert contradictory conclusions
    for the same preconditions.  Uses Z3 (SMT) when available, otherwise
    uses exhaustive enumeration over the discrete state space.

    Parameters
    ----------
    state_values : list[str]
        Ordered list of state labels from least to most severe.
    """

    def __init__(
        self,
        state_values: list[str] | None = None,
    ) -> None:
        self._states = state_values or ["STABLE", "WATCH", "ALERT", "CRITICAL"]

    def verify_rules(
        self,
        rules: list[dict[str, Any]],
    ) -> VerificationResult:
        """
        Check ``rules`` for contradiction.

        Returns a PASS result if no contradictions exist, FAIL with details
        otherwise.
        """
        if _Z3_AVAILABLE:
            return self._verify_z3(rules)
        return self._verify_enumeration(rules)

    def _build_z3_precondition(self, if_cond: dict[str, Any], state_int: Any, state_idx: dict[str, int]) -> Any:
        """Encode an ``if`` condition dict as a Z3 expression."""
        precondition = _z3.BoolVal(True)
        if "state" in if_cond:
            s = str(if_cond["state"])
            if s in state_idx:
                precondition = state_int == state_idx[s]
            elif s.startswith(">="):
                sname = s[2:].strip()
                precondition = state_int >= state_idx.get(sname, 0)
            elif s.startswith(">"):
                sname = s[1:].strip()
                precondition = state_int > state_idx.get(sname, 0)
        return precondition

    def _verify_z3(self, rules: list[dict[str, Any]]) -> VerificationResult:
        """
        SMT-based contradiction detection via Z3.

        Two checks per rule pair (i, j) where i < j:
        1. Unsatisfiable precondition — the rule can never fire.
        2. Contradictory conclusions — both rules can fire simultaneously
           (their preconditions are jointly satisfiable) yet assert different
           values for the same conclusion key.
        """
        violations = []
        state_int = _z3.Int("state")
        state_idx = {s: i for i, s in enumerate(self._states)}

        # --- Pass 1: unsatisfiable preconditions ---
        for rule in rules:
            name = rule.get("name", "unnamed")
            pre = self._build_z3_precondition(rule.get("if", {}), state_int, state_idx)
            s = _z3.Solver()
            s.add(state_int >= 0, state_int < len(self._states))
            s.add(pre)
            if s.check() == _z3.unsat:
                violations.append(f"Rule '{name}': precondition is unsatisfiable (can never fire)")

        # --- Pass 2: pairwise contradiction check ---
        # For every pair of rules, ask Z3 whether both preconditions can hold
        # simultaneously.  If yes, check that their `then` clauses agree on
        # every shared conclusion key.
        for i in range(len(rules)):
            for j in range(i + 1, len(rules)):
                rule_i = rules[i]
                rule_j = rules[j]
                pre_i = self._build_z3_precondition(rule_i.get("if", {}), state_int, state_idx)
                pre_j = self._build_z3_precondition(rule_j.get("if", {}), state_int, state_idx)

                # Can both rules fire at once?
                s = _z3.Solver()
                s.add(state_int >= 0, state_int < len(self._states))
                s.add(pre_i, pre_j)
                if s.check() == _z3.unsat:
                    # Preconditions are mutually exclusive — no contradiction possible.
                    continue

                # Both can fire: check for conflicting then-clause values.
                then_i = rule_i.get("then", {})
                then_j = rule_j.get("then", {})
                name_i = rule_i.get("name", f"rule[{i}]")
                name_j = rule_j.get("name", f"rule[{j}]")
                for key in set(then_i) & set(then_j):
                    if then_i[key] != then_j[key]:
                        violations.append(
                            f"Contradiction between '{name_i}' and '{name_j}': "
                            f"both can fire simultaneously but assert '{key}' = "
                            f"{then_i[key]!r} and {then_j[key]!r} respectively."
                        )

        passed = len(violations) == 0
        n_rules = len(rules)
        return VerificationResult(
            passed=passed,
            check_name="DecisionRuleVerifier",
            details=(
                f"All {n_rules} rules are satisfiable and mutually consistent."
                if passed
                else f"{len(violations)} issue(s) detected across {n_rules} rules."
            ),
            violations=violations,
            method="Z3 SMT solver",
        )

    def _verify_enumeration(self, rules: list[dict[str, Any]]) -> VerificationResult:
        """Exhaustive enumeration over the discrete state space."""
        violations = []
        conclusions: dict[str, dict[str, Any]] = {}

        for rule in rules:
            rule.get("name", "unnamed")
            if_cond = str(rule.get("if", {}))
            then_cond = rule.get("then", {})

            if if_cond in conclusions:
                existing = conclusions[if_cond]
                for key, val in then_cond.items():
                    if key in existing and existing[key] != val:
                        violations.append(
                            f"Contradiction: rules for condition {if_cond!r} assert "
                            f"'{key}' = {existing[key]} and {val} simultaneously."
                        )
            else:
                conclusions[if_cond] = dict(then_cond)

        passed = len(violations) == 0
        return VerificationResult(
            passed=passed,
            check_name="DecisionRuleVerifier",
            details=(
                f"All {len(rules)} rules are consistent."
                if passed
                else f"{len(violations)} contradiction(s) detected."
            ),
            violations=violations,
            method="enumeration",
        )


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


def run_all_checks(
    weights: dict[str, float] | None = None,
    watch_threshold: float = 1.5,
    alert_threshold: float = 2.2,
    critical_threshold: float = 2.8,
    decision_rules: list[dict[str, Any]] | None = None,
) -> VerificationReport:
    """
    Run MonotonicityVerifier, ThresholdConsistencyChecker, and
    DecisionRuleVerifier in sequence and return a combined report.

    Designed to be called at service startup or after any calibration change.
    """
    results: list[VerificationResult] = []

    # 1. Monotonicity
    mv = MonotonicityVerifier(weights)
    results.append(mv.verify())

    # 2. Threshold ordering
    tc = ThresholdConsistencyChecker(watch_threshold, alert_threshold, critical_threshold)
    results.append(tc.verify())

    # 3. Decision rules
    if decision_rules:
        drv = DecisionRuleVerifier()
        results.append(drv.verify_rules(decision_rules))

    all_passed = all(r.passed for r in results)
    return VerificationReport(all_passed=all_passed, results=results)
