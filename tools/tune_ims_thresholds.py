#!/usr/bin/env python3
"""Parameter sweep for IMS bearing-specific Neraium threshold validation.

Reference cycles are used only after each forward-only run to score output.
They are never passed into NeraiumEngine.update().
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.neraium_engine import NeraiumEngine  # noqa: E402
from tools.ims_bearing_runner import FeatureExtractor, IMSDataLoader  # noqa: E402
from tools.run_ims_neraium_demo import reference_verdict  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep Neraium IMS thresholds against evaluation references.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bearings", default="bearing_3,bearing_4")
    parser.add_argument("--references", default="bearing_3:2120,bearing_4:1508")
    parser.add_argument("--max-combinations", type=int, default=80)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="Use a smaller threshold grid and default to 30 combinations.")
    return parser.parse_args()


def parse_bearings(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_references(value: str) -> Dict[str, int]:
    refs: Dict[str, int] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        key, raw_cycle = item.split(":", 1)
        refs[key.strip()] = int(raw_cycle)
    return refs


def threshold_grid(*, quick: bool = False) -> Dict[str, list]:
    if quick:
        return {
            "watch_threshold": [0.45, 0.50],
            "actionable_hazard_threshold": [0.58, 0.62],
            "recovery_resistance_threshold": [0.10, 0.20],
            "instability_density_threshold": [0.35, 0.50],
            "accumulation_slope_threshold": [0.20],
            "recurrence_count_threshold": [2, 3],
            "min_actionable_cycle_bearing3": [1950, 2050],
            "min_actionable_cycle_bearing4": [1350, 1450],
        }
    return {
        "watch_threshold": [0.45, 0.50, 0.55],
        "actionable_hazard_threshold": [0.58, 0.62, 0.66],
        "recovery_resistance_threshold": [0.10, 0.20, 0.30],
        "instability_density_threshold": [0.35, 0.45, 0.55],
        "accumulation_slope_threshold": [0.20, 0.35, 0.50],
        "recurrence_count_threshold": [2, 3, 4],
        "min_actionable_cycle_bearing3": [1800, 1950, 2050],
        "min_actionable_cycle_bearing4": [1200, 1350, 1450],
    }


def config_grid(*, quick: bool = False) -> Iterable[Dict[str, float | int]]:
    grid = threshold_grid(quick=quick)
    keys = list(grid)
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def load_bearing_packets(data_dir: Path, bearing: str, max_files: int | None = None) -> List[dict]:
    discovered = IMSDataLoader.discover_timestamp_files(data_dir)
    packets: List[dict] = []
    selected_column = IMSDataLoader.bearing_column_index(bearing)
    if selected_column is None:
        raise ValueError(f"Unsupported IMS bearing selector: {bearing}")

    for source_name, files in discovered.items():
        selected = files[:max_files] if max_files else files
        for cycle, file_path in enumerate(selected, start=1):
            data = IMSDataLoader.load_timestamp_file(file_path)
            if data is None:
                continue
            selected_data = IMSDataLoader.select_bearing_column(data, bearing)
            if selected_data is None:
                continue
            features = FeatureExtractor.extract_per_channel(selected_data)
            if not features:
                continue
            packets.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "asset_id": f"IMS-{source_name}-{bearing}",
                    "bearing_id": bearing,
                    "cycle": cycle,
                    "signals": {
                        "vibration_rms": features.get("rms", 0.0),
                        "vibration_std": features.get("std", 0.0),
                        "vibration_peak": features.get("peak", 0.0),
                        "vibration_kurtosis": features.get("kurtosis", 0.0),
                        "vibration_skewness": features.get("skewness", 0.0),
                        "vibration_crest_factor": features.get("crest_factor", 0.0),
                    },
                }
            )
        break
    return packets


def first_event(events: List[dict], state: str) -> int | None:
    for event in events:
        if event["state"] == state:
            return int(event["cycle"])
    return None


def run_forward(packets: List[dict], config: dict, run_id: str) -> dict:
    engine = NeraiumEngine(config=config)
    previous_state = "STABLE"
    events: List[dict] = []
    final_cycle = None
    for packet in packets:
        isolated_packet = dict(packet)
        isolated_packet["asset_id"] = f"{packet['asset_id']}-sweep-{run_id}"
        frame = engine.update(isolated_packet)
        final_cycle = int(frame["cycle"])
        state = str(frame["state"])
        if state != previous_state and state in {"WATCH", "ACTIONABLE", "ALERT"}:
            events.append({"cycle": final_cycle, "state": state})
        previous_state = state
    return {
        "events": events,
        "final_cycle": final_cycle,
        "first_watch_cycle": first_event(events, "WATCH"),
        "first_actionable_cycle": first_event(events, "ACTIONABLE"),
    }


def score_result(first_watch: int | None, first_actionable: int | None, reference: int) -> dict:
    if first_actionable is None:
        error_pct = None
        lead = None
        verdict = "NO_ACTIONABLE"
        score = 0.50
    else:
        error_pct = abs(first_actionable - reference) / reference
        lead = reference - first_actionable
        verdict = reference_verdict(first_actionable, reference, no_event="NO_ACTIONABLE")
        score = error_pct
        if verdict == "LATE":
            score += 0.50
        if first_actionable < reference * 0.5:
            score += 0.75
        if first_watch is None or first_watch >= first_actionable:
            score += 0.25
    return {
        "first_watch_cycle": first_watch,
        "first_actionable_cycle": first_actionable,
        "actionable_error_pct_of_reference": error_pct,
        "actionable_lead_to_reference": lead,
        "actionable_verdict": verdict,
        "score": score,
        "false_early_penalty": 0.75 if first_actionable is not None and first_actionable < reference * 0.5 else 0.0,
        "no_actionable_penalty": 0.50 if first_actionable is None else 0.0,
        "late_penalty": 0.50 if verdict == "LATE" else 0.0,
        "no_watch_before_actionable_penalty": 0.25 if first_actionable is not None and (first_watch is None or first_watch >= first_actionable) else 0.0,
    }


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    bearings = parse_bearings(args.bearings)
    references = parse_references(args.references)
    if args.quick and args.max_combinations == 80:
        args.max_combinations = 30

    print("[LOAD] Precomputing IMS bearing feature packets", flush=True)
    packets_by_bearing = {
        bearing: load_bearing_packets(args.data_dir, bearing, args.max_files)
        for bearing in bearings
    }

    rows: List[dict] = []
    configs = list(itertools.islice(config_grid(quick=args.quick), args.max_combinations))
    total = len(configs)
    started = time.perf_counter()
    for index, config in enumerate(configs, start=1):
        if index > args.max_combinations:
            break
        elapsed = time.perf_counter() - started
        avg = elapsed / max(index - 1, 1)
        remaining = avg * (total - index + 1)
        print(
            f"[SWEEP] combo {index}/{total} elapsed={elapsed:.1f}s eta={remaining:.1f}s params={json.dumps(config, sort_keys=True)}",
            flush=True,
        )
        per_bearing_scores = []
        row_base = {"combo": index, **config}
        for bearing in bearings:
            result = run_forward(packets_by_bearing[bearing], config, f"{index}-{bearing}")
            scored = score_result(
                result["first_watch_cycle"],
                result["first_actionable_cycle"],
                references[bearing],
            )
            per_bearing_scores.append(scored["score"])
            for key, value in scored.items():
                row_base[f"{bearing}_{key}"] = value
        row_base["score"] = sum(per_bearing_scores) / len(per_bearing_scores)
        rows.append(row_base)
        print(
            "[RESULT] "
            f"score={row_base['score']:.4f} "
            f"b3_actionable={row_base.get('bearing_3_first_actionable_cycle')} "
            f"b4_actionable={row_base.get('bearing_4_first_actionable_cycle')}",
            flush=True,
        )

    rows.sort(key=lambda item: float(item["score"]))
    all_results_path = args.output / "all_results.csv"
    with all_results_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best = rows[0]
    best_params = {key: best[key] for key in threshold_grid(quick=args.quick).keys()}
    with (args.output / "best_params.json").open("w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=2)
    with (args.output / "best_summary.json").open("w", encoding="utf-8") as f:
        json.dump(best, f, indent=2)

    print(f"[SAVED] {all_results_path}", flush=True)
    print(f"[SAVED] {args.output / 'best_params.json'}", flush=True)
    print(f"[SAVED] {args.output / 'best_summary.json'}", flush=True)
    print("[TOP]", flush=True)
    for row in rows[: args.top_k]:
        print(json.dumps(row, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
