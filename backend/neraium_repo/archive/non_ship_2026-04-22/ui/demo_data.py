from __future__ import annotations

import csv
import math
import os
from csv import DictReader
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from neraium_core.alignment import StructuralEngine
from neraium_core.tetrahedral_state import compute_tetrahedral_state

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_TURBO_SOURCE = Path(
    "C:/Users/Owner/Downloads/WUR_AutonomousGreenhouseProject_EDA-main/"
    "WUR_AutonomousGreenhouseProject_EDA-main/iGrow/greenhouse_results_turbo.csv"
)
LOCAL_TURBO_SOURCE = REPO_ROOT / "greenhouse_demo" / "greenhouse_results_turbo.csv"
_REAL_REPLAY_CACHE: list[dict[str, Any]] | None = None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _is_numeric_string(value: str) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in {"true", "1", "yes", "admit", "admitted"}:
        return True
    if raw in {"false", "0", "no", "deny", "denied", "suppressed"}:
        return False
    return None


def _is_truthy(value: Any) -> bool:
    parsed = _coerce_optional_bool(value)
    return bool(parsed)


def _normalize_numeric_timestamp(value: float) -> str | None:
    if not math.isfinite(value):
        return None
    abs_value = abs(value)
    if abs_value > 10_000_000:
        epoch_seconds = value
        if abs_value >= 1_000_000_000_000_000_000:
            epoch_seconds = value / 1_000_000_000
        elif abs_value >= 1_000_000_000_000_000:
            epoch_seconds = value / 1_000_000
        elif abs_value >= 10_000_000_000:
            epoch_seconds = value / 1_000
        try:
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return (datetime(1899, 12, 30, tzinfo=timezone.utc) + timedelta(days=value)).isoformat()
    except OverflowError:
        return None


def _normalize_timestamp(value: Any, index: int, base_time: datetime) -> str:
    try:
        raw = str(value or "").strip()
        if isinstance(value, (int, float)):
            normalized = _normalize_numeric_timestamp(float(value))
            if normalized:
                return normalized
        if raw and _is_numeric_string(raw):
            normalized = _normalize_numeric_timestamp(float(raw))
            if normalized:
                return normalized
        if raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return (base_time + timedelta(minutes=index)).isoformat()


def _resolve_turbo_source() -> Path | None:
    env_source = os.getenv("GREENHOUSE_RESULTS_TURBO_CSV")
    candidates = [Path(env_source)] if env_source else []
    candidates.extend([WINDOWS_TURBO_SOURCE, LOCAL_TURBO_SOURCE])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _parse_sensor_values_from_row(row: dict[str, Any]) -> dict[str, float]:
    sensor_values: dict[str, float] = {}
    non_sensor_cols = {
        "timestamp", "site_id", "asset_id", "state", "regime_name", "interpreted_state", "system_health", "risk_level",
        "signal_emitted", "event_admitted", "confidence", "confidence_score", "structural_drift_score", "relational_stability_score",
        "explanation", "explanation_text", "operator_message",
    }
    for col, value in row.items():
        if col in non_sensor_cols:
            continue
        if not value or not _is_numeric_string(str(value)):
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            continue
        sensor_values[col] = numeric
    return sensor_values


