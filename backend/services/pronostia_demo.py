"""PRONOSTIA-only demo runtime state.

This module owns the current operator-demo state so the Demo, Decisions, and
Audit Trail surfaces do not depend on the generic playback system.
"""

import asyncio
import csv
import math
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from services.pronostia_decision_layer import feature_baseline, synthesize_decision, synthesize_outcome_frame
    from services.intervention_boundary_estimator import InterventionBoundaryEstimator
except ModuleNotFoundError:
    from backend.services.pronostia_decision_layer import feature_baseline, synthesize_decision, synthesize_outcome_frame
    from backend.services.intervention_boundary_estimator import InterventionBoundaryEstimator


REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_ID = "PRONOSTIA"
SYSTEM_NAME = "FEMTO Bearing Test"
ASSET_TEST = "FEMTO bearing degradation"
DATASET = "PRONOSTIA"

TIMELINE = {
    "baseline_finalized": 51,
    "baseline_departure": 94,
    "structural_confirmation": 103,
    "actionable_point": 123,
    "failure_endpoint": 2802,
}

DECISION_MESSAGES = {
    "STABLE": "System operating within stable bounds.",
    "TRANSITION": "Initial structural deviation detected.",
    "UNSTABLE": "Structural instability confirmed.",
    "ACTIONABLE": "Investigate and plan intervention before degradation locks in.",
    "LOCK_IN": "Failure endpoint approached.",
}

BASELINE_MESSAGE = "Establishing baseline from incoming FEMTO bearing telemetry."
BASELINE_RECOMMENDATION = "Continue baseline capture before making degradation judgments."

EVENTS = [
    ("baseline_finalized", "Baseline finalized", TIMELINE["baseline_finalized"], "STABLE"),
    ("baseline_departure", "Baseline departure detected", TIMELINE["baseline_departure"], "TRANSITION"),
    ("structural_confirmation", "Structural confirmation reached", TIMELINE["structural_confirmation"], "UNSTABLE"),
    ("actionable_point", "Actionable point reached", TIMELINE["actionable_point"], "ACTIONABLE"),
    ("failure_endpoint", "Failure endpoint approached", TIMELINE["failure_endpoint"], "LOCK_IN"),
]

_state: Dict[str, Any] = {}
_series: Optional[List[Dict[str, Any]]] = None
_raw_signal_run: Any = None
_raw_signal_error: Optional[str] = None
_raw_signal_baseline: Any = None
_task: Optional[asyncio.Task] = None
_lock = asyncio.Lock()

