"""Engine state container — wraps SIIEngineAdapter (single source of truth).

The new SIIEngine emits the canonical contract:
  - instability_score : float in [0,1]
  - regime           : STABLE | TRANSITION | UNSTABLE | LOCK_IN | WARMUP
  - urgency          : NOMINAL | WATCH | ALERT | CRITICAL
  - structural_drift, drift_velocity, transition_pressure, confidence

We map urgency → legacy `state` (STABLE/WATCH/ALERT) for the existing UI
and return the full unified dict on every frame.

Configuration via env vars (all optional):
  NERAIUM_BASELINE_WINDOW (default 50)
  NERAIUM_RECENT_WINDOW   (default 12)
  NERAIUM_DETECTION_THRESHOLD (default 0.65)
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional, Any
import numpy as np

from neraium_core.sii_engine_adapter import SIIEngineAdapter


# ------------------------------------------------------------------
# Adapter (single global) + per-asset bookkeeping
# ------------------------------------------------------------------
def _build_adapter() -> SIIEngineAdapter:
    return SIIEngineAdapter(
        baseline_window=int(os.environ.get("NERAIUM_BASELINE_WINDOW", "50")),
        recent_window=int(os.environ.get("NERAIUM_RECENT_WINDOW", "12")),
        detection_threshold=float(os.environ.get("NERAIUM_DETECTION_THRESHOLD", "0.65")),
    )


_adapter: SIIEngineAdapter = _build_adapter()
_run_id: Optional[str] = None
_demo_asset_meta: Dict[str, Any] = {}
_global_idx: int = 0

# Stable per-asset sensor key order (so the vector dimension is consistent)
_sensor_order: Dict[str, List[str]] = {}

# Per-asset history of unified state dicts (what every API endpoint reads)
_raw_results: Dict[str, List[Dict[str, Any]]] = {}


URGENCY_TO_LEGACY_STATE = {
    "NOMINAL": "STABLE",
    "WATCH": "WATCH",
    "ALERT": "ALERT",
    "CRITICAL": "ALERT",  # the legacy UI doesn't have a CRITICAL bucket
}


def _vectorise(asset_id: str, sensor_values: Dict[str, float]) -> np.ndarray:
    """Convert a sensor_values dict to a numpy vector with stable order."""
    if asset_id not in _sensor_order:
        # First time we see this asset — lock in alphabetical key order
        _sensor_order[asset_id] = sorted(sensor_values.keys())
    keys = _sensor_order[asset_id]
    return np.array([float(sensor_values.get(k, 0.0)) for k in keys], dtype=float)


def next_idx() -> int:
    global _global_idx
    idx = _global_idx
    _global_idx += 1
    return idx


def process_frame(asset_id: str, frame: dict) -> dict:
    """Process one frame through SIIEngineAdapter. Returns a full unified dict
    (not a UnifiedSystemState — JSON-friendly already).
    """
    sv: Dict[str, float] = frame.get("sensor_values", {}) or {}
    vec = _vectorise(asset_id, sv)
    ts = float(frame.get("timestamp", 0.0))
    state = _adapter.ingest(sv if False else vec, ts, asset_id, run_id=(_run_id or "default"))

    # Build canonical raw dict — keys mirror what builders.py expects
    raw: Dict[str, Any] = {
        "_index": next_idx(),
        "_asset_id": asset_id,
        "asset_id": asset_id,
        "timestamp": ts,
        "cycle": state.cycle,
        # SII canonical fields
        "regime": state.regime,
        "urgency": state.urgency,
        "instability_score": float(state.instability_score),
        "structural_drift_score": float(state.structural_drift),
        "drift_velocity": float(state.drift_velocity),
        "transition_pressure": float(state.transition_pressure),
        "confidence_score": float(state.confidence),
        "gradient_norm": float(state.gradient_norm),
        "recovery_alignment": float(state.recovery_alignment),
        # Legacy compatibility shims for existing UI / builders
        "state": URGENCY_TO_LEGACY_STATE.get(state.urgency, "STABLE"),
        "interpreted_state": state.regime,
        "phase": "stable" if state.urgency == "NOMINAL" else "transitioning",
        "risk_level": state.urgency,
        "engine_ready": state.regime != "WARMUP",
        "transition_state": "ACTIVE" if state.regime == "TRANSITION" else "NONE",
        "regime_name": state.regime,
        "regime_distance": None,
        "operator_message": "",
        "signal_emitted": state.urgency in ("ALERT", "CRITICAL"),
        # Sensor metadata (for SensorsTab fallback)
        "sensor_relationships": list(_sensor_order.get(asset_id, [])),
        "active_sensor_count": len(_sensor_order.get(asset_id, [])),
        # SII history (last 50)
        "instability_history": [float(v) for v in state.instability_history[-50:]],
        "regime_history": list(state.regime_history[-50:]),
        "velocity_history": [float(v) for v in state.velocity_history[-50:]],
        # Detection context
        "lead_time_cycles": state.detection_context.lead_time_cycles,
        "first_detection_cycle": state.detection_context.first_detection_cycle,
        "detection_confidence": float(state.detection_context.detection_confidence),
    }
    _raw_results.setdefault(asset_id, []).append(raw)
    return raw


def reset_all() -> None:
    """Wipe all engine state and rebuild the adapter."""
    global _adapter, _raw_results, _global_idx, _run_id, _demo_asset_meta, _sensor_order
    _adapter = _build_adapter()
    _raw_results = {}
    _sensor_order = {}
    _demo_asset_meta = {}
    _global_idx = 0
    _run_id = None


def reset_asset(asset_id: str) -> None:
    _raw_results.pop(asset_id, None)
    _sensor_order.pop(asset_id, None)
    _demo_asset_meta.pop(asset_id, None)
    # SIIEngineAdapter has no public per-asset reset; engines dict is internal
    try:
        for key in list(_adapter.engines.keys()):
            if key[0] == asset_id:
                _adapter.engines.pop(key, None)
    except Exception:
        pass


def first_asset() -> Optional[str]:
    return next(iter(_raw_results)) if _raw_results else None


def get_results(asset_id: str) -> List[Dict[str, Any]]:
    return _raw_results.get(asset_id, [])


def all_results() -> Dict[str, List[Dict[str, Any]]]:
    return _raw_results


def asset_meta() -> Dict[str, Any]:
    return _demo_asset_meta


def set_run_id(rid: Optional[str]) -> None:
    global _run_id
    _run_id = rid


def get_run_id() -> Optional[str]:
    return _run_id


# ------------------------------------------------------------------
# Helpers exposed for the readiness endpoint
# ------------------------------------------------------------------
def asset_readiness(asset_id: str) -> dict:
    """Return readiness info for an asset, derived from the SIIEngineAdapter."""
    key = (asset_id, _run_id or "default")
    eng = _adapter.engines.get(key)
    sensors = _sensor_order.get(asset_id, [])
    if eng is None:
        return {
            "asset_id": asset_id, "ready": False, "frames_collected": 0,
            "baseline_window": _adapter.baseline_window, "sensors": sensors,
            "total_results": len(_raw_results.get(asset_id, [])),
        }
    return {
        "asset_id": asset_id,
        "ready": eng.engine.baseline_ready if hasattr(eng.engine, "baseline_ready") else False,
        "frames_collected": eng.cycle_count,
        "baseline_window": _adapter.baseline_window,
        "sensors": sensors,
        "total_results": len(_raw_results.get(asset_id, [])),
    }


def all_asset_ids() -> List[str]:
    return list(_raw_results.keys())