def _normalize_engine_result(result: dict[str, Any], frame: dict[str, Any]) -> dict[str, Any]:
    drift = _clamp(_coerce_float(result.get("structural_drift_score"), _coerce_float(result.get("drift_score"), 0.0)))
    stability = _clamp(_coerce_float(result.get("relational_stability_score"), _coerce_float(result.get("stability_score"), 1.0)))
    confidence = _clamp(
        _coerce_float(
            result.get("confidence_score"),
            _coerce_float(result.get("confidence"), _clamp(0.62 + drift * 0.3)),
        )
    )
    admitted_override = _coerce_optional_bool(result.get("signal_emitted"))
    if admitted_override is None:
        admitted_override = _coerce_optional_bool(result.get("event_admitted"))
    admitted = admitted_override if admitted_override is not None else (drift >= 0.55 and stability <= 0.45)
    return {
        **result,
        "timestamp": frame["timestamp"],
        "site_id": frame["site_id"],
        "asset_id": frame["asset_id"],
        "sensor_values": frame["sensor_values"],
        "state": str(result.get("state") or _state_from_drift(drift)),
        "regime_name": str(result.get("regime_name") or result.get("interpreted_state") or result.get("state") or "greenhouse_demo"),
        "structural_drift_score": round(drift, 6),
        "relational_stability_score": round(stability, 6),
        "system_health": str(result.get("risk_level") or result.get("system_health") or _health_from_drift(drift)).lower(),
        "confidence_score": round(confidence, 6),
        "event_admitted": bool(admitted),
        "evidence_summary": str(
            result.get("explanation_text")
            or result.get("explanation")
            or result.get("operator_message")
            or "Processed telemetry replayed through StructuralEngine."
        ).strip(),
    }


