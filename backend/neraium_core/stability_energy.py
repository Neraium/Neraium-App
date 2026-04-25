"""
Stability Energy + Gradient Field Layer: Energy landscape-based dynamic system stability.

This module computes an energy landscape based on normalized state vectors and the baseline
covariance structure. The energy defines a stability basin; motion through this landscape
reveals system recovery or escape trajectories.

Core math:
  E(z) = (z - mu_B)^T Sigma_B_inv (z - mu_B)
  grad_E(z) = 2 * Sigma_B_inv * (z - mu_B)
  recovery_force = -grad_E(z)
  escape_alignment = dot(v, grad_E) / (||v|| ||grad_E|| + eps)
  recovery_alignment = dot(v, recovery_force) / (||v|| ||recovery_force|| + eps)

Warmup behavior:
  - If insufficient history, return safe defaults with label "INSUFFICIENT_HISTORY"
  - No errors during warmup
  - All fields populated with 0 or null values
"""

from __future__ import annotations

from typing import Any

import numpy as np


EPSILON = 1e-9
REGULARIZATION_LAMBDA = 1e-4


def _safe_norm(v: np.ndarray) -> float:
    """Compute norm safely, handling near-zero vectors."""
    if v.size == 0:
        return 0.0
    try:
        n = float(np.linalg.norm(v))
        return max(EPSILON, n)
    except (ValueError, TypeError):
        return EPSILON


def _safe_inverse_covariance(
    cov: np.ndarray,
    lambda_reg: float = REGULARIZATION_LAMBDA,
) -> np.ndarray | None:
    """
    Compute regularized inverse covariance via Moore-Penrose pseudo-inverse.

    Args:
        cov: Covariance matrix (d x d)
        lambda_reg: Regularization parameter

    Returns:
        Regularized inverse covariance, or None if computation fails
    """
    try:
        if cov.shape[0] == 0 or cov.shape[1] == 0:
            return None

        # Add regularization diagonal
        dim = cov.shape[0]
        cov_reg = cov + lambda_reg * np.eye(dim)

        # Pseudo-inverse (robust to singular matrices)
        cov_inv = np.linalg.pinv(cov_reg)
        return cov_inv
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return None


def compute_energy(
    z: np.ndarray,
    mu_B: np.ndarray,
    sigma_B_inv: np.ndarray,
) -> float:
    """
    Compute Mahalanobis energy E(z) = (z - mu_B)^T Sigma_B_inv (z - mu_B).

    Args:
        z: Current state vector (d,)
        mu_B: Baseline mean (d,)
        sigma_B_inv: Regularized inverse covariance (d x d)

    Returns:
        Scalar energy (>= 0)
    """
    if z.size == 0 or mu_B.size == 0:
        return 0.0

    try:
        delta = np.asarray(z, dtype=float) - np.asarray(mu_B, dtype=float)
        energy = float(delta @ sigma_B_inv @ delta)
        return max(0.0, energy)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return 0.0


def compute_gradient(
    z: np.ndarray,
    mu_B: np.ndarray,
    sigma_B_inv: np.ndarray,
) -> np.ndarray:
    """
    Compute energy gradient grad_E(z) = 2 * Sigma_B_inv * (z - mu_B).

    Args:
        z: Current state vector (d,)
        mu_B: Baseline mean (d,)
        sigma_B_inv: Regularized inverse covariance (d x d)

    Returns:
        Gradient vector (d,)
    """
    if z.size == 0 or mu_B.size == 0:
        return np.array([], dtype=float)

    try:
        delta = np.asarray(z, dtype=float) - np.asarray(mu_B, dtype=float)
        grad = 2.0 * (sigma_B_inv @ delta)
        return np.asarray(grad, dtype=float)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return np.zeros_like(z, dtype=float)


def compute_alignment(
    v: np.ndarray,
    direction: np.ndarray,
    eps: float = EPSILON,
) -> float:
    """
    Compute alignment between velocity and direction.

    alignment = dot(v, direction) / (||v|| ||direction|| + eps)

    Args:
        v: Velocity vector (d,)
        direction: Direction vector (d,)
        eps: Denominator safety constant

    Returns:
        Scalar alignment in [-1, 1]
    """
    if v.size == 0 or direction.size == 0:
        return 0.0

    try:
        v_arr = np.asarray(v, dtype=float)
        d_arr = np.asarray(direction, dtype=float)

        dot_prod = float(v_arr @ d_arr)
        norm_v = _safe_norm(v_arr)
        norm_d = _safe_norm(d_arr)

        denom = norm_v * norm_d + eps
        alignment = dot_prod / denom
        return float(np.clip(alignment, -1.0, 1.0))
    except (ValueError, TypeError):
        return 0.0


