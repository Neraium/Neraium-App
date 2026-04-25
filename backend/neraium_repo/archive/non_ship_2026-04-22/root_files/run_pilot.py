#!/usr/bin/env python3
"""Convenience entrypoint: run the pilot scenario CLI from repo root."""

from __future__ import annotations

import runpy
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_TARGET = _ROOT / "examples" / "pilot" / "run_pilot.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
