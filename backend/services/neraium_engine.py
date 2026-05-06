"""Compatibility resolver for the canonical NeraiumEngine.

This module intentionally contains no engine business logic. It only resolves
the implementation class from the supported locations so existing imports keep
working:

    from backend.services.neraium_engine import NeraiumEngine
"""

from __future__ import annotations

CHECKED = (
    "backend.services.neraium_engine_impl",
    "backend.services.decision_synth",
    "neraium_engine",
)

try:
    from backend.services.neraium_engine_impl import NeraiumEngine

    SOURCE = "backend.services.neraium_engine_impl"
except ImportError as impl_error:
    try:
        from backend.services.decision_synth import NeraiumEngine

        SOURCE = "backend.services.decision_synth"
    except ImportError as synth_error:
        try:
            from neraium_engine import NeraiumEngine

            SOURCE = "root neraium_engine"
        except ImportError as root_error:
            raise ImportError(
                "NeraiumEngine implementation not found. Checked: "
                + ", ".join(CHECKED)
            ) from root_error

print(f"[ENGINE] Loaded NeraiumEngine from {SOURCE}")

_ENGINE: NeraiumEngine | None = None


def get_engine() -> NeraiumEngine:
    """Return the process-local canonical engine instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = NeraiumEngine()
    return _ENGINE


def reset_engine() -> NeraiumEngine:
    """Reset the process-local engine instance."""
    global _ENGINE
    _ENGINE = NeraiumEngine()
    return _ENGINE


__all__ = ["NeraiumEngine", "SOURCE", "get_engine", "reset_engine"]
