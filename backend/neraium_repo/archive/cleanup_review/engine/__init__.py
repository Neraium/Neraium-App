"""Structural detection engine: unified runtime interface."""

from neraium_core.engine.schemas import BatchResult, EngineResult, InputFrame
from neraium_core.engine.unified import Engine

__all__ = ["Engine", "InputFrame", "EngineResult", "BatchResult"]
