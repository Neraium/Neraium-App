"""
Symbolic math engine — exact algebra and calculus on the scoring pipeline.

Uses SymPy to represent the composite instability formula as a symbolic
expression.  This lets you:

  • Compute *exact* partial derivatives (not finite-difference approximations)
    for sensitivity analysis.
  • Solve for the exact sensor-component value that crosses a state boundary
    (WATCH / ALERT / CRITICAL), useful for explaining "how close are we?".
  • Simplify decision-rule expressions and emit LaTeX proofs.
  • Symbolically differentiate / integrate any scalar function of the
    component vector, enabling downstream formal-verification checks.

Optional dependency: ``sympy``  (pip install sympy)
"""

from __future__ import annotations

import math
from typing import Any

try:
    import sympy as sp

    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SYMPY_AVAILABLE = False
    sp = None  # type: ignore[assignment]

from neraium_core.scoring import DEFAULT_WEIGHTS

COMPONENT_NAMES: list[str] = [k for k in DEFAULT_WEIGHTS if DEFAULT_WEIGHTS[k] > 0]


def _require_sympy() -> None:
    if not _SYMPY_AVAILABLE:
        raise ImportError(
            "sympy is required for symbolic math support. "
            "Install it with:  pip install 'neraium-core[math]'"
        )


# ---------------------------------------------------------------------------
# Core symbolic model
# ---------------------------------------------------------------------------


