from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RegimeStore:
    """Persist regime library / baselines as JSON (read/write, small footprint)."""

    def __init__(self, path: str = "regime_library.json"):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"regimes": [], "baselines": {}}

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"regimes": [], "baselines": {}}

    def save(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


__all__ = ["RegimeStore"]
