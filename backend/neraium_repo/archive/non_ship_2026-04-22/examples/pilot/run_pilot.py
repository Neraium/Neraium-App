from __future__ import annotations

import argparse
import copy
import gc
import json
import logging
import math
import os
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from neraium_core.alignment import StructuralEngine
from neraium_core.service import StructuralMonitoringService
from neraium_core.store import ResultStore


PILOT_KEYS = ("timestamp", "signals", "score", "status", "aligned", "anomaly")

# Score → pilot state (deterministic; decoupled from engine drift-based state).
SCORE_STABLE_LT = 1.25
SCORE_WATCH_LT = 2.0

# interpreted_state smoothing: require this many consecutive raw proposals before switching.
INTERPRETED_CONSECUTIVE_REQUIRED = 3

# Severe score move: bypass hysteresis for interpreted_state.
SEVERE_SCORE_DELTA = 0.75
SEVERE_SCORE_HIGH = 2.25
SEVERE_SCORE_LOW_PRIOR = 1.45

INTERPRETED_CANONICAL = frozenset(
    {
        "NOMINAL_STRUCTURE",
        "COHERENCE_UNDER_CONSTRAINT",
        "REGIME_SHIFT_OBSERVED",
        "COUPLING_INSTABILITY_OBSERVED",
        "STRUCTURAL_INSTABILITY_OBSERVED",
    }
)

SCENARIO_LOG = logging.getLogger("neraium_pilot.scenario")


def _setup_scenario_logging() -> None:
    SCENARIO_LOG.setLevel(logging.INFO)
    if not SCENARIO_LOG.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] neraium_pilot.scenario: %(message)s"))
        SCENARIO_LOG.addHandler(handler)
    SCENARIO_LOG.propagate = False


def _load_json_payloads(path: Path) -> list[dict[str, Any]]:
    payloads, _meta = _load_pilot_input(path)
    return payloads