def _run_structural_replay(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = StructuralEngine()
    records: list[dict[str, Any]] = []
    for frame in frames:
        result = engine.process_frame(frame)
        if not isinstance(result, dict):
            continue
        records.append(_normalize_engine_result(result, frame))
    return records


def _load_rows_from_turbo_results(*, limit: int | None) -> list[dict[str, Any]]:
    source = _resolve_turbo_source()
    if source is None:
        return []
    csv.field_size_limit(10_000_000)
    with source.open("r", encoding="utf-8") as handle:
        raw_rows = list(DictReader(handle))

    if not raw_rows:
        return []
    base_time = datetime.now(timezone.utc) - timedelta(minutes=max(1, len(raw_rows)))
    normalized: list[dict[str, Any]] = []
    position_history: list[list[float]] = []
    engine = StructuralEngine()

    for idx, row in enumerate(raw_rows):
        timestamp = _normalize_timestamp(row.get("timestamp"), idx, base_time)
        site_id = str(row.get("site_id") or "grow-house")
        asset_id = str(row.get("asset_id") or "zone-A")
        sensor_values = _parse_sensor_values_from_row(row)

        phase = str(row.get("phase") or row.get("transition_state") or "unknown").strip()
        interpreted_state = str(row.get("interpreted_state") or row.get("state") or "unknown").strip()
        explanation_text = str(
            row.get("explanation_text") or row.get("operator_message") or row.get("explanation") or ""
        ).strip()
        if not explanation_text:
            explanation_text = "No explanation provided in greenhouse_results_turbo.csv."

        normalized_row: dict[str, Any] = {
            "timestamp": timestamp,
            "site_id": site_id,
            "asset_id": asset_id,
            "sensor_values": sensor_values,
            "state": interpreted_state,
            "regime_name": phase or interpreted_state,
            "system_phase": phase,
            "transition_type": (phase or "STABLE").upper(),
            "explanation_text": explanation_text,
            "evidence_summary": explanation_text,
        }

        if sensor_values:
            result = engine.process_frame(
                {
                    "timestamp": timestamp,
                    "site_id": site_id,
                    "asset_id": asset_id,
                    "sensor_values": sensor_values,
                }
            )
            if isinstance(result, dict):
                normalized_row.update(_normalize_engine_result(result, normalized_row))

        # Fall back to CSV metrics if engine output is unavailable.
        if "structural_drift_score" not in normalized_row:
            dynamic_signal_strength = _clamp(
                _coerce_float(
                    row.get("dynamic_signal_strength"),
                    _coerce_float(row.get("signal_strength"), _coerce_float(row.get("structural_drift_score"), 0.0)),
                )
            )
            confidence = _clamp(_coerce_float(row.get("confidence_score"), _coerce_float(row.get("confidence"), 0.0)))
            event_admitted_override = _coerce_optional_bool(row.get("signal_emitted"))
            if event_admitted_override is None:
                event_admitted_override = _coerce_optional_bool(row.get("event_admitted"))

            normalized_row.update(
                {
                    "risk_level": str(row.get("risk_level") or "unknown").strip(),
                    "system_health": str(row.get("risk_level") or "unknown").strip().lower(),
                    "confidence_score": confidence,
                    "dynamic_signal_strength": dynamic_signal_strength,
                    "structural_drift_score": dynamic_signal_strength,
                    "relational_stability_score": round(
                        _clamp(_coerce_float(row.get("relational_stability_score"), 1.0 - dynamic_signal_strength)),
                        6,
                    ),
                    "event_admitted": bool(event_admitted_override),
                }
            )

        structural_drift = _clamp(_coerce_float(normalized_row.get("structural_drift_score"), 0.0))
        relational_instability = _clamp(1.0 - _coerce_float(normalized_row.get("relational_stability_score"), 1.0))
        temporal_consistency = _clamp(
            _coerce_float(
                row.get("temporal_consistency_score"),
                _coerce_float(row.get("coherence_score"), _coerce_float(normalized_row.get("confidence_score"), 0.0)),
            )
        )
        transition_pressure = _clamp(_coerce_float(row.get("transition_pressure"), structural_drift))

        tetrahedral_state = compute_tetrahedral_state(
            structural_drift_score=structural_drift,
            relational_instability_score=relational_instability,
            transition_pressure=transition_pressure,
            temporal_consistency_score=temporal_consistency,
            history_positions=position_history[-50:] if len(position_history) > 0 else None,
        )
        position = tetrahedral_state.get("position", [0.0, 0.0, 0.0])
        if isinstance(position, (list, tuple)) and len(position) >= 3:
            position_history.append([float(position[0]), float(position[1]), float(position[2])])

        normalized_row["tetrahedral_state"] = tetrahedral_state
        normalized.append(normalized_row)
    normalized.sort(key=lambda entry: str(entry.get("timestamp") or ""))
    if isinstance(limit, int) and limit > 0:
        return normalized[:limit]
    return normalized


def load_greenhouse_demo_bundle(*, limit: int | None = 320) -> tuple[list[dict[str, Any]], str]:
    global _REAL_REPLAY_CACHE
    if _REAL_REPLAY_CACHE is None:
        _REAL_REPLAY_CACHE = _load_rows_from_turbo_results(limit=None)
    rows = _REAL_REPLAY_CACHE or []
    source = _resolve_turbo_source()
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    return rows, str(source) if source else "greenhouse_results_turbo.csv"


def _generate_synthetic_replay(*, timesteps: int = 120, base_time: datetime | None = None) -> list[dict[str, Any]]:
    """Generate a synthetic replay dataset with clear progression.

    Creates a deterministic sequence showing:
    - Stable baseline (0-20 steps)
    - Early drift (20-35 steps)
    - Transition pressure (35-55 steps)
    - Divergence/confirmed change (55-80 steps)
    - Recovery/new coherence (80-120 steps)

    All fields are populated for full UI contract.
    """
    if base_time is None:
        # Use fixed base time for determinism: every run produces identical output
        base_time = datetime(2026, 4, 10, 0, 0, 0, tzinfo=timezone.utc)

    rows: list[dict[str, Any]] = []
    position_history: list[list[float]] = []

    for t in range(timesteps):
        # Phase progression (deterministic, smooth)
        t / max(timesteps - 1, 1)

        # Define phase boundaries
        if t < 20:
            # STABLE BASELINE
            phase = "BASELINE"
            transition_type = "STABLE"
            drift = 0.08 + 0.02 * math.sin(t / 5.0)  # slight noise
            stability = 0.92 - 0.01 * (t / 20.0)
            coherence = 0.88 + 0.02 * math.cos(t / 7.0)
            confidence = 0.75 + 0.05 * math.cos(t / 4.0)
            event_admitted = False
            risk_level = "nominal"

        elif t < 35:
            # EARLY DRIFT - system starting to change
            phase = "DRIFT_WATCH"
            transition_type = "TRANSITION"
            drift_progress = (t - 20) / 15.0
            drift = 0.12 + 0.25 * drift_progress + 0.03 * math.sin(t / 3.0)
            stability = 0.91 - 0.08 * drift_progress
            coherence = 0.87 - 0.05 * drift_progress
            confidence = 0.70 - 0.08 * drift_progress + 0.03 * math.cos(t / 5.0)
            event_admitted = False
            risk_level = "watch"

        elif t < 55:
            # TRANSITION PRESSURE - sustained change
            phase = "TRANSITION_ACTIVE"
            transition_type = "TRANSITION"
            drift_progress = (t - 35) / 20.0
            drift = 0.38 + 0.22 * drift_progress + 0.04 * math.sin(t / 2.5)
            stability = 0.83 - 0.25 * drift_progress
            coherence = 0.82 - 0.15 * drift_progress
            confidence = 0.62 - 0.08 * drift_progress
            # Admission starts to be considered
            event_admitted = drift >= 0.55
            risk_level = "watch" if not event_admitted else "degraded"

        elif t < 80:
            # DIVERGENCE - confirmed change
            phase = "REORGANIZATION_UNDERWAY"
            transition_type = "REORGANIZATION"
            drift_progress = (t - 55) / 25.0
            drift = 0.60 + 0.28 * drift_progress
            stability = 0.58 - 0.22 * drift_progress
            coherence = 0.67 + 0.15 * drift_progress  # coherence improves as system settles
            confidence = 0.54 + 0.15 * drift_progress  # confidence rises in reorganization
            event_admitted = True
            risk_level = "degraded"

        else:
            # RECOVERY/NEW COHERENCE - system reaches new equilibrium
            phase = "NEW_BASELINE"
            transition_type = "STABLE"
            recovery_progress = (t - 80) / max(timesteps - 80, 1)
            drift = 0.88 - 0.20 * recovery_progress  # drifts back toward middle
            stability = 0.36 + 0.35 * recovery_progress  # stability recovers
            coherence = 0.82 + 0.12 * recovery_progress
            confidence = 0.69 + 0.18 * recovery_progress
            event_admitted = True if t < 90 else False  # admission only during change
            risk_level = "nominal" if t > 100 else "degraded"

        # Clamp all values to [0, 1]
        drift = _clamp(drift, 0.0, 1.0)
        stability = _clamp(stability, 0.0, 1.0)
        coherence = _clamp(coherence, 0.0, 1.0)
        confidence = _clamp(confidence, 0.0, 1.0)
        snr_score = 1.2 + 0.8 * math.sin(t / 8.0) + 0.3 * (t / timesteps)

        # Dynamic signal strength = drift with smoothing
        dynamic_signal_strength = drift

        # Persistence minutes: increases during transition
        if transition_type == "TRANSITION":
            persistence_minutes = 5 + 40 * ((t - 20) / 35.0) if t >= 20 else 0
        elif transition_type == "REORGANIZATION":
            persistence_minutes = 45 + 10 * ((t - 55) / 25.0) if t >= 55 else 0
        else:
            persistence_minutes = 0

        # Corroborating signals increase during transition
        if transition_type in {"TRANSITION", "REORGANIZATION"}:
            corroborating_signal_count = max(0, int((t - 20) / 5) if t >= 20 else 0)
        else:
            corroborating_signal_count = 0

        # Build the row
        timestamp = (base_time + timedelta(minutes=t)).isoformat()

        # Compute transition pressure from phase progression
        if phase == "BASELINE":
            transition_pressure = 0.0
        elif phase == "DRIFT_WATCH":
            transition_pressure = 0.25 * ((t - 20) / 15.0)
        elif phase == "TRANSITION_ACTIVE":
            transition_pressure = 0.25 + 0.65 * ((t - 35) / 20.0)
        elif phase == "REORGANIZATION_UNDERWAY":
            transition_pressure = 0.90 + 0.08 * ((t - 55) / 25.0)
        else:  # NEW_BASELINE
            transition_pressure = max(0.0, 0.98 - 0.20 * ((t - 80) / max(timesteps - 80, 1)))

        transition_pressure = _clamp(transition_pressure, 0.0, 1.0)

        # Compute tetrahedral state
        tetrahedral_state = compute_tetrahedral_state(
            structural_drift_score=drift,
            relational_instability_score=1.0 - stability,
            transition_pressure=transition_pressure,
            temporal_consistency_score=coherence,
            history_positions=position_history[-50:] if len(position_history) > 0 else None,
        )

        # Track position for history
        position = tetrahedral_state.get("position", [0.0, 0.0, 0.0])
        if isinstance(position, (list, tuple)) and len(position) >= 3:
            position_history.append([float(position[0]), float(position[1]), float(position[2])])

        row: dict[str, Any] = {
            "timestamp": timestamp,
            "site_id": "greenhouse-demo",
            "asset_id": "zone-synthetic",
            "system_phase": phase,
            "interpreted_state": phase,
            "state": phase,
            "regime_name": phase,
            "transition_type": transition_type,
            "system_health": risk_level,
            "risk_level": risk_level,
            "confidence_score": round(confidence, 6),
            "structural_drift_score": round(drift, 6),
            "relational_stability_score": round(stability, 6),
            "coherence_score": round(coherence, 6),
            "dynamic_signal_strength": round(dynamic_signal_strength, 6),
            "snr_score": round(snr_score, 6),
            "persistence_minutes": round(persistence_minutes, 2),
            "corroborating_signal_count": corroborating_signal_count,
            "event_admitted": event_admitted,
            "explanation_text": _synthetic_explanation(phase, drift, stability, event_admitted),
            "evidence_summary": _synthetic_explanation(phase, drift, stability, event_admitted),
            "sensor_values": {},
            "tetrahedral_state": tetrahedral_state,
        }
        rows.append(row)

    return rows


def _synthetic_explanation(phase: str, drift: float, stability: float, admitted: bool) -> str:
    """Generate contextual explanation text for synthetic replay."""
    if phase == "BASELINE":
        return "Stable baseline: drift low, stability and coherence high."
    elif phase == "DRIFT_WATCH":
        return f"Early drift detected (drift={drift:.2f}): system starting to diverge from baseline; under observation."
    elif phase == "TRANSITION_ACTIVE":
        return f"Active transition (drift={drift:.2f}, stability={stability:.2f}): sustained change detected; threshold approaching."
    elif phase == "REORGANIZATION_UNDERWAY":
        if admitted:
            return f"Coherent reorganization confirmed (drift={drift:.2f}): transition has been admitted; system in flux."
        else:
            return f"System reorganizing (drift={drift:.2f}): change persisting; coherence forming."
    elif phase == "NEW_BASELINE":
        if admitted:
            return "System recovering from reorganization; new baseline establishing."
        else:
            return "New stable baseline reached; system has settled into new configuration."
    return "Synthetic replay telemetry: system state under examination."


def load_greenhouse_demo_records(*, limit: int | None = 180, use_synthetic: bool = False) -> list[dict[str, Any]]:
    """Load greenhouse demo records.

    Args:
        limit: Maximum number of records to return
        use_synthetic: If True, use synthetic dataset; if False, use real replay

    Returns:
        List of demo records
    """
    if use_synthetic:
        synthetic_rows = _generate_synthetic_replay(timesteps=120)
        if isinstance(limit, int) and limit > 0:
            return synthetic_rows[:limit]
        return synthetic_rows

    rows, _ = load_greenhouse_demo_bundle(limit=limit)
    return rows


def load_fd004_demo_records(*, limit: int | None = 250, unit_id: str = "unit_001") -> list[dict[str, Any]]:
    """Load FD004 demo records from real prognostics dataset.

    Args:
        limit: Maximum number of records to return
        unit_id: The FD004 unit to load (e.g., "unit_001")

    Returns:
        List of demo records normalized to UI contract format
    """
    fd004_csv = REPO_ROOT / "fd004_outputs_subset" / "fd004_real_timeseries.csv"

    if not fd004_csv.is_file():
        return []

    csv.field_size_limit(10_000_000)
    rows: list[dict[str, Any]] = []
    position_history: list[list[float]] = []

    with fd004_csv.open("r", encoding="utf-8") as f:
        reader = DictReader(f)
        for row in reader:
            if str(row.get("asset_id", "")).strip() != unit_id:
                continue

            # Extract and normalize FD004 fields
            timestamp_str = str(row.get("timestamp", "")).strip()
            timestamp = timestamp_str if timestamp_str else datetime.now(timezone.utc).isoformat()

            drift = _clamp(_coerce_float(row.get("structural_drift_score"), 0.0))
            composite_instability = _clamp(_coerce_float(row.get("composite_instability"), 0.0))
            stability = _clamp(1.0 - composite_instability)

            trend = str(row.get("trend", "stable")).lower().strip()
            phase = str(row.get("phase", "stable")).lower().strip()
            risk_level_raw = str(row.get("risk_level", "LOW")).upper().strip()

            # Map risk level to system health
            if risk_level_raw == "HIGH":
                system_health = "critical"
                confidence_boost = 0.85
            elif risk_level_raw == "MEDIUM":
                system_health = "degraded"
                confidence_boost = 0.75
            else:
                system_health = "nominal"
                confidence_boost = 0.65

            # Determine transition type based on trend
            if trend == "increasing":
                transition_type = "REORGANIZATION"
            elif trend == "decreasing":
                transition_type = "TRANSITION"
            else:
                transition_type = "STABLE"

            # Compute confidence score based on drift and stability
            confidence = _clamp(confidence_boost * (1.0 - drift * 0.4) + stability * 0.2)

            # Compute tetrahedral state
            transition_pressure = _clamp(drift)
            coherence = _clamp(0.85 - composite_instability * 0.5)

            tetrahedral_state = compute_tetrahedral_state(
                structural_drift_score=drift,
                relational_instability_score=composite_instability,
                transition_pressure=transition_pressure,
                temporal_consistency_score=coherence,
                history_positions=position_history[-50:] if len(position_history) > 0 else None,
            )

            # Track position for history
            position = tetrahedral_state.get("position", [0.0, 0.0, 0.0])
            if isinstance(position, (list, tuple)) and len(position) >= 3:
                position_history.append([float(position[0]), float(position[1]), float(position[2])])

            operator_message = str(row.get("operator_message", "")).strip()

            normalized_row = {
                "timestamp": timestamp,
                "site_id": "fd004-prognostics",
                "asset_id": unit_id,
                "system_phase": phase,
                "state": phase,
                "regime_name": phase,
                "transition_type": transition_type,
                "system_health": system_health,
                "risk_level": risk_level_raw.lower(),
                "confidence_score": round(confidence, 6),
                "structural_drift_score": round(drift, 6),
                "relational_stability_score": round(stability, 6),
                "coherence_score": round(coherence, 6),
                "dynamic_signal_strength": round(drift, 6),
                "snr_score": round(1.5 + drift * 0.8, 6),
                "persistence_minutes": 0.0,
                "corroborating_signal_count": 0,
                "event_admitted": drift >= 0.55 and stability <= 0.45,
                "explanation_text": operator_message or f"FD004 unit {unit_id} prognostics: {phase} phase, {risk_level_raw} risk.",
                "evidence_summary": operator_message or f"FD004 unit {unit_id} prognostics: {phase} phase, {risk_level_raw} risk.",
                "sensor_values": {},
                "tetrahedral_state": tetrahedral_state,
            }
            rows.append(normalized_row)

    if isinstance(limit, int) and limit > 0:
        return rows[:limit]
    return rows
