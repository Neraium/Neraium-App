from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso8601(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        f = float(value)
    except Exception:
        return float(default)
    if f != f:  # NaN
        return float(default)
    return f


def l2_norm(vector: Iterable[float]) -> float:
    return sqrt(sum((v * v for v in vector)))


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
