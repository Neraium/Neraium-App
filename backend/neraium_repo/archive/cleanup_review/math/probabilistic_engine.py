"""
Probabilistic reasoning engine — Bayesian inference, uncertainty propagation,
and Monte Carlo tools.

Every result the engine emits is a point estimate.  This module augments those
estimates with *confidence bounds* and *state probabilities* so that operators
see risk, not just scores.

Classes
-------
BayesianStateFilter
    Maintains a probability distribution P(state | observations) and updates
    it frame-by-frame via Bayes' rule.  States: STABLE, WATCH, ALERT, CRITICAL.

UncertaintyPropagator
    Propagates sensor-level noise (measurement error, quantisation) through
    the scoring pipeline via first-order uncertainty analysis (error bars on
    the composite score) and second-order Monte Carlo sampling.

MonteCarloSampler
    Bootstraps confidence intervals for the instability score by resampling
    component vectors.  Also provides probability-of-threshold-crossing
    estimates used in risk dashboards.

Optional dependency: ``scipy``  (pip install scipy)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    from scipy import stats as _stats

    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False
    _stats = None  # type: ignore[assignment]

from neraium_core.scoring import composite_instability_score_normalized, DEFAULT_WEIGHTS

# State label ordering (index = ordinal severity)
_STATES = ["STABLE", "WATCH", "ALERT", "CRITICAL"]
_N_STATES = len(_STATES)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ProbabilisticResult:
    """
    Augmented result carrying confidence information alongside a point estimate.
    """

    point_estimate: float
    mean: float
    std: float
    p5: float
    p25: float
    p75: float
    p95: float
    n_samples: int
    probability_watch: float = 0.0
    probability_alert: float = 0.0
    probability_critical: float = 0.0

    @property
    def confidence_interval_90(self) -> tuple[float, float]:
        return (self.p5, self.p95)

    @property
    def confidence_interval_50(self) -> tuple[float, float]:
        return (self.p25, self.p75)

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_estimate": self.point_estimate,
            "mean": self.mean,
            "std": self.std,
            "p5": self.p5,
            "p25": self.p25,
            "p75": self.p75,
            "p95": self.p95,
            "n_samples": self.n_samples,
            "ci_90": list(self.confidence_interval_90),
            "ci_50": list(self.confidence_interval_50),
            "probability_watch": self.probability_watch,
            "probability_alert": self.probability_alert,
            "probability_critical": self.probability_critical,
        }


@dataclass
class BayesianStateEstimate:
    """State probability distribution from the Bayesian filter."""

    probabilities: dict[str, float]
    map_state: str       # maximum-a-posteriori state label
    entropy: float       # Shannon entropy of the distribution (bits)
    frame_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "probabilities": self.probabilities,
            "map_state": self.map_state,
            "entropy": self.entropy,
            "frame_index": self.frame_index,
        }


@dataclass
class StructuralUncertaintyEstimate:
    """
    Probabilistic uncertainty over structural deformation signatures.

    Each field is a Beta-posterior estimate over a structural event:
    - structure_deformation: relational/spectral geometry departed baseline
    - operator_drift: persistent operator-level drift is present
    - coherence_margin_degradation: coherence margin has materially degraded
    - regime_transition: transition pressure indicates regime change
    """

    posterior_means: dict[str, float]
    credible_intervals_90: dict[str, list[float]]
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "posterior_means": self.posterior_means,
            "credible_intervals_90": self.credible_intervals_90,
            "sample_count": self.sample_count,
        }


# ---------------------------------------------------------------------------
# Bayesian state filter
# ---------------------------------------------------------------------------


class BayesianStateFilter:
    """
    Frame-by-frame Bayesian filter over discrete states
    {STABLE, WATCH, ALERT, CRITICAL}.

    At each frame the filter:
    1. Applies a transition prior (persistence + small diffusion).
    2. Multiplies by the likelihood of the observed score under each state.
    3. Normalises to obtain P(state | all observations so far).

    Parameters
    ----------
    prior : dict[str, float] | None
        Initial prior over states.  Defaults to a uniform distribution.
    persistence : float
        Probability that the state stays the same from one frame to the next
        (used to build the Markov transition matrix).  Range [0, 1].
    state_means : dict[str, float] | None
        Mean instability score expected in each state (used for likelihood).
    state_stds : dict[str, float] | None
        Standard deviation of instability score in each state.

    Example
    -------
    >>> filt = BayesianStateFilter()
    >>> for frame_score in score_history:
    ...     estimate = filt.update(frame_score)
    ...     print(estimate.map_state, estimate.probabilities)
    """

    _DEFAULT_MEANS = {"STABLE": 0.4, "WATCH": 1.2, "ALERT": 2.0, "CRITICAL": 3.0}
    _DEFAULT_STDS  = {"STABLE": 0.3, "WATCH": 0.4, "ALERT": 0.5, "CRITICAL": 0.6}

    def __init__(
        self,
        prior: dict[str, float] | None = None,
        persistence: float = 0.85,
        state_means: dict[str, float] | None = None,
        state_stds: dict[str, float] | None = None,
    ) -> None:
        p = prior or {s: 1.0 / _N_STATES for s in _STATES}
        total = sum(p.values())
        self._probs: np.ndarray = np.array(
            [p.get(s, 0.0) / total for s in _STATES], dtype=float
        )
        self._persistence = persistence
        self._means = state_means or dict(self._DEFAULT_MEANS)
        self._stds  = state_stds  or dict(self._DEFAULT_STDS)
        self._frame_index: int = 0
        self._transition = self._build_transition(persistence)

    @staticmethod
    def _build_transition(persistence: float) -> np.ndarray:
        """
        Build a Markov transition matrix with ``persistence`` on the diagonal
        and equal diffusion mass spread over neighbours.
        """
        n = _N_STATES
        T = np.full((n, n), (1.0 - persistence) / (n - 1))
        np.fill_diagonal(T, persistence)
        return T

    def _likelihood(self, score: float) -> np.ndarray:
        """P(score | state) for each state using a Gaussian emission model."""
        likes = np.array([
            self._gaussian_pdf(score, self._means[s], self._stds[s])
            for s in _STATES
        ], dtype=float)
        # Avoid complete zero rows
        if likes.sum() == 0:
            likes[:] = 1.0 / _N_STATES
        return likes

    @staticmethod
    def _gaussian_pdf(x: float, mu: float, sigma: float) -> float:
        if sigma <= 0:
            return 1.0 if abs(x - mu) < 1e-9 else 0.0
        return float(math.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi)))

    def update(self, score: float) -> BayesianStateEstimate:
        """
        Ingest one frame's instability score and return the updated state estimate.
        """
        # Predict: apply transition prior
        predicted = self._transition.T @ self._probs

        # Update: multiply by likelihood and normalise
        likes = self._likelihood(score)
        posterior = predicted * likes
        total = posterior.sum()
        if total > 0:
            posterior /= total
        else:
            posterior = np.ones(_N_STATES) / _N_STATES

        self._probs = posterior
        self._frame_index += 1

        probs_dict = {s: float(posterior[i]) for i, s in enumerate(_STATES)}
        map_state = _STATES[int(np.argmax(posterior))]
        ent = self._shannon_entropy(posterior)

        return BayesianStateEstimate(
            probabilities=probs_dict,
            map_state=map_state,
            entropy=ent,
            frame_index=self._frame_index,
        )

    @staticmethod
    def _shannon_entropy(probs: np.ndarray) -> float:
        eps = 1e-12
        return float(-np.sum(probs * np.log2(probs + eps)))

    def reset(self) -> None:
        self._probs = np.ones(_N_STATES) / _N_STATES
        self._frame_index = 0

    @property
    def current_probabilities(self) -> dict[str, float]:
        return {s: float(self._probs[i]) for i, s in enumerate(_STATES)}


class StructuralUncertaintyTracker:
    """
    Beta-Bernoulli tracker over structural events (not score labels).

    Update input should be structural metrics from the inference layer.
    """

    _EVENT_KEYS = (
        "structure_deformation",
        "operator_drift",
        "coherence_margin_degradation",
        "regime_transition",
    )

    def __init__(self) -> None:
        self._alpha: dict[str, float] = {k: 1.0 for k in self._EVENT_KEYS}
        self._beta: dict[str, float] = {k: 1.0 for k in self._EVENT_KEYS}
        self._n: int = 0

    @staticmethod
    def _event_observations(metrics: dict[str, float]) -> dict[str, float]:
        rd = float(metrics.get("relational_drift", 0.0))
        spectral = float(metrics.get("spectral", 0.0))
        op_drift = float(metrics.get("operator_drift", metrics.get("regime_drift", 0.0)))
        coherence_margin = float(metrics.get("coherence_margin", 0.0))
        transition_pressure = float(metrics.get("transition_pressure", 0.0))
        regime_drift = float(metrics.get("regime_drift", 0.0))

        # Bernoulli observations in [0,1] (fractional evidence supported).
        return {
            "structure_deformation": float(np.clip(max(rd / 1.05, spectral / 0.92), 0.0, 1.0)),
            "operator_drift": float(np.clip(op_drift / 0.85, 0.0, 1.0)),
            "coherence_margin_degradation": float(np.clip((1.0 - coherence_margin) / 0.55, 0.0, 1.0)),
            "regime_transition": float(np.clip(max(transition_pressure / 0.95, regime_drift / 0.88), 0.0, 1.0)),
        }

    def update(self, metrics: dict[str, float]) -> StructuralUncertaintyEstimate:
        obs = self._event_observations(metrics)
        self._n += 1
        for key in self._EVENT_KEYS:
            x = float(obs.get(key, 0.0))
            self._alpha[key] += x
            self._beta[key] += (1.0 - x)

        posterior_means: dict[str, float] = {}
        ci_90: dict[str, list[float]] = {}
        for key in self._EVENT_KEYS:
            a = float(self._alpha[key])
            b = float(self._beta[key])
            posterior_means[key] = a / (a + b)
            if _SCIPY_AVAILABLE:
                lo, hi = _stats.beta.ppf([0.05, 0.95], a, b)
                ci_90[key] = [float(lo), float(hi)]
            else:  # fallback: Gaussian approximation around Beta mean
                var = (a * b) / (((a + b) ** 2) * (a + b + 1.0))
                sigma = math.sqrt(max(0.0, var))
                mu = posterior_means[key]
                ci_90[key] = [float(max(0.0, mu - 1.645 * sigma)), float(min(1.0, mu + 1.645 * sigma))]

        return StructuralUncertaintyEstimate(
            posterior_means=posterior_means,
            credible_intervals_90=ci_90,
            sample_count=self._n,
        )

    def reset(self) -> None:
        self._alpha = {k: 1.0 for k in self._EVENT_KEYS}
        self._beta = {k: 1.0 for k in self._EVENT_KEYS}
        self._n = 0


# ---------------------------------------------------------------------------
# Uncertainty propagator
# ---------------------------------------------------------------------------


class UncertaintyPropagator:
    """
    Propagate sensor-level noise through the scoring pipeline.

    Uses first-order (linear) error propagation to compute the standard
    deviation of the composite score given per-component uncertainties.
    Can also run a full Monte Carlo propagation for non-linear regimes.

    Parameters
    ----------
    weights : dict[str, float] | None
        Component weights (defaults to scoring.DEFAULT_WEIGHTS).
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or DEFAULT_WEIGHTS

    def propagate_linear(
        self,
        component_values: dict[str, float],
        component_uncertainties: dict[str, float],
    ) -> dict[str, float]:
        """
        First-order Gaussian error propagation.

        For a weighted average  s = sum(w_i * c_i) / sum(w_i),
        the variance is  Var(s) = sum((w_i / W)^2 * sigma_i^2)
        where W = sum(w_i).

        Returns
        -------
        dict with keys: ``score``, ``score_std``, ``score_variance``,
        ``relative_uncertainty`` (std/score if score != 0).
        """
        active_names = [
            k for k in DEFAULT_WEIGHTS if self._weights.get(k, 0.0) > 0.0
        ]
        W = sum(self._weights.get(k, 0.0) for k in active_names)
        if W == 0:
            return {"score": 0.0, "score_std": 0.0, "score_variance": 0.0,
                    "relative_uncertainty": 0.0}

        score = sum(
            self._weights.get(k, 0.0) * component_values.get(k, 0.0)
            for k in active_names
        ) / W

        variance = sum(
            (self._weights.get(k, 0.0) / W) ** 2 * (component_uncertainties.get(k, 0.0) ** 2)
            for k in active_names
        )
        std = math.sqrt(variance)
        rel = std / abs(score) if abs(score) > 1e-9 else 0.0

        return {
            "score": score,
            "score_std": std,
            "score_variance": variance,
            "relative_uncertainty": rel,
        }

    def propagate_monte_carlo(
        self,
        component_values: dict[str, float],
        component_uncertainties: dict[str, float],
        n_samples: int = 2000,
        seed: int | None = None,
    ) -> ProbabilisticResult:
        """
        Monte Carlo uncertainty propagation.

        Draws ``n_samples`` realisations of the component vector by adding
        zero-mean Gaussian noise with the specified per-component standard
        deviations, then evaluates the composite score for each realisation.
        """
        rng = np.random.default_rng(seed)
        active_names = [
            k for k in DEFAULT_WEIGHTS if self._weights.get(k, 0.0) > 0.0
        ]
        means = np.array([component_values.get(k, 0.0) for k in active_names])
        stds  = np.array([component_uncertainties.get(k, 0.0) for k in active_names])

        # Draw samples: shape (n_samples, n_components)
        samples = rng.normal(means, stds, size=(n_samples, len(active_names)))
        samples = np.clip(samples, 0.0, None)  # components are non-negative

        weights_arr = np.array([self._weights.get(k, 0.0) for k in active_names])
        W = weights_arr.sum()
        scores = (samples @ weights_arr) / max(W, 1e-12)
        scores = np.clip(scores, 0.0, 3.0)  # winsorise like pipeline

        point_est = composite_instability_score_normalized(component_values, self._weights)

        return _build_probabilistic_result(scores, point_est)