def label_stability_direction(
    escape_alignment: float,
    recovery_alignment: float,
    energy_delta: float,
    thresholds: dict[str, float] | None = None,
) -> tuple[str, str]:
    """
    Label system motion direction based on alignments and energy change.

    Labeling rules:
      - ESCAPING_STABILITY: escape_alignment > 0.50 AND energy_delta > 0
      - RECOVERING: recovery_alignment > 0.50 AND energy_delta < 0
      - SIDEWAYS_TRANSITION: abs(escape_alignment) < 0.25
      - DEGRADING: else (elevated energy without recovery alignment)

    Args:
        escape_alignment: Alignment with escaping (instability) direction
        recovery_alignment: Alignment with recovery direction
        energy_delta: Change in energy (current - previous)
        thresholds: Optional override thresholds dict with keys:
            "escape_threshold", "recovery_threshold", "sideways_threshold"

    Returns:
        (label, interpretation) tuple
    """
    if thresholds is None:
        thresholds = {}

    escape_thr = float(thresholds.get("escape_threshold", 0.50))
    recovery_thr = float(thresholds.get("recovery_threshold", 0.50))
    sideways_thr = float(thresholds.get("sideways_threshold", 0.25))

    if escape_alignment > escape_thr and energy_delta > 0.0:
        label = "ESCAPING_STABILITY"
        interp = "System trajectory is aligned with increasing instability energy."
    elif recovery_alignment > recovery_thr and energy_delta < 0.0:
        label = "RECOVERING"
        interp = "System trajectory is moving back toward the learned stability basin."
    elif abs(escape_alignment) < sideways_thr:
        label = "SIDEWAYS_TRANSITION"
        interp = "System is moving across the stability landscape without clear recovery or escape direction."
    else:
        label = "DEGRADING"
        interp = "System energy is elevated or rising without confirmed recovery alignment."

    return label, interp


