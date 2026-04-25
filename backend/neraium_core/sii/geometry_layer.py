from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dependence import DependenceBackend, estimate_dependence
from .errors import SIIValidationError


def normalize_window(window: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = np.asarray(window, dtype=float)
    if arr.ndim != 2:
        raise SIIValidationError("normalize_window expects a 2D matrix")
    mean = np.nanmean(arr, axis=0)
    std = np.nanstd(arr, axis=0)
    std = np.where(std < 1e-9, 1.0, std)
    z = (arr - mean) / std
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    return z, mean, std


def covariance_matrix(z_window: np.ndarray) -> np.ndarray:
    z = np.asarray(z_window, dtype=float)
    if z.ndim != 2:
        raise SIIValidationError("covariance_matrix expects a 2D matrix")
    cov = np.cov(z.T)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    if cov.ndim == 0:
        cov = np.asarray([[float(cov)]], dtype=float)
    cov = 0.5 * (cov + cov.T)
    return cov


def correlation_matrix(z_window: np.ndarray, *, backend: DependenceBackend = "pearson", lag: int = 0) -> np.ndarray:
    z = np.asarray(z_window, dtype=float)
    if z.ndim != 2:
        raise SIIValidationError("correlation_matrix expects a 2D matrix")
    return estimate_dependence(z, backend=backend, lag=lag).matrix


def flatten_upper(corr: np.ndarray) -> np.ndarray:
    c = np.asarray(corr, dtype=float)
    if c.ndim != 2 or c.shape[0] != c.shape[1]:
        return np.array([], dtype=float)
    idx = np.triu_indices(c.shape[0], k=1)
    return c[idx]


def geometric_distance(current: np.ndarray, reference: np.ndarray) -> float:
    a = np.asarray(current, dtype=float)
    b = np.asarray(reference, dtype=float)
    if a.shape != b.shape:
        return 0.0
    n = float(max(1, a.size))
    return float(np.linalg.norm(a - b, ord="fro") / np.sqrt(n))


def relational_instability(current_corr: np.ndarray, reference_corr: np.ndarray) -> float:
    cur = flatten_upper(current_corr)
    ref = flatten_upper(reference_corr)
    if cur.shape != ref.shape or cur.size == 0:
        return 0.0
    return float(np.mean(np.abs(cur - ref)))


def _principal_subspace(cov: np.ndarray, energy: float = 0.80) -> np.ndarray:
    vals, vecs = np.linalg.eigh(cov)
    vals = np.clip(np.asarray(vals, dtype=float), a_min=1e-12, a_max=None)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    total = float(np.sum(vals))
    if total <= 0.0:
        return vecs[:, :1]
    ratio = np.cumsum(vals) / total
    k = int(np.searchsorted(ratio, energy, side="left") + 1)
    k = max(1, min(k, vecs.shape[1]))
    return vecs[:, :k]


def _subspace_distance(cov_a: np.ndarray, cov_b: np.ndarray) -> float:
    ua = _principal_subspace(cov_a)
    ub = _principal_subspace(cov_b)
    k = min(ua.shape[1], ub.shape[1])
    if k <= 0:
        return 0.0
    proj = ua[:, :k].T @ ub[:, :k]
    s = np.linalg.svd(proj, compute_uv=False)
    s = np.clip(np.asarray(s, dtype=float), -1.0, 1.0)
    angles = np.arccos(s)
    return float(np.mean(np.abs(angles)) / np.pi)


def _effective_rank(cov: np.ndarray) -> float:
    vals = np.linalg.eigvalsh(cov)
    vals = np.clip(np.asarray(vals, dtype=float), a_min=1e-12, a_max=None)
    p = vals / np.sum(vals)
    ent = -float(np.sum(p * np.log(p + 1e-12)))
    return float(np.exp(ent))


def _coherence_from_cov(cov: np.ndarray) -> float:
    rank = _effective_rank(cov)
    n = float(max(1, cov.shape[0]))
    return float(np.clip(rank / n, 0.0, 1.0))


@dataclass(frozen=True)
class GeometryState:
    mean: np.ndarray
    cov: np.ndarray
    feature_names: list[str]
    coherence_score: float = 1.0


@dataclass(frozen=True)
class GeometryFeatures:
    baseline_mean: np.ndarray
    baseline_std: np.ndarray
    recent_mean: np.ndarray
    recent_std: np.ndarray
    baseline_cov: np.ndarray
    recent_cov: np.ndarray
    baseline_corr: np.ndarray
    recent_corr: np.ndarray
    mean_shift_norm: float
    covariance_shift_norm: float
    subspace_rotation: float
    structural_drift: float
    relational_instability: float
    coherence_score: float


def build_geometry_state(
    baseline_window: np.ndarray,
    recent_window: np.ndarray,
    reference_corr: np.ndarray | None = None,
    *,
    dependence_backend: DependenceBackend = "pearson",
    dependence_lag: int = 0,
) -> GeometryFeatures:
    z_base, mean_base, std_base = normalize_window(baseline_window)
    z_recent, mean_recent, std_recent = normalize_window(recent_window)

    cov_base = covariance_matrix(z_base)
    cov_recent = covariance_matrix(z_recent)
    corr_base = correlation_matrix(z_base, backend=dependence_backend, lag=dependence_lag)
    corr_recent = correlation_matrix(z_recent, backend=dependence_backend, lag=dependence_lag)

    effective_ref_corr = (
        np.asarray(reference_corr, dtype=float)
        if reference_corr is not None and np.asarray(reference_corr).shape == corr_recent.shape
        else corr_base
    )

    mean_shift = float(np.linalg.norm(mean_recent - mean_base) / np.sqrt(float(max(1, mean_base.size))))
    cov_shift = geometric_distance(cov_recent, cov_base)
    subspace_rot = _subspace_distance(cov_base, cov_recent)
    corr_drift = geometric_distance(corr_recent, effective_ref_corr)
    rel_inst = relational_instability(corr_recent, effective_ref_corr)
    structural = float(0.40 * cov_shift + 0.35 * corr_drift + 0.25 * subspace_rot)
    coherence = _coherence_from_cov(cov_recent)

    return GeometryFeatures(
        baseline_mean=mean_base,
        baseline_std=std_base,
        recent_mean=mean_recent,
        recent_std=std_recent,
        baseline_cov=cov_base,
        recent_cov=cov_recent,
        baseline_corr=corr_base,
        recent_corr=corr_recent,
        mean_shift_norm=mean_shift,
        covariance_shift_norm=cov_shift,
        subspace_rotation=subspace_rot,
        structural_drift=structural,
        relational_instability=rel_inst,
        coherence_score=coherence,
    )
