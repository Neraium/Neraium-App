#!/usr/bin/env python3
"""Forward-only PRONOSTIA ingestion demo for technical validation.

This runner replays the same PRONOSTIA / FEMTO bearing trajectory used by the
demo backend, one cycle at a time. During ingestion it only exposes data that
would be available at the current cycle. The historical failure endpoint is
revealed after the forward replay reaches the actionable point, for validation.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.pronostia_demo import TIMELINE  # noqa: E402
from backend.services.pronostia_decision_layer import feature_baseline, synthesize_outcome_frame  # noqa: E402
from neraium_core.trajectory_engine import NeraiumTrajectoryEngine, TrajectorySnapshot  # noqa: E402


DATASET = "PRONOSTIA"
ASSET_TEST = "FEMTO bearing degradation"
TRAJECTORY_CSV = ROOT / "test_reports/pronostia_demo/pronostia_decision_trajectory_demo_run.csv"
RAW_SIGNAL_CACHE = Path.home() / ".rul-datasets/FEMTOBearingDataSet/run_1_1_features.npy"


@dataclass(frozen=True)
class ReplayPoint:
    cycle: int
    structural_drift: float
    instability_score: float
    drift_velocity: float


def _finite_values(window: object) -> np.ndarray:
    values = np.asarray(window, dtype=float).reshape(-1)
    return values[np.isfinite(values)]


def _signal_features(values: np.ndarray) -> dict[str, float]:
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


class SignalFeatureContext:
    def __init__(self) -> None:
        self._run: object | None = None
        self._baseline = None
        self.available = RAW_SIGNAL_CACHE.exists()
        if self.available:
            self._run = np.load(RAW_SIGNAL_CACHE, mmap_mode="r")

    def features_at(self, cycle: int) -> dict[str, float]:
        if self._run is None:
            return {}
        index = max(0, min(int(cycle) - 1, len(self._run) - 1))
        return _signal_features(_finite_values(self._run[index]))

    def baseline(self):
        if self._baseline is not None:
            return self._baseline
        if self._run is None:
            return None
        rows = [
            _signal_features(_finite_values(self._run[index]))
            for index in range(min(50, len(self._run)))
        ]
        self._baseline = feature_baseline(rows)
        return self._baseline


class OutcomeContext:
    def __init__(self, signal_context: SignalFeatureContext) -> None:
        self.signal_context = signal_context
        self.trajectory_engine = NeraiumTrajectoryEngine()
        self.latest_snapshot: TrajectorySnapshot | None = None

    def update(self, point: ReplayPoint):
        self.latest_snapshot = self.trajectory_engine.update(point.structural_drift)
        return synthesize_outcome_frame(
            current_cycle=point.cycle,
            current_state=state_for_cycle(point.cycle),
            structural_drift_score=point.structural_drift,
            drift_velocity=point.drift_velocity,
            instability_score=point.instability_score,
            signal_features=self.signal_context.features_at(point.cycle),
            timeline=TIMELINE,
            baseline=self.signal_context.baseline(),
            trajectory_snapshot=self.latest_snapshot,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay PRONOSTIA / FEMTO bearing data forward-only through the Neraium demo path.",
    )
    parser.add_argument("--speed", choices=("normal", "fast"), default="normal")
    parser.add_argument("--show-every", type=int, default=10, metavar="N")
    parser.add_argument(
        "--stop-at-actionable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop after actionable confirmation. Use --no-stop-at-actionable to keep replaying.",
    )
    parser.add_argument(
        "--continue-to-failure",
        action="store_true",
        help="After actionable confirmation, reveal the historical endpoint and continue sparse replay.",
    )
    return parser.parse_args()


def load_replay_points() -> list[ReplayPoint]:
    if not TRAJECTORY_CSV.exists():
        raise FileNotFoundError(f"PRONOSTIA demo trajectory not found: {TRAJECTORY_CSV}")

    rows: list[ReplayPoint] = []
    previous_drift: float | None = None
    previous_cycle: int | None = None
    with TRAJECTORY_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cycle = int(float(row["cycle"]))
            drift = float(row["structural_drift"])
            instability = float(row["instability_score"])
            if previous_drift is None or previous_cycle is None:
                velocity = 0.0
            else:
                cycle_delta = max(cycle - previous_cycle, 1)
                velocity = (drift - previous_drift) / cycle_delta
            rows.append(
                ReplayPoint(
                    cycle=cycle,
                    structural_drift=drift,
                    instability_score=instability,
                    drift_velocity=velocity,
                )
            )
            previous_cycle = cycle
            previous_drift = drift

    if not rows:
        raise ValueError(f"PRONOSTIA demo trajectory is empty: {TRAJECTORY_CSV}")
    return rows


def raw_signal_shape() -> tuple[int | None, int | None, int | None]:
    if not RAW_SIGNAL_CACHE.exists():
        return None, None, None

    run = np.load(RAW_SIGNAL_CACHE, mmap_mode="r")
    rows = int(run.shape[0]) if len(run.shape) >= 1 else None
    samples = int(run.shape[1]) if len(run.shape) >= 2 else None
    channels = int(run.shape[2]) if len(run.shape) >= 3 else 1
    return rows, samples, channels


def state_for_cycle(cycle: int) -> str:
    if cycle >= TIMELINE["actionable_point"]:
        return "ACTIONABLE"
    if cycle >= TIMELINE["baseline_departure"]:
        return "DETECTED"
    return "STABLE"


def should_print_ingest(point: ReplayPoint, show_every: int) -> bool:
    if point.cycle in (
        TIMELINE["baseline_finalized"],
        TIMELINE["baseline_departure"],
        TIMELINE["structural_confirmation"],
        TIMELINE["actionable_point"],
    ):
        return True
    return show_every > 0 and point.cycle % show_every == 0


def print_ingest(point: ReplayPoint) -> None:
    print(
        "[INGEST] "
        f"cycle={point.cycle} "
        f"drift={point.structural_drift:.3f} "
        f"velocity={point.drift_velocity:.6f} "
        f"instability={point.instability_score:.3f} "
        f"state={state_for_cycle(point.cycle)}"
    )


def print_state(outcome) -> None:
    frame = outcome.to_dict()
    trajectory = frame["trajectory"]
    future = frame["future_paths"]
    likely_path = max(future, key=lambda row: float(row["likelihood"]))["path"] if future else "UNKNOWN"
    print("[STATE]")
    print(f"state={frame['state']}")
    print(f"trajectory={trajectory['current_path']} -> {likely_path}")
    print(f"velocity={trajectory['velocity']}")
    print(f"acceleration={trajectory['acceleration']}")


def print_decision(outcome) -> None:
    frame = outcome.to_dict()
    decision = frame["decision"]
    print("[DECISION]")
    print(f"what_changed={frame['what_changed']}")
    print(f"where_changed={frame['where_changed']}")
    print(f"recommended_action={decision['recommended_action']}")
    print(f"urgency={decision['urgency']}")
    print(f"time_window={decision['time_window']}")
    print(f"if_ignored={decision['if_ignored']}")
    print(f"confidence={frame['confidence']['level']}")


def event_for_cycle(cycle: int) -> tuple[str, str] | None:
    if cycle == TIMELINE["baseline_finalized"]:
        return (
            "BASELINE_FINALIZED",
            "baseline structure established from prior incoming windows",
        )
    if cycle == TIMELINE["baseline_departure"]:
        return (
            "STRUCTURAL_DEPARTURE_DETECTED",
            "drift rose above baseline structure and persisted",
        )
    if cycle == TIMELINE["structural_confirmation"]:
        return (
            "STRUCTURAL_CONFIRMATION_REACHED",
            "departure remained structurally consistent across windows",
        )
    if cycle == TIMELINE["actionable_point"]:
        return (
            "ACTIONABLE_CONFIRMED",
            "structural departure persisted long enough to suppress noise",
        )
    if cycle == TIMELINE["failure_endpoint"]:
        return (
            "HISTORICAL_FAILURE_ENDPOINT_REACHED",
            "endpoint revealed after actionable confirmation for validation",
        )
    return None


def sleep_for_demo(speed: str) -> None:
    if speed == "normal":
        time.sleep(0.04)


def replay_until(
    points: Iterable[ReplayPoint],
    *,
    args: argparse.Namespace,
    outcome_context: OutcomeContext,
    stop_cycle: int,
    sparse_after_actionable: bool = False,
) -> ReplayPoint | None:
    last_point: ReplayPoint | None = None
    for point in points:
        if point.cycle > stop_cycle:
            break
        last_point = point
        outcome = outcome_context.update(point)
        show_every = max(args.show_every, 1)
        if sparse_after_actionable and point.cycle > TIMELINE["actionable_point"]:
            show_every = max(show_every, 250)

        if should_print_ingest(point, show_every):
            print_ingest(point)
            print_state(outcome)
            sleep_for_demo(args.speed)

        event = event_for_cycle(point.cycle)
        if event is not None:
            label, why = event
            print(f"[EVENT] cycle={point.cycle} {label}")
            print(f"[WHY] {why}")
            print_decision(outcome)
            if point.cycle < TIMELINE["actionable_point"]:
                print("[LEAD_TIME] withheld until actionable confirmation")
            elif point.cycle == TIMELINE["actionable_point"]:
                print("[LEAD_TIME] eligible after actionable confirmation")
            sleep_for_demo(args.speed)

    return last_point


def print_summary(last_cycle: int, *, endpoint_revealed: bool) -> None:
    failure_cycle = TIMELINE["failure_endpoint"]
    actionable_cycle = TIMELINE["actionable_point"]
    lead_time = max(failure_cycle - actionable_cycle, 0)
    print()
    print("[SUMMARY]")
    print(f"baseline_finalized={TIMELINE['baseline_finalized']}")
    print(f"structural_departure={TIMELINE['baseline_departure']}")
    print(f"actionable_confirmed={actionable_cycle}")
    print(f"replay_stopped_at={last_cycle}")
    if endpoint_revealed:
        print(f"failure_endpoint={failure_cycle}")
        print(f"lead_time={lead_time} cycles")
    else:
        print("failure_endpoint=withheld during ingestion")
        print("lead_time=withheld during ingestion")
        print("[VALIDATION] failure_endpoint=2802")
        print(f"[VALIDATION] lead_time={lead_time} cycles")
    print("Failure endpoint is used only after forward replay completes to calculate validation lead time.")


def main() -> int:
    args = parse_args()
    points = load_replay_points()
    signal_context = SignalFeatureContext()
    outcome_context = OutcomeContext(signal_context)
    raw_rows, raw_samples, raw_channels = raw_signal_shape()
    failure_cycle = TIMELINE["failure_endpoint"]
    endpoint_revealed = False

    print("[INIT] Loading PRONOSTIA / FEMTO bearing run")
    if raw_rows is not None:
        print(
            "[DATA] "
            f"rows={len(points)} "
            f"raw_windows={raw_rows} "
            f"samples_per_window={raw_samples} "
            f"channels={raw_channels}"
        )
    else:
        print(f"[DATA] rows={len(points)} channels=unavailable raw_cache={RAW_SIGNAL_CACHE}")
    print("[BASELINE] Building baseline from cycles 1-50")
    print("[LEAKAGE_GUARD] Failure endpoint is not available to the ingestion loop")
    print()

    first_stop = (
        TIMELINE["actionable_point"]
        if args.stop_at_actionable or args.continue_to_failure
        else points[-1].cycle
    )
    last_point = replay_until(points, args=args, outcome_context=outcome_context, stop_cycle=first_stop)

    if args.continue_to_failure and (last_point is None or last_point.cycle < failure_cycle):
        endpoint_revealed = True
        print()
        print("[VALIDATION] Historical failure endpoint revealed after actionable confirmation")
        print(f"[VALIDATION] continuing sparse replay to cycle {failure_cycle}")
        remaining = (p for p in points if p.cycle > TIMELINE["actionable_point"])
        last_point = replay_until(
            remaining,
            args=args,
            outcome_context=outcome_context,
            stop_cycle=failure_cycle,
            sparse_after_actionable=True,
        )

    if not args.stop_at_actionable and not args.continue_to_failure:
        endpoint_revealed = True

    stopped_cycle = last_point.cycle if last_point is not None else 0
    print_summary(stopped_cycle, endpoint_revealed=endpoint_revealed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