def _load_pilot_input(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Load pilot input JSON. Returns (payloads, file_meta).

    Optional top-level keys on a dict root (alongside payloads/items/sequence) are preserved
    in file_meta, e.g. ``interpreted_smoothing: { "consecutive_required": 2 }``.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    file_meta: dict[str, Any] = {}

    def _extract_meta(d: dict[str, Any]) -> None:
        for k in (
            "scenario",
            "description",
            "timesteps",
            "interpreted_smoothing",
        ):
            if k in d:
                file_meta[k] = d[k]

    if isinstance(data, list):
        return data, file_meta

    if isinstance(data, dict):
        _extract_meta(data)
        for key in ("payloads", "items", "sequence"):
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe, file_meta
        return [data], file_meta

    raise ValueError("Input JSON must be an object or array of objects")


def _pilot_view(result: dict[str, Any]) -> dict[str, Any]:
    return {k: result.get(k) for k in PILOT_KEYS}


def state_from_score(score: float | None) -> str:
    """Deterministic pilot state from instability score (latest_instability)."""
    if score is None:
        return "STABLE"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "STABLE"
    if math.isnan(s) or math.isinf(s):
        return "STABLE"
    if s < SCORE_STABLE_LT:
        return "STABLE"
    if s < SCORE_WATCH_LT:
        return "WATCH"
    return "ALERT"


@dataclass
class InterpretedStateSmoother:
    """Hysteresis on engine interpreted_state; duplicate frames do not advance this."""

    consecutive_required: int = INTERPRETED_CONSECUTIVE_REQUIRED
    _current: str = "NOMINAL_STRUCTURE"
    _pending: str | None = None
    _pending_count: int = 0

    @property
    def current(self) -> str:
        return self._current

    def _normalize_proposed(self, raw: Any) -> str:
        if raw is None:
            return "NOMINAL_STRUCTURE"
        text = str(raw)
        return text if text in INTERPRETED_CANONICAL else "NOMINAL_STRUCTURE"

    def _severe_jump(self, score: float, prev_score: float | None) -> bool:
        if prev_score is None:
            return False
        try:
            ps = float(prev_score)
            sc = float(score)
        except (TypeError, ValueError):
            return False
        if math.isnan(sc) or math.isnan(ps):
            return False
        if sc - ps >= SEVERE_SCORE_DELTA:
            return True
        if sc >= SEVERE_SCORE_HIGH and ps < SEVERE_SCORE_LOW_PRIOR:
            return True
        return False

    def update(self, proposed_raw: Any, score: float, prev_score: float | None) -> str:
        proposed = self._normalize_proposed(proposed_raw)

        if proposed == self._current:
            self._pending = None
            self._pending_count = 0
            return self._current

        if self._severe_jump(score, prev_score):
            self._current = proposed
            self._pending = None
            self._pending_count = 0
            return self._current

        if proposed == self._pending:
            self._pending_count += 1
        else:
            self._pending = proposed
            self._pending_count = 1

        if self._pending_count >= self.consecutive_required:
            self._current = self._pending
            self._pending = None
            self._pending_count = 0

        return self._current


def generate_signals(t: int, rng: np.random.Generator) -> dict[str, float]:
    """
    Evolving multivariate scenario (timestep index t >= 0).

    - t < 30: stable baseline - correlated, non-identical channels.
    - 30 <= t < 60: regime shift - one channel ramps steadily vs the others.
    - t >= 60: instability - independent high noise / coupling breakdown.
    """
    if t < 30:
        u = float(t)
        s1 = 10.0 + 0.004 * u + 0.015 * math.sin(u / 4.5)
        s2 = s1 + 0.12 + 0.008 * math.sin(u / 6.0)
        s3 = 10.0 + 0.012 * math.sin((u + 3.5) / 4.5) + 0.003 * u
        s4 = s1 + 0.06 * math.sin(u / 7.0) + float(rng.normal(0.0, 0.025))
        return {"s1": s1, "s2": s2, "s3": s3, "s4": s4}

    if t < 60:
        latent = rng.normal(0.0, 0.04)
        ramp = 0.095 * float(t - 30)
        base = 10.0
        eps = 0.02
        return {
            "s1": base + ramp + latent + rng.normal(0.0, eps),
            "s2": base + latent + rng.normal(0.0, eps),
            "s3": base + latent + rng.normal(0.0, eps),
            "s4": base + latent + rng.normal(0.0, eps),
        }

    u = float(t - 60)
    return {
        "s1": 8.0 + 0.08 * u + rng.normal(0.0, 1.4),
        "s2": 14.0 + rng.normal(0.0, 1.6),
        "s3": 6.0 + rng.normal(0.0, 1.5),
        "s4": 11.0 + rng.normal(0.0, 1.7),
    }


def _iso_timestamp(start: datetime, step: int) -> str:
    return (start + timedelta(seconds=step)).isoformat()


def _scenario_timestamp(start: datetime, logical_t: int) -> tuple[str, list[str]]:
    tags: list[str] = []
    if 70 <= logical_t < 80:
        sec = max(0, logical_t - 10)
        tags.append("delayed_timestamp_lag_10_steps")
        return (start + timedelta(seconds=sec)).isoformat(), tags
    return _iso_timestamp(start, logical_t), tags


def _rounded_signals_from_result(result: dict[str, Any]) -> dict[str, float | None] | None:
    pv = _pilot_view(result)
    signals = pv.get("signals")
    if not isinstance(signals, dict):
        return None
    rounded: dict[str, float | None] = {}
    for k, v in signals.items():
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            rounded[str(k)] = None
        else:
            rounded[str(k)] = round(float(v), 6)
    return rounded


def _result_score(result: dict[str, Any]) -> float | None:
    pv = _pilot_view(result)
    s = pv.get("score")
    if s is None:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _row_missing_data(signals: dict[str, float | None] | None, degraded: list[str] | None) -> bool:
    if degraded and "missing_s2_s3" in degraded:
        return True
    if not isinstance(signals, dict):
        return False
    return any(v is None for v in signals.values())


def build_pilot_record(
    *,
    timestep: int,
    result: dict[str, Any],
    pilot_state: str,
    interpreted_smoothed: str,
    frame_type: str,
    missing_data: bool,
    pilot_score: float | None = None,
) -> dict[str, Any]:
    """pilot_score overrides engine score for duplicate rows (same logical timestep, identical payload)."""
    sc = pilot_score if pilot_score is not None else _result_score(result)
    return {
        "timestep": timestep,
        "signals": _rounded_signals_from_result(result),
        "state": pilot_state,
        "interpreted_state": interpreted_smoothed,
        "score": sc,
        "frame_type": frame_type,
        "missing_data": missing_data,
    }


def summarize_pilot_records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats for pilot_results.json summary block."""
    if not rows:
        return {
            "first_step_by_state": {},
            "count_by_state": {},
            "count_by_interpreted_state": {},
            "max_score": None,
            "mean_score_after_timestep_60": None,
            "duplicate_frame_count": 0,
            "missing_data_frame_count": 0,
            "first_step_by_interpreted_state": {},
        }

    states = [str(r.get("state", "STABLE")) for r in rows]
    interps = [str(r.get("interpreted_state", "NOMINAL_STRUCTURE")) for r in rows]
    scores: list[float] = []
    for r in rows:
        s = r.get("score")
        if s is not None:
            try:
                scores.append(float(s))
            except (TypeError, ValueError):
                pass

    first_by_state: dict[str, int | None] = {}
    for name in ("STABLE", "WATCH", "ALERT"):
        first_by_state[name] = None
        for r in rows:
            if str(r.get("state")) == name:
                first_by_state[name] = int(r["timestep"])
                break

    first_by_interp: dict[str, int] = {}
    for r in rows:
        k = str(r.get("interpreted_state", "NOMINAL_STRUCTURE"))
        ts = int(r["timestep"])
        if k not in first_by_interp:
            first_by_interp[k] = ts

    after_60 = [float(r["score"]) for r in rows if int(r["timestep"]) >= 60 and r.get("score") is not None]
    mean_after_60 = round(sum(after_60) / len(after_60), 6) if after_60 else None

    dup_count = sum(1 for r in rows if r.get("frame_type") == "duplicate")
    miss_count = sum(1 for r in rows if r.get("missing_data") is True)

    return {
        "first_step_by_state": first_by_state,
        "count_by_state": dict(Counter(states)),
        "count_by_interpreted_state": dict(Counter(interps)),
        "max_score": round(max(scores), 6) if scores else None,
        "mean_score_after_timestep_60": mean_after_60,
        "duplicate_frame_count": dup_count,
        "missing_data_frame_count": miss_count,
        "first_step_by_interpreted_state": first_by_interp,
        "score_thresholds": {
            "STABLE_lt": SCORE_STABLE_LT,
            "WATCH_lt": SCORE_WATCH_LT,
            "ALERT_gte": SCORE_WATCH_LT,
        },
        "interpreted_smoothing": {
            "consecutive_required": INTERPRETED_CONSECUTIVE_REQUIRED,
            "severe_score_delta": SEVERE_SCORE_DELTA,
            "severe_score_high": SEVERE_SCORE_HIGH,
            "severe_score_low_prior": SEVERE_SCORE_LOW_PRIOR,
        },
    }


def _write_pilot_results_document(path: Path, records: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"records": records, "summary": summary}
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    SCENARIO_LOG.info("saved %s records + summary to %s", len(records), path.resolve())


def _apply_scenario_degradations(
    sensors: dict[str, float],
    logical_t: int,
) -> tuple[dict[str, float | None], list[str]]:
    tags: list[str] = []
    out: dict[str, float | None] = dict(sensors)

    if 40 <= logical_t < 45:
        out["s2"] = None
        out["s3"] = None
        tags.append("missing_s2_s3")

    if logical_t >= 75:
        out["s4"] = 9.5
        tags.append("s4_flatline")

    return out, tags


def _print_step_record(
    *,
    ingest_seq: int,
    logical_t: int,
    result: dict[str, Any],
    pilot_state: str,
    interpreted_smoothed: str,
    frame_type: str,
    missing_data: bool,
    degraded: list[str] | None = None,
    pilot_score: float | None = None,
) -> None:
    pv = _pilot_view(result)
    rounded_signals = _rounded_signals_from_result(result)
    display_score = pilot_score if pilot_score is not None else pv.get("score")

    record: dict[str, Any] = {
        "ingest_seq": ingest_seq,
        "logical_t": logical_t,
        "timestamp": pv.get("timestamp"),
        "signals": rounded_signals,
        "score": display_score,
        "status": pv.get("status"),
        "state": pilot_state,
        "interpreted_state": interpreted_smoothed,
        "frame_type": frame_type,
        "missing_data": missing_data,
        "confidence": result.get("confidence"),
        "engine_state": result.get("state"),
        "engine_interpreted_raw": result.get("interpreted_state"),
    }
    if degraded:
        record["degraded"] = degraded
    print(json.dumps(record, separators=(",", ":")))


def _log_engine_data_quality_if_degraded(
    *,
    logical_t: int,
    ingest_seq: int,
    result: dict[str, Any],
) -> None:
    dq = result.get("data_quality_summary")
    if not isinstance(dq, dict):
        return
    if dq.get("gate_passed") is not False:
        return
    SCENARIO_LOG.info(
        "engine_data_quality_degraded ingest_seq=%s logical_t=%s gate_passed=False missingness_rate=%s statuses=%s",
        ingest_seq,
        logical_t,
        dq.get("missingness_rate"),
        dq.get("statuses"),
    )


def _run_scenario(
    *,
    timesteps: int,
    seed: int,
    baseline_window: int,
    recent_window: int,
    results_path: Path,
) -> None:
    if timesteps < 100:
        raise ValueError("timesteps must be at least 100 for the pilot scenario")

    _setup_scenario_logging()

    for name in ("neraium_core.service", "neraium_core.store"):
        logging.getLogger(name).setLevel(logging.WARNING)

    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    save_records: list[dict[str, Any]] = []
    smoother = InterpretedStateSmoother()
    prev_score: float | None = None

    tmp_dir = tempfile.mkdtemp(prefix="neraium_pilot_")
    try:
        tmp_path = Path(tmp_dir)
        engine = StructuralEngine(
            baseline_window=baseline_window,
            recent_window=recent_window,
            window_stride=1,
            regime_store_path=str(tmp_path / "regimes.json"),
        )
        store = ResultStore(db_path=str(tmp_path / "run.db"))
        service = StructuralMonitoringService(engine=engine, store=store)

        first_watch: int | None = None
        first_alert: int | None = None
        ingest_seq = 0

        def process_ingest(
            *,
            logical_t: int,
            result: dict[str, Any],
            step_tags: list[str],
            frame_type: str,
            advance_smoother: bool,
        ) -> None:
            nonlocal ingest_seq, prev_score, first_watch, first_alert

            score = _result_score(result)
            pilot_state = state_from_score(score)
            pilot_score_out: float | None = score

            # Duplicate of same logical timestep: mirror pilot score/state from first ingest (engine may differ).
            if (
                not advance_smoother
                and save_records
                and int(save_records[-1]["timestep"]) == logical_t
            ):
                canon = save_records[-1]
                cs = canon.get("score")
                if cs is not None:
                    try:
                        pilot_score_out = float(cs)
                    except (TypeError, ValueError):
                        pilot_score_out = score
                pilot_state = str(canon.get("state", pilot_state))

            if advance_smoother:
                raw_interp = result.get("interpreted_state")
                interpreted_smoothed = smoother.update(raw_interp, score if score is not None else 0.0, prev_score)
            else:
                # Duplicate: do not advance hysteresis; keep last smoothed interpretation.
                interpreted_smoothed = smoother.current

            # Do not advance prev_score on duplicate ingests (keeps step-to-step jump logic on real cadence).
            if score is not None and advance_smoother:
                prev_score = score

            str(result.get("action_state", ""))
            if first_watch is None and pilot_state == "WATCH":
                first_watch = logical_t
            if first_alert is None and pilot_state == "ALERT":
                first_alert = logical_t

            rounded = _rounded_signals_from_result(result)
            missing_data = _row_missing_data(rounded, step_tags if step_tags else None)

            _log_engine_data_quality_if_degraded(
                logical_t=logical_t, ingest_seq=ingest_seq, result=result
            )
            _print_step_record(
                ingest_seq=ingest_seq,
                logical_t=logical_t,
                result=result,
                pilot_state=pilot_state,
                interpreted_smoothed=interpreted_smoothed,
                frame_type=frame_type,
                missing_data=missing_data,
                degraded=step_tags if step_tags else None,
                pilot_score=pilot_score_out if not advance_smoother else None,
            )
            save_records.append(
                build_pilot_record(
                    timestep=logical_t,
                    result=result,
                    pilot_state=pilot_state,
                    interpreted_smoothed=interpreted_smoothed,
                    frame_type=frame_type,
                    missing_data=missing_data,
                    pilot_score=pilot_score_out if not advance_smoother else None,
                )
            )
            ingest_seq += 1

        for logical_t in range(timesteps):
            raw = generate_signals(logical_t, rng)
            sensors, deg_tags = _apply_scenario_degradations(raw, logical_t)
            ts, ts_tags = _scenario_timestamp(start, logical_t)
            step_tags = list(deg_tags) + list(ts_tags)

            if logical_t == 40:
                SCENARIO_LOG.info(
                    "data_degraded window=missing_sensors logical_t=40..44 sensors=null for s2,s3"
                )
            if logical_t == 70:
                SCENARIO_LOG.info(
                    "data_degraded window=delayed_timestamps logical_t=70..79 timestamps lag 10 steps vs nominal"
                )
            if logical_t == 75:
                SCENARIO_LOG.info(
                    "data_degraded window=flatline logical_t>=75 sensor=s4 value=9.5 constant"
                )

            payload = {
                "timestamp": ts,
                "site_id": "pilot-scenario",
                "asset_id": "asset-1",
                "sensor_values": sensors,
            }

            result = service.ingest_payload(payload)
            process_ingest(
                logical_t=logical_t,
                result=result,
                step_tags=step_tags,
                frame_type="normal",
                advance_smoother=True,
            )

            if logical_t == 55:
                SCENARIO_LOG.info(
                    "data_degraded event=duplicated_frame logical_t=55 re-ingesting identical payload"
                )
                dup_payload = copy.deepcopy(payload)
                result_dup = service.ingest_payload(dup_payload)
                process_ingest(
                    logical_t=logical_t,
                    result=result_dup,
                    step_tags=["duplicated_frame"],
                    frame_type="duplicate",
                    advance_smoother=False,
                )

        del service, store, engine
        gc.collect()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    summary = summarize_pilot_records(save_records)
    summary["scenario"] = {
        "stable_baseline_t_lt_30": True,
        "first_disruption_t_ge_30": True,
        "stronger_disruption_t_ge_60": True,
        "missing_data_logical_t_40_44": True,
        "note": "state is score-threshold pilot state; interpreted_state is hysteresis-smoothed.",
    }
    summary["first_WATCH_step_action_state_legacy"] = first_watch
    summary["first_ALERT_step_action_state_legacy"] = first_alert

    _write_pilot_results_document(results_path, save_records, summary)

    print(
        json.dumps(
            {
                "summary_stdout": {
                    "scenario": "stable → regime_shift → instability",
                    "degradation_injected": {
                        "missing_s2_s3": "logical_t 40–44",
                        "duplicated_frame": "logical_t 55 (second ingest, frame_type=duplicate)",
                        "delayed_timestamps": "logical_t 70–79",
                        "s4_flatline": "logical_t ≥ 75",
                    },
                    "pilot_results_file": str(results_path.resolve()),
                    "first_WATCH_pilot_state_step": summary["first_step_by_state"].get("WATCH"),
                    "first_ALERT_pilot_state_step": summary["first_step_by_state"].get("ALERT"),
                }
            },
            indent=2,
        ),
        flush=True,
    )


def _run_file_payloads(
    path: Path,
    *,
    results_path: Path,
    baseline_window: int = 24,
    recent_window: int = 8,
) -> None:
    payloads, file_meta = _load_pilot_input(path)
    _setup_scenario_logging()

    smooth_cfg = file_meta.get("interpreted_smoothing")
    consec = INTERPRETED_CONSECUTIVE_REQUIRED
    if isinstance(smooth_cfg, dict) and "consecutive_required" in smooth_cfg:
        try:
            cr = int(smooth_cfg["consecutive_required"])
            if 1 <= cr <= 10:
                consec = cr
        except (TypeError, ValueError):
            pass
    smoother = InterpretedStateSmoother(consecutive_required=consec)
    prev_score: float | None = None
    save_records: list[dict[str, Any]] = []

    tmp_dir = tempfile.mkdtemp(prefix="neraium_pilot_")
    try:
        tmp_path = Path(tmp_dir)
        engine = StructuralEngine(
            baseline_window=baseline_window,
            recent_window=recent_window,
            window_stride=1,
            regime_store_path=str(tmp_path / "regimes.json"),
        )
        store = ResultStore(db_path=str(tmp_path / "run.db"))
        service = StructuralMonitoringService(engine=engine, store=store)

        outputs: list[dict[str, Any]] = []
        for timestep, payload in enumerate(payloads):
            result = service.ingest_payload(payload)
            outputs.append(_pilot_view(result))
            score = _result_score(result)
            pilot_state = state_from_score(score)
            interpreted_smoothed = smoother.update(
                result.get("interpreted_state"),
                score if score is not None else 0.0,
                prev_score,
            )
            if score is not None:
                prev_score = score
            rounded = _rounded_signals_from_result(result)
            missing_data = _row_missing_data(rounded, None)
            save_records.append(
                build_pilot_record(
                    timestep=timestep,
                    result=result,
                    pilot_state=pilot_state,
                    interpreted_smoothed=interpreted_smoothed,
                    frame_type="normal",
                    missing_data=missing_data,
                )
            )

        del service, store, engine
        gc.collect()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    summary = summarize_pilot_records(save_records)
    summary["interpreted_smoothing"]["consecutive_required_applied"] = consec
    if isinstance(smooth_cfg, dict):
        summary["interpreted_smoothing"]["input_file_overrides"] = dict(smooth_cfg)
    summary["scenario"] = {
        "mode": "file_payloads",
        "input_file": str(path.resolve()),
        "baseline_window": baseline_window,
        "recent_window": recent_window,
    }
    if file_meta.get("scenario") is not None:
        summary["scenario"]["input_scenario"] = file_meta.get("scenario")
    _write_pilot_results_document(results_path, save_records, summary)

    if len(outputs) == 1:
        print(json.dumps(outputs[0], indent=2))
    else:
        print(json.dumps(outputs, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Neraium Pilot Hardening Mode: dynamic scenario or JSON payload file.",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Optional JSON file: single payload, list, or {payloads|items|sequence: [...]}. "
        "Dict roots may include interpreted_smoothing: {consecutive_required: 1–10}. "
        "If omitted, runs the built-in evolving scenario (≥100 steps).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable pilot debug logging (redacted).")
    parser.add_argument("--timesteps", type=int, default=120, help="Scenario length (default 120, min 100).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible scenario noise.")
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=24,
        help="StructuralEngine baseline window (default scenario and --input file mode).",
    )
    parser.add_argument(
        "--recent-window",
        type=int,
        default=8,
        help="StructuralEngine recent window (default scenario and --input file mode).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pilot_results.json"),
        help="Write records + summary JSON document (timestep, signals, state, interpreted_state, score, frame_type).",
    )
    args = parser.parse_args()

    os.environ["NERAIUM_PILOT_HARDENING"] = "1"
    if args.debug:
        os.environ["NERAIUM_DEBUG_PILOT"] = "1"

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(str(input_path))
        _run_file_payloads(
            input_path,
            results_path=args.output,
            baseline_window=args.baseline_window,
            recent_window=args.recent_window,
        )
        return

    _run_scenario(
        timesteps=args.timesteps,
        seed=args.seed,
        baseline_window=args.baseline_window,
        recent_window=args.recent_window,
        results_path=args.output,
    )


if __name__ == "__main__":
    main()
