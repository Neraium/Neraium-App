"""Pure helpers — JSON-safe coercion and number guards."""
from __future__ import annotations
from datetime import datetime
import numpy as np


def sf(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if not np.isfinite(v) else v
    if isinstance(obj, np.ndarray):
        return [sf(x) for x in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: sf(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sf(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return [sf(x) for x in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return sf(obj.to_dict())
    return obj


def sfloat(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default
