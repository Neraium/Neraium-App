from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def fit_ar1(series: Sequence[float]) -> tuple[float, float]:
    y = np.asarray(list(series), dtype=float)
    if len(y) < 5:
        return 0.0, float(y[-1]) if len(y) else 0.0

    x = y[:-1]
    z = y[1:]

    denom = float(np.dot(x, x))
    if abs(denom) < 1e-12:
        return 0.0, float(np.mean(y))

    phi = float(np.dot(x, z) / denom)
    intercept = float(np.mean(z - phi * x))
    return phi, intercept


def forecast_next(series: Sequence[float]) -> float | None:
    y = np.asarray(list(series), dtype=float)
    if len(y) < 5:
        return None

    phi, intercept = fit_ar1(y)
    return float(intercept + phi * y[-1])


def time_to_threshold_ar1(
    series: Sequence[float],
    threshold: float = 1.5,
    max_steps: int = 100,
) -> float | None:
    y = np.asarray(list(series), dtype=float)
    if len(y) < 5:
        return None

    phi, intercept = fit_ar1(y)
    current = float(y[-1])

    for step in range(1, max_steps + 1):
        current = intercept + phi * current
        if current >= threshold:
            return float(step)

    return None