# ---------------------------------------------------------------------------
# Monte Carlo sampler
# ---------------------------------------------------------------------------


class MonteCarloSampler:
    """
    Bootstrap confidence intervals for the composite instability score.

    Given a window of recent component vectors, samples with replacement to
    estimate the distribution of the composite score.  Also computes
    probability of crossing each state threshold.

    Parameters
    ----------
    watch_threshold : float
        Score threshold for WATCH state (default 1.5).
    alert_threshold : float
        Score threshold for ALERT state (default 2.2).
    critical_threshold : float
        Score threshold for CRITICAL state (default 2.8).
    """

    def __init__(
        self,
        watch_threshold: float = 1.5,
        alert_threshold: float = 2.2,
        critical_threshold: float = 2.8,
    ) -> None:
        self.watch_threshold = watch_threshold
        self.alert_threshold = alert_threshold
        self.critical_threshold = critical_threshold

    def bootstrap(
        self,
        component_history: list[dict[str, float]],
        n_samples: int = 2000,
        weights: dict[str, float] | None = None,
        seed: int | None = None,
    ) -> ProbabilisticResult:
        """
        Bootstrap confidence intervals from a list of historical component dicts.

        Parameters
        ----------
        component_history : list of component dicts (one per recent frame).
        n_samples : number of bootstrap replicates.
        weights : scoring weights (defaults to DEFAULT_WEIGHTS).
        seed : random seed for reproducibility.
        """
        rng = np.random.default_rng(seed)
        w = weights or DEFAULT_WEIGHTS
        n = len(component_history)
        if n == 0:
            dummy = ProbabilisticResult(
                point_estimate=0.0, mean=0.0, std=0.0,
                p5=0.0, p25=0.0, p75=0.0, p95=0.0, n_samples=0,
            )
            return dummy

        # Bootstrap: resample rows
        indices = rng.integers(0, n, size=(n_samples, n))
        scores = np.array([
            composite_instability_score_normalized(component_history[i], w)
            for i in range(n)
        ])
        bootstrap_means = scores[indices].mean(axis=1)

        point_est = float(scores.mean())
        return _build_probabilistic_result(
            bootstrap_means,
            point_est,
            watch_t=self.watch_threshold,
            alert_t=self.alert_threshold,
            critical_t=self.critical_threshold,
        )

    def sample_score(
        self,
        components: dict[str, float],
        component_stds: dict[str, float],
        n_samples: int = 1000,
        weights: dict[str, float] | None = None,
        seed: int | None = None,
    ) -> ProbabilisticResult:
        """
        Monte Carlo: perturb a single component vector by Gaussian noise and
        compute the score distribution.

        Useful for single-frame risk assessment when no history is available.
        """
        prop = UncertaintyPropagator(weights)
        return prop.propagate_monte_carlo(components, component_stds, n_samples, seed)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _build_probabilistic_result(
    samples: np.ndarray,
    point_estimate: float,
    watch_t: float = 1.5,
    alert_t: float = 2.2,
    critical_t: float = 2.8,
) -> ProbabilisticResult:
    p5, p25, p75, p95 = float(np.percentile(samples, 5)), float(np.percentile(samples, 25)), float(np.percentile(samples, 75)), float(np.percentile(samples, 95))
    return ProbabilisticResult(
        point_estimate=point_estimate,
        mean=float(samples.mean()),
        std=float(samples.std()),
        p5=p5,
        p25=p25,
        p75=p75,
        p95=p95,
        n_samples=len(samples),
        probability_watch=float(np.mean(samples >= watch_t)),
        probability_alert=float(np.mean(samples >= alert_t)),
        probability_critical=float(np.mean(samples >= critical_t)),
    )
