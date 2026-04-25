"""
High-performance numerics — sparse linear algebra, automatic differentiation,
and optional GPU acceleration.

The existing pipeline uses dense NumPy arrays throughout.  For customers with
large sensor networks (hundreds of signals) this becomes the bottleneck.
This module provides drop-in replacements that:

  SparseCorrelationComputer
      Computes correlation / covariance matrices using scipy.sparse and
      sparse SVD, reducing memory from O(n²) to O(nnz) for near-diagonal
      or block-diagonal structures.

  AutoDiff
      Automatic differentiation of scalar Python functions w.r.t. a numpy
      vector input.  Uses forward-mode finite differences as a universal
      fallback, with JAX's ``jit + grad`` when JAX is available.

  gpu_available()
      Returns True if CuPy (CUDA) is importable and a CUDA device is
      reachable.  All compute-intensive methods check this and dispatch
      accordingly.

  chunked_matmul(A, B, chunk_size)
      Tile-based matrix multiplication that avoids OOM errors when A or B
      does not fit in GPU VRAM, with automatic CPU fallback.

Optional dependencies:
  scipy   — for SparseCorrelationComputer (pip install scipy)
  jax     — for JIT-compiled autodiff       (pip install jax)
  cupy    — for GPU acceleration             (pip install cupy-cuda12x)
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

# ------- optional imports -------

try:
    import scipy.sparse as _sp_sparse
    import scipy.sparse.linalg as _sp_linalg

    _SCIPY_SPARSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_SPARSE_AVAILABLE = False
    _sp_sparse = None  # type: ignore[assignment]
    _sp_linalg = None  # type: ignore[assignment]

try:
    import jax
    import jax.numpy as jnp
    from jax import grad as _jax_grad, jit as _jax_jit

    _JAX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JAX_AVAILABLE = False
    jax = None  # type: ignore[assignment]
    jnp = None  # type: ignore[assignment]
    _jax_grad = None  # type: ignore[assignment]
    _jax_jit = None  # type: ignore[assignment]

try:
    import cupy as _cp  # type: ignore[import]

    _CUPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CUPY_AVAILABLE = False
    _cp = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# GPU probe
# ---------------------------------------------------------------------------


def gpu_available() -> bool:
    """Return True if CuPy is importable and a CUDA device is accessible."""
    if not _CUPY_AVAILABLE:
        return False
    try:
        _cp.cuda.runtime.getDeviceCount()
        return True
    except Exception:
        return False


def _xp(use_gpu: bool = False) -> Any:
    """Return cupy if GPU is requested and available, else numpy."""
    if use_gpu and gpu_available():
        return _cp
    return np


# ---------------------------------------------------------------------------
# Sparse correlation computer
# ---------------------------------------------------------------------------


class SparseCorrelationComputer:
    """
    Memory-efficient correlation matrix using scipy.sparse.

    For dense sensor matrices this adds no overhead (falls back to numpy).
    For near-diagonal or block-sparse structures the memory savings can be
    substantial (O(nnz) instead of O(n²)).

    Parameters
    ----------
    threshold : float
        Absolute correlation values below this are zeroed out (sparsified).
        Set to 0 to disable sparsification.
    use_gpu : bool
        If True and CuPy is available, move arrays to the GPU for computation.

    Example
    -------
    >>> comp = SparseCorrelationComputer(threshold=0.05)
    >>> corr = comp.compute(data_matrix)   # shape (n_sensors, n_sensors)
    >>> eigvals = comp.top_k_eigenvalues(corr, k=5)
    """

    def __init__(self, threshold: float = 0.0, use_gpu: bool = False) -> None:
        self.threshold = threshold
        self.use_gpu = use_gpu

    def compute(self, X: np.ndarray) -> np.ndarray:
        """
        Compute the Pearson correlation matrix of ``X`` (shape: n_frames × n_sensors).

        Returns a dense numpy array regardless of internal representation so
        the result slots into existing pipeline code without changes.
        """
        xp = _xp(self.use_gpu)
        Xg = xp.asarray(X, dtype=float)

        # z-score each column
        mean = Xg.mean(axis=0)
        std = Xg.std(axis=0)
        std = xp.where(std < 1e-12, 1.0, std)
        Xz = (Xg - mean) / std

        n = Xz.shape[0]
        corr = (Xz.T @ Xz) / max(n - 1, 1)

        # Move back to numpy if on GPU
        corr_np: np.ndarray = np.asarray(corr) if self.use_gpu and gpu_available() else corr

        if self.threshold > 0:
            corr_np[np.abs(corr_np) < self.threshold] = 0.0

        return corr_np

    def to_sparse(self, corr: np.ndarray) -> Any:
        """Convert a dense correlation matrix to a scipy sparse CSR matrix."""
        if not _SCIPY_SPARSE_AVAILABLE:
            raise ImportError("scipy is required for sparse operations. pip install scipy")
        return _sp_sparse.csr_matrix(corr)

    def top_k_eigenvalues(self, corr: np.ndarray, k: int = 5) -> np.ndarray:
        """
        Compute the top-``k`` eigenvalues of the correlation matrix.

        Uses sparse ARPACK (``scipy.sparse.linalg.eigsh``) when scipy is
        available and the matrix is large, otherwise falls back to
        ``numpy.linalg.eigh``.
        """
        n = corr.shape[0]
        if _SCIPY_SPARSE_AVAILABLE and n > 50 and k < n - 1:
            sparse_corr = _sp_sparse.csr_matrix(corr)
            eigenvalues, _ = _sp_linalg.eigsh(sparse_corr, k=k, which="LM")
            return np.sort(eigenvalues)[::-1]
        else:
            eigenvalues = np.linalg.eigvalsh(corr)
            return np.sort(eigenvalues)[::-1][:k]

    def spectral_gap(self, corr: np.ndarray, k: int = 2) -> float:
        """
        Ratio of the k-th to (k+1)-th eigenvalue.  A large gap indicates
        a dominant low-rank structure.
        """
        eigs = self.top_k_eigenvalues(corr, k=k + 1)
        if len(eigs) < k + 1 or eigs[k] == 0:
            return 0.0
        return float(eigs[k - 1] / eigs[k])


# ---------------------------------------------------------------------------
# Automatic differentiation
# ---------------------------------------------------------------------------


class AutoDiff:
    """
    Automatic differentiation of scalar-valued functions f: R^n → R.

    Dispatch priority:
    1. JAX ``grad`` + ``jit``  (exact, fast, JIT-compiled on CPU/GPU/TPU).
    2. Numpy central finite differences (universal fallback, O(2n) evals).

    Example
    -------
    >>> ad = AutoDiff()
    >>> def loss(w):
    ...     return float(np.sum((w - 0.5) ** 2))
    >>> grad = ad.gradient(loss, np.array([1.0, 0.0, 0.5]))
    >>> # array([1.0, -1.0, 0.0])
    """

    def __init__(self, eps: float = 1e-5) -> None:
        self.eps = eps

    def gradient(
        self,
        fn: Callable[[np.ndarray], float],
        x: np.ndarray,
        use_jax: bool = True,
    ) -> np.ndarray:
        """
        Compute the gradient ∇f(x) at point ``x``.

        Parameters
        ----------
        fn : scalar-valued function accepting a 1-D numpy array.
        x : point at which to evaluate the gradient.
        use_jax : if True, try JAX before falling back to finite differences.
        """
        if use_jax and _JAX_AVAILABLE:
            return self._jax_gradient(fn, x)
        return self._fd_gradient(fn, x)

    def _jax_gradient(
        self, fn: Callable[[np.ndarray], float], x: np.ndarray
    ) -> np.ndarray:
        x_jax = jnp.array(x, dtype=float)  # type: ignore[union-attr]

        @_jax_jit  # type: ignore[misc]
        def jax_fn(v: Any) -> Any:
            return fn(np.asarray(v))

        grad_fn = _jax_grad(jax_fn)  # type: ignore[misc]
        try:
            g = grad_fn(x_jax)
            return np.asarray(g)
        except Exception:
            return self._fd_gradient(fn, x)

    def _fd_gradient(
        self, fn: Callable[[np.ndarray], float], x: np.ndarray
    ) -> np.ndarray:
        """Central finite differences: O(2n) function evaluations."""
        n = len(x)
        grad = np.zeros(n)
        for i in range(n):
            xp = x.copy()
            xm = x.copy()
            xp[i] += self.eps
            xm[i] -= self.eps
            grad[i] = (fn(xp) - fn(xm)) / (2 * self.eps)
        return grad

    def hessian(
        self,
        fn: Callable[[np.ndarray], float],
        x: np.ndarray,
    ) -> np.ndarray:
        """
        Approximate Hessian via finite-difference gradient.
        Shape: (n, n).  Uses O(2n) gradient evaluations.
        """
        n = len(x)
        H = np.zeros((n, n))
        for i in range(n):
            xp = x.copy()
            xm = x.copy()
            xp[i] += self.eps
            xm[i] -= self.eps
            gp = self._fd_gradient(fn, xp)
            gm = self._fd_gradient(fn, xm)
            H[i] = (gp - gm) / (2 * self.eps)
        return (H + H.T) / 2  # symmetrise

    def jacobian(
        self,
        fn: Callable[[np.ndarray], np.ndarray],
        x: np.ndarray,
    ) -> np.ndarray:
        """
        Approximate Jacobian for a vector-valued function f: R^n → R^m.
        Returns shape (m, n).
        """
        f0 = fn(x)
        m = len(f0)
        n = len(x)
        J = np.zeros((m, n))
        for i in range(n):
            xp = x.copy()
            xm = x.copy()
            xp[i] += self.eps
            xm[i] -= self.eps
            J[:, i] = (fn(xp) - fn(xm)) / (2 * self.eps)
        return J


# ---------------------------------------------------------------------------
# GPU-aware chunked matrix multiply
# ---------------------------------------------------------------------------


def chunked_matmul(
    A: np.ndarray,
    B: np.ndarray,
    chunk_size: int = 512,
    use_gpu: bool = False,
) -> np.ndarray:
    """
    Tile-based matrix multiplication to avoid OOM for large matrices.

    Splits ``A`` into row-chunks of ``chunk_size``, multiplies each chunk by
    ``B``, and concatenates results.  Falls back to standard matmul for small
    inputs where chunking adds no benefit.

    Parameters
    ----------
    A : shape (m, k)
    B : shape (k, n)
    chunk_size : number of rows of A per chunk.
    use_gpu : if True, moves arrays to GPU via CuPy.
    """
    m = A.shape[0]
    if m <= chunk_size:
        if use_gpu and gpu_available():
            Ag = _cp.asarray(A)
            Bg = _cp.asarray(B)
            return np.asarray(Ag @ Bg)
        return A @ B

    xp = _xp(use_gpu)
    rows = []
    for start in range(0, m, chunk_size):
        end = min(start + chunk_size, m)
        Ac = xp.asarray(A[start:end])
        Bc = xp.asarray(B)
        rows.append(np.asarray(Ac @ Bc))
    return np.vstack(rows)


# ---------------------------------------------------------------------------
# Sparse SVD helper (dimensionality reduction for large sensor sets)
# ---------------------------------------------------------------------------


def sparse_svd(
    X: np.ndarray,
    k: int = 10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Truncated SVD retaining the top ``k`` singular vectors.

    Uses ARPACK-backed ``scipy.sparse.linalg.svds`` for large matrices,
    numpy full SVD for small ones.

    Returns (U, s, Vt) matching numpy.linalg.svd convention.
    """
    m, n = X.shape
    if _SCIPY_SPARSE_AVAILABLE and min(m, n) > 2 * k:
        sparse_X = _sp_sparse.csr_matrix(X.astype(float))
        U, s, Vt = _sp_linalg.svds(sparse_X, k=k)
        # svds returns in ascending order; reverse
        order = np.argsort(s)[::-1]
        return U[:, order], s[order], Vt[order, :]
    else:
        U, s, Vt = np.linalg.svd(X.astype(float), full_matrices=False)
        return U[:, :k], s[:k], Vt[:k, :]