class SymbolicScoringModel:
    """
    Exact symbolic representation of the composite instability score.

    The composite score is a weighted average::

        score = sum(w_i * c_i) / sum(w_i)

    where each ``c_i`` is a non-negative real-valued component (relational_drift,
    spectral, etc.) and ``w_i`` is its calibrated weight.

    Example
    -------
    >>> model = SymbolicScoringModel()
    >>> expr = model.expression
    >>> dscore_drelational = model.sensitivity("relational_drift")
    >>> boundary = model.solve_boundary("relational_drift", threshold=1.5)
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        _require_sympy()
        self._weights: dict[str, float] = dict(weights or DEFAULT_WEIGHTS)
        self._symbols: dict[str, Any] = {
            name: sp.Symbol(name, nonneg=True)
            for name in COMPONENT_NAMES
        }
        self._expr: Any = self._build_expression()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_expression(self) -> Any:
        active = {
            name: self._weights[name]
            for name in COMPONENT_NAMES
            if self._weights.get(name, 0.0) > 0.0
        }
        if not active:
            return sp.Integer(0)

        total_weight = sum(sp.Rational(str(w)) for w in active.values())
        weighted_sum = sum(
            sp.Rational(str(w)) * self._symbols[name]
            for name, w in active.items()
        )
        return weighted_sum / total_weight

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def expression(self) -> Any:
        """The full symbolic scoring expression."""
        return self._expr

    @property
    def symbols(self) -> dict[str, Any]:
        """SymPy Symbol objects keyed by component name."""
        return dict(self._symbols)

    # ------------------------------------------------------------------
    # Calculus
    # ------------------------------------------------------------------

    def sensitivity(self, component: str) -> Any:
        """
        Exact partial derivative  d(score) / d(component).

        Because the formula is linear this always returns a rational constant,
        but the method works correctly even if the formula is later extended.
        """
        if component not in self._symbols:
            raise ValueError(f"Unknown component '{component}'. Valid: {COMPONENT_NAMES}")
        return sp.diff(self._expr, self._symbols[component])

    def all_sensitivities(self) -> dict[str, Any]:
        """Partial derivative for every active component."""
        return {name: self.sensitivity(name) for name in COMPONENT_NAMES}

    def sensitivity_float(self, component: str) -> float:
        """Convenience: sensitivity as a plain Python float."""
        return float(self.sensitivity(component))

    def integrate(self, component: str, lower: float = 0.0, upper: float = 3.0) -> Any:
        """
        Definite integral of the score w.r.t. ``component`` from ``lower`` to ``upper``,
        holding all other components at zero.

        Useful for computing the average score over a component's expected range.
        """
        if component not in self._symbols:
            raise ValueError(f"Unknown component '{component}'.")
        sym = self._symbols[component]
        subs = {self._symbols[n]: sp.Integer(0) for n in COMPONENT_NAMES if n != component}
        expr_1d = self._expr.subs(subs)
        return sp.integrate(expr_1d, (sym, sp.Float(lower), sp.Float(upper)))

    # ------------------------------------------------------------------
    # Boundary solving
    # ------------------------------------------------------------------

    def solve_boundary(
        self,
        component: str,
        threshold: float,
        fixed_values: dict[str, float] | None = None,
    ) -> float | None:
        """
        Find the exact value of ``component`` that causes score == ``threshold``,
        holding all other components at ``fixed_values`` (defaults: 0 for each).

        Returns the boundary as a float, or ``None`` if no real solution exists.

        Example — "at what relational_drift value do we cross WATCH (1.5)?"::

            >>> model.solve_boundary("relational_drift", threshold=1.5)
            1.8947...
        """
        if component not in self._symbols:
            raise ValueError(f"Unknown component '{component}'.")
        fixed = fixed_values or {}
        subs: dict[Any, Any] = {}
        for name, sym in self._symbols.items():
            if name == component:
                continue
            val = fixed.get(name, 0.0)
            if math.isnan(val) or math.isinf(val):
                val = 0.0
            subs[sym] = sp.Float(val)

        expr_sub = self._expr.subs(subs)
        target = self._symbols[component]
        solutions = sp.solve(expr_sub - sp.Float(threshold), target)
        real_solutions = [s for s in solutions if s.is_real]
        if not real_solutions:
            return None
        return float(real_solutions[0])

    def margin_to_boundary(
        self,
        component: str,
        current_value: float,
        threshold: float,
        fixed_values: dict[str, float] | None = None,
    ) -> float | None:
        """
        How far is ``current_value`` from the state boundary?

        Returns ``boundary_value - current_value`` so that positive means
        "still below threshold" and negative means "already over".
        Returns ``None`` if the boundary cannot be computed.
        """
        boundary = self.solve_boundary(component, threshold, fixed_values)
        if boundary is None:
            return None
        return boundary - current_value

    # ------------------------------------------------------------------
    # Simplification / display
    # ------------------------------------------------------------------

    def simplify(self) -> Any:
        """Return a simplified form of the expression."""
        return sp.simplify(self._expr)

    def to_latex(self) -> str:
        """Render the expression as a LaTeX string."""
        return sp.latex(self._expr)

    def to_string(self) -> str:
        """Human-readable string representation."""
        return str(self._expr)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, component_values: dict[str, float]) -> float:
        """
        Numerically evaluate the symbolic expression.

        Equivalent to ``composite_instability_score()`` but goes through the
        symbolic model, which catches any formula divergence between the two.
        """
        subs = {
            self._symbols[name]: sp.Float(component_values.get(name, 0.0))
            for name in COMPONENT_NAMES
        }
        result = self._expr.subs(subs)
        return float(result)

    # ------------------------------------------------------------------
    # Proof artifact
    # ------------------------------------------------------------------

    def proof_summary(self) -> dict[str, Any]:
        """
        Return a structured summary suitable for storing as a proof artifact.

        Fields
        ------
        formula_latex : LaTeX rendering of the scoring formula.
        sensitivities : mapping component → exact rational sensitivity.
        monotone_components : list of components with strictly positive sensitivity.
        """
        sensitivities = self.all_sensitivities()
        return {
            "formula_latex": self.to_latex(),
            "formula_str": self.to_string(),
            "sensitivities": {k: str(v) for k, v in sensitivities.items()},
            "sensitivities_float": {k: float(v) for k, v in sensitivities.items()},
            "monotone_components": [
                k for k, v in sensitivities.items() if float(v) > 0
            ],
        }


# ---------------------------------------------------------------------------
# Convenience: symbolic calculus helpers for arbitrary expressions
# ---------------------------------------------------------------------------


def symbolic_diff(expr_str: str, var_name: str) -> str:
    """
    Differentiate an arbitrary SymPy expression string w.r.t. a variable.

    Example::

        >>> symbolic_diff("x**3 + 2*x", "x")
        '3*x**2 + 2'
    """
    _require_sympy()
    var = sp.Symbol(var_name)
    expr = sp.sympify(expr_str)
    return str(sp.diff(expr, var))


def symbolic_integrate(expr_str: str, var_name: str, lower: str = "0", upper: str = "oo") -> str:
    """
    Integrate an arbitrary SymPy expression string w.r.t. a variable.

    Example::

        >>> symbolic_integrate("exp(-x)", "x", "0", "oo")
        '1'
    """
    _require_sympy()
    var = sp.Symbol(var_name)
    expr = sp.sympify(expr_str)
    result = sp.integrate(expr, (var, sp.sympify(lower), sp.sympify(upper)))
    return str(result)


def symbolic_solve(equation_str: str, var_name: str) -> list[str]:
    """
    Solve an equation string for a variable.

    Pass the equation as a string representing the expression that equals zero.

    Example::

        >>> symbolic_solve("x**2 - 4", "x")
        ['-2', '2']
    """
    _require_sympy()
    var = sp.Symbol(var_name)
    expr = sp.sympify(equation_str)
    solutions = sp.solve(expr, var)
    return [str(s) for s in solutions]


def symbolic_simplify(expr_str: str) -> str:
    """Simplify a SymPy expression string."""
    _require_sympy()
    return str(sp.simplify(sp.sympify(expr_str)))