SPEED_INTERVAL_SECONDS = {
    "slow": 1.5,
    "normal": 1.0,
    "fast": 0.25,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_series() -> List[Dict[str, Any]]:
    global _series
    if _series is not None:
        return _series

    csv_path = REPO_ROOT / "test_reports/pronostia_demo/pronostia_decision_trajectory_demo_run.csv"
    series: List[Dict[str, Any]] = []
    if csv_path.exists():
        with csv_path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    series.append({
                        "cycle": int(float(row["cycle"])),
                        "rul": float(row["rul"]),
                        "structural_drift": float(row["structural_drift"]),
                        "instability_score": float(row["instability_score"]),
                        "drift_norm": float(row["drift_norm"]),
                        "drift_smooth": float(row["drift_smooth"]),
                    })
                except Exception:
                    continue

    if not series:
        series = [
            {
                "cycle": cycle,
                "rul": max(TIMELINE["failure_endpoint"] - cycle, 0),
                "structural_drift": min(cycle / TIMELINE["failure_endpoint"], 1.0),
                "instability_score": min(cycle / TIMELINE["actionable_point"], 1.0),
                "drift_norm": min(cycle / TIMELINE["actionable_point"], 1.0),
                "drift_smooth": min(cycle / TIMELINE["actionable_point"], 1.0),
            }
            for cycle in range(0, TIMELINE["failure_endpoint"] + 1, 10)
        ]

    previous = None
    for point in series:
        if previous is None:
            point["drift_velocity"] = 0.0
        else:
            cycle_delta = max(int(point["cycle"]) - int(previous["cycle"]), 1)
            drift_delta = float(point["structural_drift"]) - float(previous["structural_drift"])
            point["drift_velocity"] = drift_delta / cycle_delta
        previous = point

    _series = series
    return _series


def _initial_state() -> Dict[str, Any]:
    return {
        "running": False,
        "speed": "normal",
        "current_cycle": 0,
        "current_state": "STABLE",
        "first_confirmed_detection_cycle": None,
        "baseline_finalized": False,
        "baseline_departure": False,
        "structural_confirmation": False,
        "actionable_point": False,
        "failure_endpoint": False,
        "recommendation": DECISION_MESSAGES["STABLE"],
        "events": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


def _ensure_state() -> Dict[str, Any]:
    if not _state:
        _state.update(_initial_state())
    _sync_state_to_cycle(_state)
    return _state


def _sync_state_to_cycle(st: Dict[str, Any]) -> None:
    cycle = int(st.get("current_cycle") or 0)
    st["current_state"] = _state_for_cycle(cycle)
    st["baseline_finalized"] = cycle >= TIMELINE["baseline_finalized"]
    st["baseline_departure"] = cycle >= TIMELINE["baseline_departure"]
    st["structural_confirmation"] = cycle >= TIMELINE["structural_confirmation"]
    st["actionable_point"] = cycle >= TIMELINE["actionable_point"]
    st["failure_endpoint"] = cycle >= TIMELINE["failure_endpoint"]
    st["recommendation"] = _recommendation_for_state(st)
    if st["baseline_departure"] and st.get("first_confirmed_detection_cycle") is None:
        st["first_confirmed_detection_cycle"] = TIMELINE["baseline_departure"]


def _state_for_cycle(cycle: int) -> str:
    if cycle >= TIMELINE["failure_endpoint"]:
        return "LOCK_IN"
    if cycle >= TIMELINE["actionable_point"]:
        return "ACTIONABLE"
    if cycle >= TIMELINE["structural_confirmation"]:
        return "UNSTABLE"
    if cycle >= TIMELINE["baseline_departure"]:
        return "TRANSITION"
    return "STABLE"


def _message_for_state(st: Dict[str, Any]) -> str:
    if not st.get("baseline_finalized"):
        return BASELINE_MESSAGE
    return DECISION_MESSAGES[st["current_state"]]


def _recommendation_for_state(st: Dict[str, Any]) -> str:
    if not st.get("baseline_finalized"):
        return BASELINE_RECOMMENDATION
    return DECISION_MESSAGES[st["current_state"]]


def _event_entry(key: str, message: str, cycle: int, state: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "timestamp": _now(),
        "system_id": SYSTEM_ID,
        "system_label": SYSTEM_NAME,
        "event_key": key,
        "headline": message,
        "kind": "pronostia",
        "from_value": None,
        "to_value": state,
        "frame_index": cycle,
        "instability_score": _series_value(cycle, "instability_score"),
        "drift_velocity": _series_value(cycle, "drift_norm"),
        "action_type": "PRONOSTIA_EVENT",
        "operator_note": "",
    }


def _series_value(cycle: int, key: str) -> float:
    points = _load_series()
    if not points:
        return 0.0
    nearest = min(points, key=lambda p: abs(int(p["cycle"]) - cycle))
    return float(nearest.get(key) or 0.0)


def _current_series_point(cycle: int) -> Dict[str, Any]:
    points = _load_series()
    if not points:
        return {}
    return min(points, key=lambda p: abs(int(p["cycle"]) - cycle))


def _load_raw_signal_run() -> Any:
    global _raw_signal_run, _raw_signal_error
    if _raw_signal_run is not None or _raw_signal_error is not None:
        return _raw_signal_run

    signal_path = Path.home() / ".rul-datasets/FEMTOBearingDataSet/run_1_1_features.npy"
    if not signal_path.exists():
        _raw_signal_error = f"PRONOSTIA vibration cache not found: {signal_path}"
        return None

    try:
        _raw_signal_run = np.load(signal_path, mmap_mode="r")
    except Exception as exc:
        _raw_signal_error = f"Unable to load PRONOSTIA vibration cache: {exc}"
        return None

    return _raw_signal_run


def _finite_window_values(window: Any) -> np.ndarray:
    values = np.asarray(window, dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    return values


def _signal_features(values: np.ndarray) -> Dict[str, float]:
    if values.size == 0:
        return {}

    mean = float(np.mean(values))
    std = float(np.std(values))
    rms = float(np.sqrt(np.mean(values ** 2)))
    peak = float(np.max(np.abs(values)))
    centered = values - mean
    if std > 1e-12:
        normalized = centered / std
        skewness = float(np.mean(normalized ** 3))
        kurtosis = float(np.mean(normalized ** 4))
    else:
        skewness = 0.0
        kurtosis = 0.0
    crest_factor = float(peak / rms) if rms > 1e-12 else 0.0

    return {
        "rms": rms,
        "peak": peak,
        "kurtosis": kurtosis,
        "skewness": skewness,
        "crest_factor": crest_factor,
    }


def _current_signal_features_unlocked(cycle: int) -> Dict[str, float]:
    run = _load_raw_signal_run()
    if run is None:
        return {}
    index = max(0, min(int(cycle) - 1, len(run) - 1))
    return _signal_features(_finite_window_values(run[index]))


def _signal_feature_baseline_unlocked() -> Any:
    global _raw_signal_baseline
    if _raw_signal_baseline is not None:
        return _raw_signal_baseline
    run = _load_raw_signal_run()
    if run is None:
        return None
    rows = []
    for index in range(min(50, len(run))):
        rows.append(_signal_features(_finite_window_values(run[index])))
    _raw_signal_baseline = feature_baseline(rows)
    return _raw_signal_baseline


def _intervention_boundary_for_cycle(cycle: int) -> Dict[str, Any]:
    estimator = InterventionBoundaryEstimator()
    last = None
    for point in _load_series():
        point_cycle = int(point.get("cycle") or 0)
        if point_cycle > int(cycle):
            break
        state = _state_for_cycle(point_cycle)
        product_state = "ACTIONABLE" if state == "ACTIONABLE" else "LOCK_IN" if state == "LOCK_IN" else "DETECTED" if state in ("TRANSITION", "UNSTABLE") else "STABLE"
        drift = float(point.get("structural_drift") or 0.0)
        velocity = float(point.get("drift_velocity") or 0.0)
        covariance = float(point.get("drift_norm") or drift)
        stability = max(0.08, min(1.0, 1.0 - covariance * 0.75))
        last = estimator.update(
            cycle=point_cycle,
            structural_drift_score=drift,
            relational_stability_score=stability,
            covariance_shift=covariance,
            drift_velocity=velocity,
            drift_acceleration=0.0,
            trajectory_classification="DEGRADATION" if product_state in ("DETECTED", "ACTIONABLE") else product_state,
            recovery_probability=0.72 if product_state == "STABLE" else 0.18,
            degradation_probability=0.20 if product_state == "STABLE" else 0.68,
            lock_in_probability=0.08 if product_state == "STABLE" else 0.14,
            current_state=product_state,
            baseline_ready=point_cycle >= TIMELINE["baseline_finalized"],
        )
    return last or InterventionBoundaryEstimator().update(
        cycle=0,
        structural_drift_score=0.0,
        relational_stability_score=1.0,
        covariance_shift=0.0,
        current_state="STABLE",
        baseline_ready=False,
    )


def _feature_item(label: str, key: str, current: Dict[str, float], previous: Dict[str, float]) -> Dict[str, Any]:
    value = current.get(key)
    prior = previous.get(key)
    delta = value - prior if value is not None and prior is not None else None
    return {"label": label, "key": key, "value": value, "delta": delta}


def _signal_layer_unlocked(cycle: int) -> Dict[str, Any]:
    run = _load_raw_signal_run()
    if run is None:
        return {
            "available": False,
            "source": "PRONOSTIA / FEMTO bearing degradation",
            "reason": _raw_signal_error or "PRONOSTIA vibration cache unavailable",
            "features": [],
            "waveform_preview": [],
        }

    index = max(0, min(int(cycle) - 1, len(run) - 1))
    previous_index = max(0, index - 1)
    values = _finite_window_values(run[index])
    previous_values = _finite_window_values(run[previous_index]) if index > 0 else np.asarray([], dtype=float)
    current_features = _signal_features(values)
    previous_features = _signal_features(previous_values)

    preview_values = values[-200:] if values.size > 200 else values
    waveform_preview = [
        {"sample": int(i), "value": float(v)}
        for i, v in enumerate(preview_values)
        if math.isfinite(float(v))
    ]

    return {
        "available": True,
        "source": "PRONOSTIA / FEMTO bearing degradation",
        "cycle": int(cycle),
        "sample_window": int(index + 1),
        "features": [
            _feature_item("RMS", "rms", current_features, previous_features),
            _feature_item("Peak", "peak", current_features, previous_features),
            _feature_item("Kurtosis", "kurtosis", current_features, previous_features),
            _feature_item("Skewness", "skewness", current_features, previous_features),
            _feature_item("Crest Factor", "crest_factor", current_features, previous_features),
        ],
        "waveform_preview": waveform_preview,
    }


def _apply_cycle(cycle: int) -> None:
    st = _ensure_state()
    max_cycle = TIMELINE["failure_endpoint"]
    st["current_cycle"] = max(0, min(int(cycle), max_cycle))
    st["current_state"] = _state_for_cycle(st["current_cycle"])
    st["recommendation"] = _recommendation_for_state(st)

    for key, message, event_cycle, event_state in EVENTS:
        reached = st["current_cycle"] >= event_cycle
        st[key] = reached
        if key == "baseline_departure" and reached and st["first_confirmed_detection_cycle"] is None:
            st["first_confirmed_detection_cycle"] = event_cycle
        if reached and not any(e["event_key"] == key for e in st["events"]):
            st["events"].append(_event_entry(key, message, event_cycle, event_state))

    st["updated_at"] = _now()


def _next_recorded_cycle(current_cycle: int) -> int:
    for point in _load_series():
        cycle = int(point["cycle"])
        if cycle > current_cycle:
            return cycle
    return TIMELINE["failure_endpoint"]


def _interval_for_speed(speed: str) -> float:
    return SPEED_INTERVAL_SECONDS.get(speed, SPEED_INTERVAL_SECONDS["normal"])


async def _runner() -> None:
    while True:
        async with _lock:
            st = _ensure_state()
            if not st["running"]:
                return
            speed = st["speed"]
            _apply_cycle(_next_recorded_cycle(st["current_cycle"]))
            if st["current_cycle"] >= TIMELINE["failure_endpoint"]:
                st["running"] = False
                return
        await asyncio.sleep(_interval_for_speed(speed))


def _snapshot_unlocked(include_series: bool = True) -> Dict[str, Any]:
    st = _ensure_state()
    current_point = _current_series_point(st["current_cycle"])
    signal_features = _current_signal_features_unlocked(st["current_cycle"])
    drift_history = [
        float(point.get("structural_drift") or 0.0)
        for point in _load_series()
        if int(point.get("cycle") or 0) <= int(st["current_cycle"])
    ]
    return {
        "system_id": SYSTEM_ID,
        "system": SYSTEM_NAME,
        "asset_test": ASSET_TEST,
        "dataset": DATASET,
        "running": st["running"],
        "speed": st["speed"],
        "current_cycle": st["current_cycle"],
        "current_state": st["current_state"],
        "baseline_finalized": st["baseline_finalized"],
        "baseline_departure": st["baseline_departure"],
        "structural_confirmation": st["structural_confirmation"],
        "actionable_point": st["actionable_point"],
        "failure_endpoint": st["failure_endpoint"],
        "recommendation": _recommendation_for_state(st),
        "timeline": dict(TIMELINE),
        "status": st["current_state"],
        "risk_band": "elevated" if st["current_state"] in ("UNSTABLE", "ACTIONABLE", "LOCK_IN") else "nominal",
        "severity": "FAST DEGRADATION" if st["current_state"] in ("ACTIONABLE", "LOCK_IN") else "MONITORING",
        "departure_confidence": "CONFIRMED" if st["structural_confirmation"] else "LOW",
        "decision": decision_unlocked(),
        "product_decision": synthesize_outcome_frame(
            current_cycle=st["current_cycle"],
            current_state=st["current_state"],
            structural_drift_score=float(current_point.get("structural_drift") or 0.0),
            drift_velocity=float(current_point.get("drift_velocity") or 0.0),
            instability_score=float(current_point.get("instability_score") or 0.0),
            signal_features=signal_features,
            timeline=TIMELINE,
            baseline=_signal_feature_baseline_unlocked(),
            drift_history=drift_history,
        ).to_dict(),
        "intervention_boundary": _intervention_boundary_for_cycle(st["current_cycle"]),
        "distilled_output": {
            "current_state": st["current_state"],
            "structural_drift_score": current_point.get("structural_drift"),
            "drift_trend": decision_unlocked()["trend"],
            "alert_status": _alert_status_for_state(st["current_state"]),
        },
        "signal_layer": _signal_layer_unlocked(st["current_cycle"]),
        "series": _load_series() if include_series else [],
    }


def _alert_status_for_state(state: str) -> str:
    if state in ("ACTIONABLE", "LOCK_IN"):
        return "ALERT"
    if state in ("TRANSITION", "UNSTABLE"):
        return "WATCH"
    return "NO ALERT"


def decision_unlocked() -> Dict[str, Any]:
    st = _ensure_state()
    cycle = st["current_cycle"]
    state = st["current_state"]
    time_since_departure = max(0, cycle - TIMELINE["baseline_departure"]) if st["baseline_departure"] else 0
    failure_cycle = TIMELINE["failure_endpoint"]
    first_detection_cycle = st["first_confirmed_detection_cycle"]
    lead_time_cycles = (
        max(failure_cycle - first_detection_cycle, 0)
        if first_detection_cycle is not None and failure_cycle is not None
        else None
    )
    actionable_detection_cycle = TIMELINE["actionable_point"] if st["actionable_point"] else None
    actionable_lead_cycles = (
        max(failure_cycle - actionable_detection_cycle, 0)
        if actionable_detection_cycle is not None and failure_cycle is not None
        else None
    )
    return {
        "system_id": SYSTEM_ID,
        "system": SYSTEM_NAME,
        "asset_test": ASSET_TEST,
        "dataset": DATASET,
        "current_cycle": cycle,
        "current_state": state,
        "state": state,
        "message": _message_for_state(st),
        "recommendation": _recommendation_for_state(st),
        "time_since_departure": time_since_departure,
        "lead_time_cycles": lead_time_cycles,
        "actionable_detection_cycle": actionable_detection_cycle,
        "actionable_lead_cycles": actionable_lead_cycles,
        "first_confirmed_detection_cycle": first_detection_cycle,
        "failure_cycle": failure_cycle,
        "trend": "linear_or_flat_degradation",
        "trajectory_mode": "actionable_window" if state == "ACTIONABLE" else "failure_endpoint" if state == "LOCK_IN" else "early_stage_monitoring",
        "velocity": _series_value(cycle, "drift_norm"),
        "acceleration": 0.0,
        "failure_time_estimate": None,
        "baseline_finalized": st["baseline_finalized"],
        "baseline_departure": st["baseline_departure"],
        "structural_confirmation": st["structural_confirmation"],
        "actionable_point": st["actionable_point"],
        "failure_endpoint": st["failure_endpoint"],
    }


async def snapshot(include_series: bool = True) -> Dict[str, Any]:
    async with _lock:
        return deepcopy(_snapshot_unlocked(include_series=include_series))


async def decisions() -> Dict[str, Any]:
    async with _lock:
        return {"count": 1, "items": [deepcopy(decision_unlocked())]}


async def audit() -> Dict[str, Any]:
    async with _lock:
        events = list(reversed(_ensure_state()["events"]))
        return {"count": len(events), "items": deepcopy(events)}


async def start(speed: str = "normal") -> Dict[str, Any]:
    global _task
    async with _lock:
        st = _ensure_state()
        st["speed"] = speed if speed in ("slow", "normal", "fast") else "normal"
        st["running"] = True
        st["updated_at"] = _now()
        if _task is None or _task.done():
            _task = asyncio.create_task(_runner())
        return deepcopy(_snapshot_unlocked(include_series=False))


async def stop() -> Dict[str, Any]:
    async with _lock:
        st = _ensure_state()
        st["running"] = False
        st["updated_at"] = _now()
        return deepcopy(_snapshot_unlocked(include_series=False))


async def reset() -> Dict[str, Any]:
    global _task
    async with _lock:
        _state.clear()
        _state.update(_initial_state())
        if _task is not None:
            _task.cancel()
            _task = None
        return deepcopy(_snapshot_unlocked(include_series=False))


async def set_speed(speed: str) -> Dict[str, Any]:
    async with _lock:
        st = _ensure_state()
        st["speed"] = speed if speed in ("slow", "normal", "fast") else "normal"
        st["updated_at"] = _now()
        return deepcopy(_snapshot_unlocked(include_series=False))
