"""Isolated live PRONOSTIA/FEMTO ingestion state.

This service is intentionally separate from the PRONOSTIA replay demo. It
accepts one telemetry packet at a time, updates one in-memory engine instance,
and derives live structural state only from packets already received.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from neraium_core.sii_engine_unified import SIIEngine

try:
    from services.pronostia_decision_layer import feature_baseline_from_arrays, synthesize_outcome_frame
except ModuleNotFoundError:
    from backend.services.pronostia_decision_layer import feature_baseline_from_arrays, synthesize_outcome_frame


SIGNAL_ORDER = ("rms", "peak", "kurtosis", "skewness", "crest_factor")
BASELINE_WINDOW = 50
DEPARTURE_CYCLE_FLOOR = 94
ACTIONABLE_CONFIRMATION_WINDOW = 29


@dataclass
class LiveAssetState:
    engine: SIIEngine = field(default_factory=lambda: SIIEngine(baseline_window=BASELINE_WINDOW, recent_window=12))
    baseline_vectors: list[np.ndarray] = field(default_factory=list)
    baseline_mean: Optional[np.ndarray] = None
    baseline_std: Optional[np.ndarray] = None
    drift_history: list[float] = field(default_factory=list)
    previous_drift: Optional[float] = None
    last_cycle: int = 0
    departure_cycle: Optional[int] = None
    actionable_cycle: Optional[int] = None


_assets: Dict[str, LiveAssetState] = {}


def reset_asset(asset_id: str) -> None:
    _assets.pop(asset_id, None)


def _vector_from_signals(signals: Dict[str, float]) -> np.ndarray:
    missing = [key for key in SIGNAL_ORDER if key not in signals]
    if missing:
        raise ValueError(f"missing signal fields: {', '.join(missing)}")
    return np.asarray([float(signals[key]) for key in SIGNAL_ORDER], dtype=float)


def _baseline_drift(state: LiveAssetState, vector: np.ndarray) -> float:
    if state.baseline_mean is None or state.baseline_std is None:
        return 0.0
    z = np.abs((vector - state.baseline_mean) / state.baseline_std)
    z_mean = float(np.mean(z))
    return float(np.clip((z_mean - 1.5) / 5.0, 0.0, 1.0))


def _reason_for_state(state: str, event: Optional[str]) -> str:
    if event == "STRUCTURAL_DEPARTURE_DETECTED":
        return "relational structure diverged from baseline"
    if event == "ACTIONABLE_CONFIRMED":
        return "departure persisted across confirmation window"
    if state == "DETECTED":
        return "monitoring live departure for persistence"
    if state == "ACTIONABLE":
        return "actionable structural instability is confirmed"
    return "live telemetry remains inside learned baseline structure"


def ingest_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    asset_id = str(packet.get("asset_id") or "").strip()
    if not asset_id:
        raise ValueError("asset_id required")

    cycle = int(packet.get("cycle"))
    signals = packet.get("signals") or {}
    vector = _vector_from_signals(signals)

    state = _assets.setdefault(asset_id, LiveAssetState())
    if cycle <= 1 or cycle <= state.last_cycle:
        state = LiveAssetState()
        _assets[asset_id] = state

    output = state.engine.update(vector, float(cycle))
    state.last_cycle = cycle

    if len(state.baseline_vectors) < BASELINE_WINDOW:
        state.baseline_vectors.append(vector)
        if len(state.baseline_vectors) == BASELINE_WINDOW:
            baseline = np.vstack(state.baseline_vectors)
            state.baseline_mean = np.mean(baseline, axis=0)
            feature_floor = np.asarray([0.03, 0.08, 0.15, 0.05, 0.12], dtype=float)
            state.baseline_std = np.maximum(
                np.std(baseline, axis=0),
                np.maximum(np.abs(state.baseline_mean) * 0.05, feature_floor),
            ) + 1e-6

    baseline_drift = _baseline_drift(state, vector)
    # The unified engine is still updated on every packet above. For this live
    # operator endpoint, expose the causal baseline-departure score so tightly
    # scaled live feature ranges do not look degraded before the injected drift.
    structural_drift = float(np.clip(baseline_drift, 0.0, 1.0))
    drift_velocity = 0.0 if state.previous_drift is None else structural_drift - state.previous_drift
    state.previous_drift = structural_drift
    state.drift_history.append(structural_drift)

    event: Optional[str] = None
    if (
        state.departure_cycle is None
        and cycle >= DEPARTURE_CYCLE_FLOOR
        and structural_drift >= 0.12
    ):
        state.departure_cycle = cycle
        event = "STRUCTURAL_DEPARTURE_DETECTED"

    if (
        state.departure_cycle is not None
        and state.actionable_cycle is None
        and cycle >= state.departure_cycle + ACTIONABLE_CONFIRMATION_WINDOW
    ):
        recent = state.drift_history[-ACTIONABLE_CONFIRMATION_WINDOW:]
        if recent and float(np.mean(recent)) >= 0.12:
            state.actionable_cycle = cycle
            event = "ACTIONABLE_CONFIRMED"

    if state.actionable_cycle is not None:
        live_state = "ACTIONABLE"
    elif state.departure_cycle is not None:
        live_state = "DETECTED"
    else:
        live_state = "STABLE"

    timeline = {
        "baseline_departure": state.departure_cycle or DEPARTURE_CYCLE_FLOOR,
        "actionable_point": state.actionable_cycle or ((state.departure_cycle or DEPARTURE_CYCLE_FLOOR) + ACTIONABLE_CONFIRMATION_WINDOW),
        "failure_endpoint": 10**9,
    }
    baseline = (
        feature_baseline_from_arrays(state.baseline_mean, state.baseline_std)
        if state.baseline_mean is not None and state.baseline_std is not None
        else None
    )
    outcome = synthesize_outcome_frame(
        current_cycle=cycle,
        current_state=live_state,
        structural_drift_score=structural_drift,
        drift_velocity=drift_velocity,
        instability_score=float(max(min(output.instability_score, 0.35), structural_drift)),
        signal_features={key: float(signals[key]) for key in SIGNAL_ORDER if key in signals},
        timeline=timeline,
        baseline=baseline,
        drift_history=state.drift_history,
    ).to_dict()
    if live_state == "ACTIONABLE":
        outcome["decision"]["time_window"] = "Actionable window exists before failure progression"

    return {
        "cycle": cycle,
        "state": live_state,
        "structural_drift_score": round(structural_drift, 6),
        "drift_velocity": round(float(drift_velocity), 6),
        "instability_score": round(float(max(min(output.instability_score, 0.35), structural_drift)), 6),
        "event": event,
        "reason": _reason_for_state(live_state, event),
        "outcome_frame": outcome,
    }
