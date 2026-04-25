"""
neraium_core.math — Advanced mathematical capabilities for the core engine.

Six sub-modules, all designed to be drop-in enhancements to the existing
scoring/calibration pipeline.  Each module degrades gracefully when its
optional dependencies are not installed.

Sub-modules
-----------
symbolic_engine   — Exact algebra/calculus via SymPy (simplification, proofs,
                    equation solving, symbolic diff/integration).
optimization_engine — LP/QP/NLP/MIP solvers and auto-formulation helpers via
                    SciPy (threshold tuning, weight optimisation, planning).
probabilistic_engine — Bayesian inference, uncertainty propagation, and Monte
                    Carlo tools so every result carries confidence bounds.
numerics          — Sparse linear algebra, automatic differentiation, and
                    optional GPU acceleration for scaling harder models.
verification_engine — Constraint-checking / theorem-proving layer that verifies
                    critical mathematical claims and catches silent errors.
math_agent        — Math-aware Claude agent workflows: task decomposition,
                    dynamic method selection, and self-checking derivations.
"""

from neraium_core.math.symbolic_engine import SymbolicScoringModel
from neraium_core.math.optimization_engine import CalibrationOptimizer, WeightOptimizer
from neraium_core.math.probabilistic_engine import (
    BayesianStateFilter,
    MonteCarloSampler,
    StructuralUncertaintyTracker,
    UncertaintyPropagator,
)
from neraium_core.math.numerics import SparseCorrelationComputer, AutoDiff, gpu_available
from neraium_core.math.verification_engine import (
    MonotonicityVerifier,
    ThresholdConsistencyChecker,
    DecisionRuleVerifier,
)
from neraium_core.math.math_agent import MathAgent

__all__ = [
    # Symbolic
    "SymbolicScoringModel",
    # Optimization
    "CalibrationOptimizer",
    "WeightOptimizer",
    # Probabilistic
    "BayesianStateFilter",
    "MonteCarloSampler",
    "StructuralUncertaintyTracker",
    "UncertaintyPropagator",
    # Numerics
    "SparseCorrelationComputer",
    "AutoDiff",
    "gpu_available",
    # Verification
    "MonotonicityVerifier",
    "ThresholdConsistencyChecker",
    "DecisionRuleVerifier",
    # Agent
    "MathAgent",
]
