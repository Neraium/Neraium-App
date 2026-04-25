"""
Advanced optimization engine — LP / QP / NLP / MIP solvers for the pipeline.

Uses SciPy's optimization suite (and optionally PuLP for MIP) to auto-formulate
and solve real-world planning and decision problems:

  CalibrationOptimizer  — Tune CalibrationProfile thresholds as a constrained
                          NLP problem: minimise false-alert rate subject to a
                          minimum detection-recall constraint.

  WeightOptimizer       — Optimise per-component scoring weights via gradient
                          descent NLP.  Useful when labelled ground-truth data
                          is available.

  PlanningOptimizer     — General LP/MIP helper for operational planning
                          problems (scheduling, resource allocation) that arise
                          in customer decision workflows.

  auto_formulate_lp     — Convert a plain dict description of variables,
                          objective, and constraints into a SciPy LinearProgramResult.

Optional dependency: ``scipy``  (pip install scipy)
Optional dependency: ``pulp``   (pip install pulp)   — only required for MIP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import scipy.optimize as _sopt

    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False
    _sopt = None  # type: ignore[assignment]

try:
    import pulp as _pulp  # type: ignore[import]

    _PULP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PULP_AVAILABLE = False
    _pulp = None  # type: ignore[assignment]

from neraium_core.scoring import DEFAULT_WEIGHTS

COMPONENT_NAMES: list[str] = list(DEFAULT_WEIGHTS.keys())


def _require_scipy() -> None:
    if not _SCIPY_AVAILABLE:
        raise ImportError(
            "scipy is required for optimization support. "
            "Install it with:  pip install 'neraium-core[math]'"
        )


def _require_pulp() -> None:
    if not _PULP_AVAILABLE:
        raise ImportError(
            "pulp is required for MIP support. "
            "Install it with:  pip install pulp"
        )


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class OptimizationResult:
    """Unified result object returned by all optimizers."""

    success: bool
    message: str
    objective_value: float
    solution: dict[str, float]
    iterations: int = 0
    solver: str = "scipy"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LPResult:
    """Result of a linear program."""

    status: str
    objective: float
    variables: dict[str, float]
    dual_values: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Calibration optimizer
# ---------------------------------------------------------------------------


class CalibrationOptimizer:
    """
    Tune CalibrationProfile thresholds via constrained NLP (SciPy minimize).

    Given a history of (component_vector, true_label) pairs, finds threshold
    values that minimise false-alert rate while keeping true-alert recall above
    a specified floor.

    Parameters
    ----------
    watch_threshold_init : float
        Starting value for the WATCH threshold.
    alert_threshold_init : float
        Starting value for the ALERT threshold.
    min_recall : float
        Minimum required recall on labelled ALERT / CRITICAL samples (0–1).

    Example
    -------
    >>> opt = CalibrationOptimizer(min_recall=0.90)
    >>> result = opt.fit(scores, labels)
    >>> print(result.solution)
    {'watch_threshold': 1.42, 'alert_threshold': 2.15}
    """

    def __init__(
        self,
        watch_threshold_init: float = 1.5,
        alert_threshold_init: float = 2.2,
        min_recall: float = 0.90,
        max_iter: int = 500,
    ) -> None:
        _require_scipy()
        self.watch_init = watch_threshold_init
        self.alert_init = alert_threshold_init
        self.min_recall = min_recall
        self.max_iter = max_iter

    def fit(
        self,
        scores: list[float] | np.ndarray,
        labels: list[int] | np.ndarray,
    ) -> OptimizationResult:
        """
        Optimise thresholds against ``scores`` and binary ``labels``
        (1 = true instability event, 0 = normal).

        Minimises false-positive rate subject to recall >= min_recall.
        """
        scores_arr = np.asarray(scores, dtype=float)
        labels_arr = np.asarray(labels, dtype=int)
        len(scores_arr)

        def false_positive_rate(params: np.ndarray) -> float:
            watch, _alert = params
            predicted_alert = scores_arr >= watch
            fp = int(np.sum(predicted_alert & (labels_arr == 0)))
            tn = int(np.sum(~predicted_alert & (labels_arr == 0)))
            return fp / max(fp + tn, 1)

        def recall_deficit(params: np.ndarray) -> float:
            watch, _alert = params
            predicted_alert = scores_arr >= watch
            tp = int(np.sum(predicted_alert & (labels_arr == 1)))
            fn = int(np.sum(~predicted_alert & (labels_arr == 1)))
            recall = tp / max(tp + fn, 1)
            return recall - self.min_recall  # must be >= 0

        def ordering_constraint(params: np.ndarray) -> float:
            watch, alert = params
            return alert - watch - 0.05  # alert must be > watch by at least 0.05

        constraints = [
            {"type": "ineq", "fun": recall_deficit},
            {"type": "ineq", "fun": ordering_constraint},
        ]
        bounds = [(0.1, 5.0), (0.2, 6.0)]
        x0 = np.array([self.watch_init, self.alert_init])

        result = _sopt.minimize(
            false_positive_rate,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.max_iter},
        )

        return OptimizationResult(
            success=bool(result.success),
            message=result.message,
            objective_value=float(result.fun),
            solution={
                "watch_threshold": float(result.x[0]),
                "alert_threshold": float(result.x[1]),
            },
            iterations=int(result.nit),
            solver="scipy.SLSQP",
        )


# ---------------------------------------------------------------------------
# Weight optimizer
# ---------------------------------------------------------------------------


class WeightOptimizer:
    """
    Optimise per-component scoring weights via NLP.

    Formulates weight selection as a QP-like problem: minimise the sum of
    squared errors between predicted scores and ground-truth instability
    ratings, subject to non-negativity and unit-sum constraints.

    Parameters
    ----------
    components : list[str]
        Component names to optimise.  Defaults to all 8 pipeline components.

    Example
    -------
    >>> opt = WeightOptimizer()
    >>> result = opt.fit(component_matrix, target_scores)
    >>> print(result.solution)
    {'relational_drift': 0.28, 'spectral': 0.19, ...}
    """

    def __init__(
        self,
        components: list[str] | None = None,
        max_iter: int = 1000,
    ) -> None:
        _require_scipy()
        self.components = components or list(DEFAULT_WEIGHTS.keys())
        self.max_iter = max_iter

    def fit(
        self,
        component_matrix: np.ndarray,
        target_scores: np.ndarray,
    ) -> OptimizationResult:
        """
        Fit weights to minimise MSE(predicted_score, target_score).

        Parameters
        ----------
        component_matrix : shape (n_samples, n_components)
            Each row is a component vector from one processed frame.
        target_scores : shape (n_samples,)
            Ground-truth instability scores (e.g., from expert labels).
        """
        X = np.asarray(component_matrix, dtype=float)
        y = np.asarray(target_scores, dtype=float)
        n_components = X.shape[1]

        def mse(weights: np.ndarray) -> float:
            pred = X @ weights / (weights.sum() + 1e-12)
            return float(np.mean((pred - y) ** 2))

        def grad_mse(weights: np.ndarray) -> np.ndarray:
            w_sum = weights.sum() + 1e-12
            pred = X @ weights / w_sum
            residuals = pred - y
            # d(pred)/d(w_j) = (X[:,j] * w_sum - (X @ w)) / w_sum^2
            grads = np.zeros(n_components)
            for j in range(n_components):
                dpred_dw = (X[:, j] * w_sum - X @ weights) / (w_sum ** 2)
                grads[j] = 2 * float(np.mean(residuals * dpred_dw))
            return grads

        # Unit-sum constraint: sum(w) = 1
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * n_components
        x0 = np.ones(n_components) / n_components

        result = _sopt.minimize(
            mse,
            x0,
            jac=grad_mse,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.max_iter},
        )

        solution = {
            name: float(result.x[i])
            for i, name in enumerate(self.components)
        }
        return OptimizationResult(
            success=bool(result.success),
            message=result.message,
            objective_value=float(result.fun),
            solution=solution,
            iterations=int(result.nit),
            solver="scipy.SLSQP",
        )


# ---------------------------------------------------------------------------
# General LP / MIP planning optimizer
# ---------------------------------------------------------------------------


class PlanningOptimizer:
    """
    General-purpose LP / MIP optimizer for operational planning problems.

    Wraps SciPy ``linprog`` for LP and PuLP for MIP so callers can express
    real-world planning problems (scheduling, resource allocation, action
    sequencing) using a simple dict-based API.

    Example (LP) — minimise cost subject to capacity constraints::

        opt = PlanningOptimizer()
        result = opt.solve_lp(
            objective={"action_a": 1.0, "action_b": 2.5},
            constraints=[
                {"vars": {"action_a": 1, "action_b": 1}, "sense": "<=", "rhs": 10},
                {"vars": {"action_a": 1}, "sense": ">=", "rhs": 2},
            ],
            bounds={"action_a": (0, None), "action_b": (0, None)},
        )
    """

    def __init__(self) -> None:
        _require_scipy()

    def solve_lp(
        self,
        objective: dict[str, float],
        constraints: list[dict[str, Any]],
        bounds: dict[str, tuple[float | None, float | None]] | None = None,
        maximize: bool = False,
    ) -> LPResult:
        """
        Solve a linear program.

        Parameters
        ----------
        objective : {var_name: coefficient}  — objective function coefficients.
        constraints : list of dicts with keys:
            ``vars``  {var_name: coef},
            ``sense`` one of "<=", ">=", "==",
            ``rhs``   right-hand-side scalar.
        bounds : {var_name: (lower, upper)}.  None means (0, +inf).
        maximize : if True, negate objective to maximise.
        """
        var_names = list(objective.keys())
        n = len(var_names)
        idx = {name: i for i, name in enumerate(var_names)}

        c = np.array([objective[name] for name in var_names], dtype=float)
        if maximize:
            c = -c

        A_ub, b_ub = [], []
        A_eq, b_eq = [], []

        for con in constraints:
            row = np.zeros(n)
            for name, coef in con["vars"].items():
                if name in idx:
                    row[idx[name]] = coef
            sense = con["sense"]
            rhs = float(con["rhs"])
            if sense == "<=":
                A_ub.append(row)
                b_ub.append(rhs)
            elif sense == ">=":
                A_ub.append(-row)
                b_ub.append(-rhs)
            elif sense == "==":
                A_eq.append(row)
                b_eq.append(rhs)

        sp_bounds = []
        for name in var_names:
            if bounds and name in bounds:
                lo, hi = bounds[name]
                sp_bounds.append((lo if lo is not None else 0.0, hi))
            else:
                sp_bounds.append((0.0, None))

        result = _sopt.linprog(
            c,
            A_ub=np.array(A_ub) if A_ub else None,
            b_ub=np.array(b_ub) if b_ub else None,
            A_eq=np.array(A_eq) if A_eq else None,
            b_eq=np.array(b_eq) if b_eq else None,
            bounds=sp_bounds,
            method="highs",
        )

        obj_val = float(result.fun) if result.fun is not None else float("nan")
        if maximize:
            obj_val = -obj_val

        return LPResult(
            status=result.message,
            objective=obj_val,
            variables=(
                {name: float(result.x[i]) for i, name in enumerate(var_names)}
                if result.x is not None
                else {}
            ),
        )

    def solve_mip(
        self,
        objective: dict[str, float],
        constraints: list[dict[str, Any]],
        integer_vars: list[str] | None = None,
        binary_vars: list[str] | None = None,
        bounds: dict[str, tuple[float, float]] | None = None,
        maximize: bool = False,
        solver_msg: bool = False,
    ) -> LPResult:
        """
        Solve a mixed-integer program using PuLP.

        Parameters
        ----------
        objective : {var_name: coefficient}.
        constraints : same format as ``solve_lp``.
        integer_vars : names of variables constrained to integers.
        binary_vars : names of variables constrained to {0, 1}.
        bounds : {var_name: (lower, upper)}.
        maximize : if True, maximise instead of minimise.
        """
        _require_pulp()
        sense = _pulp.LpMaximize if maximize else _pulp.LpMinimize
        prob = _pulp.LpProblem("mip", sense)

        var_names = list(objective.keys())
        pv: dict[str, Any] = {}
        for name in var_names:
            lo, hi = (bounds or {}).get(name, (0.0, None))  # type: ignore[misc]
            if binary_vars and name in binary_vars:
                pv[name] = _pulp.LpVariable(name, cat="Binary")
            elif integer_vars and name in integer_vars:
                pv[name] = _pulp.LpVariable(
                    name, lowBound=lo, upBound=hi, cat="Integer"
                )
            else:
                pv[name] = _pulp.LpVariable(name, lowBound=lo, upBound=hi)

        prob += _pulp.lpSum(objective[n] * pv[n] for n in var_names)

        for i, con in enumerate(constraints):
            lhs = _pulp.lpSum(coef * pv[n] for n, coef in con["vars"].items() if n in pv)
            rhs_val = con["rhs"]
            s = con["sense"]
            if s == "<=":
                prob += lhs <= rhs_val, f"c{i}"
            elif s == ">=":
                prob += lhs >= rhs_val, f"c{i}"
            elif s == "==":
                prob += lhs == rhs_val, f"c{i}"

        prob.solve(_pulp.PULP_CBC_CMD(msg=int(solver_msg)))
        status = _pulp.LpStatus[prob.status]
        obj = _pulp.value(prob.objective) or 0.0

        return LPResult(
            status=status,
            objective=float(obj),
            variables={n: float(_pulp.value(pv[n]) or 0.0) for n in var_names},
        )


# ---------------------------------------------------------------------------
# Auto-formulate helper
# ---------------------------------------------------------------------------


def auto_formulate_lp(
    variables: list[str],
    objective: dict[str, float],
    constraints: list[dict[str, Any]],
    bounds: dict[str, tuple[float | None, float | None]] | None = None,
    maximize: bool = False,
) -> LPResult:
    """
    One-shot LP formulation and solve.

    Convenience wrapper around ``PlanningOptimizer.solve_lp`` for callers
    that want a functional interface without instantiating the optimizer.

    Example::

        result = auto_formulate_lp(
            variables=["x", "y"],
            objective={"x": -1, "y": -2},
            constraints=[
                {"vars": {"x": 1, "y": 1}, "sense": "<=", "rhs": 4},
                {"vars": {"x": 2, "y": 1}, "sense": "<=", "rhs": 6},
            ],
        )
    """
    opt = PlanningOptimizer()
    return opt.solve_lp(objective, constraints, bounds, maximize)
