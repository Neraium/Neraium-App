"""Per-system state, all derived from `SIIEngineAdapter` outputs.

The adapter is the SINGLE source of truth for regime / urgency /
instability_score / drift / velocity / pressure / confidence.

This module:
- holds the global adapter instance
- maintains per-system metadata (template, variable names, units)
- maintains per-system unified state history (capped)
- exposes scoped accessors for routers
"""
from __future__ import annotations
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np

# Make /app importable so neraium_core resolves
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from neraium_core.sii_engine_adapter import SIIEngineAdapter  # noqa: E402


# ------------------------------------------------------------------
# Adapter (env-tunable)
# ------------------------------------------------------------------
def _build_adapter() -> SIIEngineAdapter:
    return SIIEngineAdapter(
        baseline_window=int(os.environ.get("NERAIUM_BASELINE_WINDOW", "50")),
        recent_window=int(os.environ.get("NERAIUM_RECENT_WINDOW", "12")),
        detection_threshold=float(os.environ.get("NERAIUM_DETECTION_THRESHOLD", "0.65")),
    )


_adapter: SIIEngineAdapter = _build_adapter()
_run_id: str = "live"


@dataclass
class SystemRecord:
    system_id: str
    template: str
    label: str
    variables: List[str]
    units: Dict[str, str]
    history: List[Dict[str, Any]] = field(default_factory=list)
    sensor_history: List[Dict[str, float]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_systems: Dict[str, SystemRecord] = {}
HISTORY_LIMIT = 600


# ------------------------------------------------------------------
# Mutators
# ------------------------------------------------------------------
def register_system(system_id: str, template: str, label: str,
                    variables: List[str], units: Dict[str, str]) -> SystemRecord:
    rec = SystemRecord(system_id=system_id, template=template, label=label,
                       variables=variables, units=units)
    _systems[system_id] = rec
    return rec


def ingest_frame(system_id: str, sensor_values: Dict[str, float], timestamp: float) -> Dict[str, Any]:
    """Vectorise sensor_values in the system's stable variable order, ingest
    into the SII adapter, append unified state to history. Returns a JSON-
    serialisable unified state dict."""
    rec = _systems.get(system_id)
    if rec is None:
        raise KeyError(f"unknown system_id: {system_id}")
    vec = np.array([float(sensor_values.get(v, 0.0)) for v in rec.variables], dtype=float)
    state = _adapter.ingest(vec, timestamp, system_id, run_id=_run_id)
    unified: Dict[str, Any] = {
        "system_id": system_id,
        "timestamp": timestamp,
        "cycle": int(state.cycle),
        # Canonical SII fields — never reinterpret
        "regime": state.regime,
        "urgency": state.urgency,
        "instability_score": float(state.instability_score),
        "structural_drift": float(state.structural_drift),
        "drift_velocity": float(state.drift_velocity),
        "transition_pressure": float(state.transition_pressure),
        "confidence": float(state.confidence),
        "gradient_norm": float(state.gradient_norm),
        "recovery_alignment": float(state.recovery_alignment),
        "lead_time_cycles": state.detection_context.lead_time_cycles,
        "first_detection_cycle": state.detection_context.first_detection_cycle,
        "detection_confidence": float(state.detection_context.detection_confidence),
    }
    rec.history.append(unified)
    rec.sensor_history.append(dict(sensor_values))
    if len(rec.history) > HISTORY_LIMIT:
        rec.history = rec.history[-HISTORY_LIMIT:]
        rec.sensor_history = rec.sensor_history[-HISTORY_LIMIT:]
    return unified


def reset_all() -> None:
    """Reset adapter and clear all systems."""
    global _adapter, _systems
    _adapter = _build_adapter()
    _systems = {}


def reset_system(system_id: str) -> None:
    rec = _systems.pop(system_id, None)
    if rec is None:
        return
    try:
        for key in list(_adapter.engines.keys()):
            if key[0] == system_id:
                _adapter.engines.pop(key, None)
    except Exception:
        pass


# ------------------------------------------------------------------
# Accessors
# ------------------------------------------------------------------
def has_system(system_id: str) -> bool:
    return system_id in _systems


def get_system(system_id: str) -> Optional[SystemRecord]:
    return _systems.get(system_id)


def all_systems() -> List[SystemRecord]:
    return list(_systems.values())


def latest_state(system_id: str) -> Optional[Dict[str, Any]]:
    rec = _systems.get(system_id)
    if rec is None or not rec.history:
        return None
    return rec.history[-1]


def history(system_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    rec = _systems.get(system_id)
    if rec is None:
        return []
    return rec.history[-limit:]


def latest_sensors(system_id: str) -> Optional[Dict[str, float]]:
    rec = _systems.get(system_id)
    if rec is None or not rec.sensor_history:
        return None
    return rec.sensor_history[-1]
