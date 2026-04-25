"""System-agnostic synthetic generator.

Produces multi-variable telemetry that behaves like a real coupled system:
- Variables are coupled through a covariance matrix Σ
- "Drift events" gradually rotate the covariance toward an off-baseline target
- Mean shifts cascade across variables during severe events
- No fake sine waves — output is sampled from a time-varying multivariate
  normal so the SII engine sees genuine structural drift, not synthetic
  spectral content.

A `System` is a self-contained simulator: call `tick()` to get the next
sensor vector. Calling code is responsible for ingesting it into
`SIIEngineAdapter`.

System templates encode different domains (industrial / environmental /
generic). The simulator code is identical — only variable names + baseline
ranges differ — which is the whole point of a generalized intelligence
platform.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np


# ------------------------------------------------------------------
# Domain templates — variable names + plausible baseline ranges
# ------------------------------------------------------------------
_TEMPLATES: Dict[str, Dict] = {
    "industrial": {
        "variables": [
            ("pressure_kpa",      280.0, 8.0,  "kPa"),
            ("temperature_c",     72.0,  2.0,  "°C"),
            ("vibration_g",       0.35,  0.05, "g"),
            ("rpm",               1750.0,15.0, "rpm"),
            ("torque_nm",         48.0,  3.0,  "Nm"),
            ("flow_rate_lpm",     22.0,  1.5,  "L/min"),
        ],
        "label": "Industrial system",
    },
    "environmental": {
        "variables": [
            ("temperature_c",     22.5,  0.4,  "°C"),
            ("humidity_rh",       55.0,  3.0,  "%RH"),
            ("co2_ppm",           820.0, 35.0, "ppm"),
            ("airflow_cmh",       240.0, 8.0,  "m³/h"),
            ("vpd_kpa",           1.05,  0.05, "kPa"),
            ("light_par",         420.0, 12.0, "PAR"),
        ],
        "label": "Environmental system",
    },
    "generic": {
        "variables": [
            ("var_alpha", 100.0, 5.0,  ""),
            ("var_beta",  50.0,  3.0,  ""),
            ("var_gamma", 25.0,  2.0,  ""),
            ("var_delta", 10.0,  1.0,  ""),
            ("var_epsilon", 5.0, 0.4,  ""),
        ],
        "label": "Generic system",
    },
}


@dataclass
class System:
    system_id: str
    template: str
    variables: List[str]                  # names in stable order
    units: Dict[str, str]                 # name -> unit string
    baseline_mean: np.ndarray             # μ₀, shape (D,)
    baseline_std: np.ndarray              # σ₀, shape (D,)
    baseline_cov: np.ndarray              # Σ₀, shape (D, D)
    label: str
    rng: np.random.Generator
    # Drift schedule — list of (start_step, duration, severity in [0..1])
    drift_schedule: List[tuple] = field(default_factory=list)
    step: int = 0
    # Current state
    last_vector: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.last_vector is None:
            self.last_vector = self.baseline_mean.copy()


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------
def make_system(system_id: str, template: str = "industrial",
                seed: Optional[int] = None,
                drift_schedule: Optional[List[tuple]] = None) -> System:
    if template not in _TEMPLATES:
        raise ValueError(f"Unknown template: {template}")
    tpl = _TEMPLATES[template]
    rng = np.random.default_rng(seed)
    names = [v[0] for v in tpl["variables"]]
    means = np.array([v[1] for v in tpl["variables"]], dtype=float)
    stds = np.array([v[2] for v in tpl["variables"]], dtype=float)
    units = {v[0]: v[3] for v in tpl["variables"]}
    # Build a positive-definite baseline covariance with weak coupling
    D = len(names)
    A = rng.standard_normal((D, D)) * 0.15
    cov = stds[:, None] * stds[None, :] * (np.eye(D) + A @ A.T * 0.3)
    cov = (cov + cov.T) / 2  # ensure symmetry

    return System(
        system_id=system_id,
        template=template,
        variables=names,
        units=units,
        baseline_mean=means,
        baseline_std=stds,
        baseline_cov=cov,
        label=tpl["label"],
        rng=rng,
        drift_schedule=drift_schedule or [],
    )


# ------------------------------------------------------------------
# Drift dynamics
# ------------------------------------------------------------------
def _active_drift_severity(sys: System) -> float:
    """Returns severity in [0, 1] for current step based on schedule."""
    severity = 0.0
    for start, duration, peak in sys.drift_schedule:
        if sys.step < start or sys.step >= start + duration:
            continue
        # Triangular ramp: 0 -> peak -> 0 across duration (a bit asymmetric)
        progress = (sys.step - start) / duration
        if progress < 0.4:
            local = peak * (progress / 0.4)
        else:
            local = peak * (1 - (progress - 0.4) / 0.6)
        severity = max(severity, local)
    return float(np.clip(severity, 0.0, 1.0))


def _drift_target_cov(sys: System) -> np.ndarray:
    """A target covariance the system rotates toward during a drift event.

    We rotate Σ₀ via a fixed orthogonal perturbation + scale up some axes — this
    creates a measurable Frobenius-norm change without disturbing the baseline
    too violently.
    """
    D = sys.baseline_cov.shape[0]
    # Use a deterministic perturbation per system so drift "shape" is consistent
    seed = abs(hash(sys.system_id)) % (2**32 - 1)
    r = np.random.default_rng(seed)
    # Random orthogonal matrix Q
    Q, _ = np.linalg.qr(r.standard_normal((D, D)))
    # Scale a couple of axes by 2-3x to break coupling
    scale = np.ones(D)
    scale[r.integers(0, D, size=2)] = r.uniform(2.0, 3.5, size=2)
    return Q @ np.diag(scale) @ Q.T @ sys.baseline_cov @ Q @ np.diag(scale) @ Q.T


# ------------------------------------------------------------------
# Tick
# ------------------------------------------------------------------
def tick(sys: System) -> Dict[str, float]:
    """Advance the system one step and return a sensor_values dict.

    The output is a real multivariate-normal sample drawn from a covariance
    that smoothly evolves between baseline and a perturbed target during
    drift events. Means cascade slightly during severe events too, so
    structural drift score, drift velocity, and instability all rise.
    """
    severity = _active_drift_severity(sys)
    if severity > 0:
        target = _drift_target_cov(sys)
        cov_now = (1 - severity) * sys.baseline_cov + severity * target
        # Cascading mean shift (coupling failure): a couple of variables drift
        D = sys.baseline_mean.shape[0]
        shift = np.zeros(D)
        # Pick the first 2 variables for the cascade — stable and reproducible
        shift[0] = severity * sys.baseline_std[0] * 1.5
        shift[1] = severity * sys.baseline_std[1] * 0.8
        mean_now = sys.baseline_mean + shift
    else:
        cov_now = sys.baseline_cov
        mean_now = sys.baseline_mean

    # Sample (cov is psd; jitter for numerics)
    try:
        vec = sys.rng.multivariate_normal(mean_now, cov_now + 1e-9 * np.eye(cov_now.shape[0]))
    except np.linalg.LinAlgError:
        vec = mean_now + sys.rng.standard_normal(mean_now.shape) * sys.baseline_std

    sys.last_vector = vec
    sys.step += 1
    return {name: float(v) for name, v in zip(sys.variables, vec)}


def list_templates() -> List[Dict]:
    return [
        {
            "id": k,
            "label": v["label"],
            "variables": [{"name": var[0], "unit": var[3]} for var in v["variables"]],
        }
        for k, v in _TEMPLATES.items()
    ]


def standard_drift_schedule(start: int = 80, severity: float = 0.9, duration: int = 200) -> List[tuple]:
    """The default product-demo schedule: ~80 stable steps, then a single
    drift event that escalates the system through TRANSITION → UNSTABLE."""
    return [(start, duration, severity)]