def compute_stability_energy(
    z_current: np.ndarray,
    z_previous: np.ndarray | None,
    mu_baseline: np.ndarray,
    sigma_baseline: np.ndarray,
    prev_energy: float | None = None,
    prev_energy_velocity: float | None = None,
    energy_velocity_alpha: float = 0.8,
    regularization_lambda: float = REGULARIZATION_LAMBDA,
) -> dict[str, Any]:
    """
    Comprehensive stability energy computation for a single frame.

    Computes energy landscape metrics and motion characteristics in the energy space.
    Streaming-safe: does not require full history, only current + previous state.

    Args:
        z_current: Current normalized state vector (d,)
        z_previous: Previous normalized state vector (d,) or None for first frame
        mu_baseline: Baseline mean vector (d,)
        sigma_baseline: Baseline covariance matrix (d x d)
        prev_energy: Previous energy scalar (for delta computation)
        prev_energy_velocity: Previous energy velocity (for acceleration)
        energy_velocity_alpha: EMA smoothing for energy velocity
        regularization_lambda: Regularization parameter for covariance inversion

    Returns:
        Dict with keys:
            "energy": float - current energy
            "energy_delta": float - E(t) - E(t-1)
            "energy_velocity": float - smoothed energy_delta
            "energy_acceleration": float - energy_velocity(t) - energy_velocity(t-1)
            "instability_gradient_norm": float - ||grad_E||
            "recovery_force_norm": float - ||-grad_E||
            "escape_alignment": float - alignment(velocity, gradient)
            "recovery_alignment": float - alignment(velocity, -gradient)
            "direction_label": str - ESCAPING_STABILITY | RECOVERING | SIDEWAYS_TRANSITION | DEGRADING
            "interpretation": str - Human-readable explanation
            "history": dict - State for next frame (prev_energy, prev_energy_velocity)
    """
    output = {
        "energy": 0.0,
        "energy_delta": 0.0,
        "energy_velocity": 0.0,
        "energy_acceleration": 0.0,
        "instability_gradient_norm": 0.0,
        "recovery_force_norm": 0.0,
        "escape_alignment": 0.0,
        "recovery_alignment": 0.0,
        "direction_label": "INSUFFICIENT_HISTORY",
        "interpretation": "Insufficient history to compute stability energy.",
        "history": {
            "prev_energy": None,
            "prev_energy_velocity": None,
        },
    }

    # Validate inputs
    try:
        z_curr = np.asarray(z_current, dtype=float)
        mu_b = np.asarray(mu_baseline, dtype=float)
        sigma_b = np.asarray(sigma_baseline, dtype=float)

        if z_curr.size == 0 or mu_b.size == 0 or sigma_b.size == 0:
            return output

        if z_curr.shape[0] != mu_b.shape[0]:
            return output

        # Compute regularized inverse covariance
        sigma_b_inv = _safe_inverse_covariance(sigma_b, lambda_reg=regularization_lambda)
        if sigma_b_inv is None:
            return output

        # Energy at current state
        energy_current = compute_energy(z_curr, mu_b, sigma_b_inv)

        # Gradient and recovery force at current state
        grad_current = compute_gradient(z_curr, mu_b, sigma_b_inv)
        recovery_force_current = -grad_current

        grad_norm = _safe_norm(grad_current)
        recovery_norm = _safe_norm(recovery_force_current)

        output["energy"] = float(energy_current)
        output["instability_gradient_norm"] = float(grad_norm)
        output["recovery_force_norm"] = float(recovery_norm)

        # Velocity: z(t) - z(t-1)
        if z_previous is not None and z_previous.size > 0:
            z_prev = np.asarray(z_previous, dtype=float)
            if z_prev.shape[0] == z_curr.shape[0]:
                velocity = z_curr - z_prev

                # Alignments: cosine similarity between velocity and gradient directions
                escape_align = compute_alignment(velocity, grad_current)
                recovery_align = compute_alignment(velocity, recovery_force_current)

                output["escape_alignment"] = float(escape_align)
                output["recovery_alignment"] = float(recovery_align)

        # Energy dynamics
        if prev_energy is not None:
            energy_delta = energy_current - prev_energy
            output["energy_delta"] = float(energy_delta)

            # Smooth energy velocity with EMA
            new_energy_velocity = (
                energy_velocity_alpha * energy_delta +
                (1.0 - energy_velocity_alpha) * (prev_energy_velocity or 0.0)
            )
            output["energy_velocity"] = float(new_energy_velocity)

            # Energy acceleration
            if prev_energy_velocity is not None:
                energy_accel = new_energy_velocity - prev_energy_velocity
                output["energy_acceleration"] = float(energy_accel)

            # Update history for next frame
            output["history"]["prev_energy"] = float(energy_current)
            output["history"]["prev_energy_velocity"] = float(new_energy_velocity)

            # Label direction based on alignments and energy delta
            label, interp = label_stability_direction(
                output["escape_alignment"],
                output["recovery_alignment"],
                energy_delta,
            )
            output["direction_label"] = label
            output["interpretation"] = interp
        else:
            # First frame with history: can compute velocity but not energy dynamics
            if z_previous is not None and z_previous.size > 0:
                output["direction_label"] = "INSUFFICIENT_HISTORY"
                output["interpretation"] = "First comparison frame; energy dynamics unavailable."
                output["history"]["prev_energy"] = float(energy_current)
                output["history"]["prev_energy_velocity"] = 0.0

    except (ValueError, TypeError, np.linalg.LinAlgError):
        pass

    return output


def insufficient_history_payload() -> dict[str, Any]:
    """Safe default payload during warmup."""
    return {
        "energy": 0.0,
        "energy_delta": 0.0,
        "energy_velocity": 0.0,
        "energy_acceleration": 0.0,
        "instability_gradient_norm": 0.0,
        "recovery_force_norm": 0.0,
        "escape_alignment": 0.0,
        "recovery_alignment": 0.0,
        "direction_label": "INSUFFICIENT_HISTORY",
        "interpretation": "Engine warmup: insufficient baseline or history.",
    }


__all__ = [
    "compute_energy",
    "compute_gradient",
    "compute_alignment",
    "compute_stability_energy",
    "label_stability_direction",
    "insufficient_history_payload",
    "EPSILON",
    "REGULARIZATION_LAMBDA",
]
