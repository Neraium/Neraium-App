from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


DependenceBackend = Literal["pearson", "spearman", "partial"]


@dataclass(frozen=True)
class DependenceEstimate:
    matrix: np.ndarray
    backend: DependenceBackend
    lag: int = 0
    robustness: dict[str, float] | None = None


def _safe_rankdata(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    mask = np.isfinite(arr)
    if not np.any(mask):
        return np.zeros_like(arr, dtype=float)
    vals = arr[mask]
    order = np.argsort(vals, kind="mergesort")
    ranks = np.empty(vals.size, dtype=float)
    ranks[order] = np.arange(vals.size, dtype=float)
    out = np.zeros_like(arr, dtype=float)
    out[mask] = ranks
    return out


def _normalize_window(window: np.ndarray) -> np.ndarray:
    w = np.asarray(window, dtype=float)
    mean = np.nanmean(w, axis=0)
    std = np.nanstd(w, axis=0)
    std = np.where(std < 1e-9, 1.0, std)
    z = (w - mean) / std
    return np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)


def _pearson_corr(z: np.ndarray) -> np.ndarray:
    corr = np.corrcoef(z.T)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    if corr.ndim == 0:
        corr = np.asarray([[1.0]], dtype=float)
    np.fill_diagonal(corr, 1.0)
    return corr


def _spearman_corr(z: np.ndarray) -> np.ndarray:
    ranked = np.vstack([_safe_rankdata(z[:, i]) for i in range(z.shape[1])]).T
    return _pearson_corr(ranked)


def _partial_corr_shrinkage(z: np.ndarray) -> np.ndarray:
    n, p = z.shape
    if p == 0:
        return np.zeros((0, 0), dtype=float)
    cov = np.cov(z.T)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    if cov.ndim == 0:
        return np.asarray([[1.0]], dtype=float)
    trace = float(np.trace(cov))
    lam = 0.08 + 0.30 * max(0.0, (p - max(1, n)) / max(1.0, float(p)))
    target = np.eye(p, dtype=float) * (trace / max(1.0, float(p)))
    shrunk = (1.0 - lam) * cov + lam * target
    try:
        precision = np.linalg.pinv(shrunk)
    except np.linalg.LinAlgError:
        precision = np.eye(p, dtype=float)
    d = np.sqrt(np.maximum(np.diag(precision), 1e-12))
    pcorr = -precision / (d[:, None] * d[None, :])
    np.fill_diagonal(pcorr, 1.0)
    return np.clip(np.nan_to_num(pcorr, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)


def estimate_dependence(window: np.ndarray, *, backend: DependenceBackend = "pearson", lag: int = 0) -> DependenceEstimate:
    arr = np.asarray(window, dtype=float)
    if arr.ndim != 2:
        raise ValueError("window must be 2D")
    lag_i = max(0, int(lag))
    if lag_i > 0 and arr.shape[0] > lag_i + 1:
        arr = arr[lag_i:, :] - arr[:-lag_i, :]

    z = _normalize_window(arr)
    if backend == "spearman":
        mat = _spearman_corr(z)
    elif backend == "partial":
        mat = _partial_corr_shrinkage(z)
    else:
        mat = _pearson_corr(z)

    missingness = float(np.mean(~np.isfinite(window))) if window.size else 0.0
    robustness = {
        "missingness_rate": round(missingness, 6),
        "effective_samples": float(z.shape[0]),
        "lag": float(lag_i),
    }
    return DependenceEstimate(matrix=mat, backend=backend, lag=lag_i, robustness=robustness)
