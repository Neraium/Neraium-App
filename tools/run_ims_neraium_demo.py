#!/usr/bin/env python3
"""Run IMS bearing data through the canonical NeraiumEngine."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.neraium_engine import NeraiumEngine  # noqa: E402
from backend.services.operator_explanation_context import attach_validation_context  # noqa: E402
from tools.ims_bearing_runner import IMSDataLoader, FeatureExtractor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream IMS bearing timestamp files through the canonical Neraium decision engine.",
        epilog=(
            "Examples:\n"
            "  python -m tools.run_ims_neraium_demo --data-dir /c/Users/Owner/Documents/IMS_1st_test "
            "--output results/ims_1st_bearing3_eval --bearing bearing_3 --show-every 100 "
            "--reference-cycle 2120 --reference-label known_degradation_onset_T1B3\n"
            "  python -m tools.run_ims_neraium_demo --data-dir /c/Users/Owner/Documents/IMS_1st_test "
            "--output results/ims_1st_bearing4_eval --bearing bearing_4 --show-every 100 "
            "--reference-cycle 1508 --reference-label known_degradation_onset_T1B4"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data-dir", type=Path, required=True, help="Path to extracted IMS data directory")
    parser.add_argument("--output", type=Path, default=Path("results/ims_neraium_demo"))
    parser.add_argument("--bearing", default=None, help="Optional bearing folder/name to run")
    parser.add_argument("--max-files", type=int, default=None, help="Optional limit per bearing")
    parser.add_argument("--show-every", type=int, default=25)
    parser.add_argument("--interval", type=float, default=0.0)
    parser.add_argument("--stop-at-actionable", action="store_true", help="Stop when the canonical hazard state reaches ALERT.")
    parser.add_argument("--debug-discovery", action="store_true")
    parser.add_argument("--reference-cycle", type=int, default=None, help="Known degradation onset cycle for evaluation only.")
    parser.add_argument("--reference-label", default="known_degradation_onset", help="Label for the evaluation reference cycle.")
    return parser.parse_args()


def packet_stream(
    bearing_name: str,
    files: List[Path],
    max_files: int | None = None,
    *,
    source_name: str | None = None,
    selected_bearing: str | None = None,
) -> Iterator[Dict[str, object]]:
    selected = files[:max_files] if max_files else files
    selected_column = IMSDataLoader.bearing_column_index(selected_bearing)
    asset_name = f"IMS-{source_name}-{selected_bearing}" if selected_bearing and source_name else f"IMS-{bearing_name}"
    for cycle, file_path in enumerate(selected, start=1):
        data = IMSDataLoader.load_timestamp_file(file_path)
        if data is None:
            continue
        if selected_bearing:
            selected_data = IMSDataLoader.select_bearing_column(data, selected_bearing)
            if selected_data is None:
                column_count = data.shape[1] if getattr(data, "ndim", 1) > 1 else 1
                print(
                    f"[WARNING] Skipping {file_path.name}: selected={selected_bearing} "
                    f"column={selected_column} but file has {column_count} column(s)."
                )
                continue
            data = selected_data
        features = FeatureExtractor.extract_per_channel(data)
        if not features:
            continue
        yield {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_id": asset_name,
            "bearing_id": selected_bearing or bearing_name,
            "cycle": cycle,
            "signals": {
                "vibration_rms": features.get("rms", 0.0),
                "vibration_std": features.get("std", 0.0),
                "vibration_peak": features.get("peak", 0.0),
                "vibration_kurtosis": features.get("kurtosis", 0.0),
                "vibration_skewness": features.get("skewness", 0.0),
                "vibration_crest_factor": features.get("crest_factor", 0.0),
            },
            "source_file": file_path.name,
        }


def state_event(previous: str, current: str) -> str | None:
    if previous == current:
        return None
    return {
        "WATCH": "HAZARD_WATCH_CONFIRMED",
        "ACTIONABLE": "HAZARD_ACTIONABLE_CONFIRMED",
        "ALERT": "HAZARD_ALERT_CONFIRMED",
    }.get(current)


def print_frame(frame: Dict[str, object], event: str | None) -> None:
    drivers = frame["drivers"]
    audit = frame["audit"]

    def as_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    hazard_score = as_float(frame.get("hazard_score", 0.0))
    hazard_rate = as_float(frame.get("hazard_rate", 0.0))
    hazard_acceleration = as_float(frame.get("hazard_acceleration", 0.0))

    print(f"[INPUT] cycle={frame['cycle']} asset={frame['asset_id']}")
    if event:
        print(f"[EVENT] {event}")
    print(
        "[HAZARD] "
        f"score={hazard_score:.3f} "
        f"rate={hazard_rate:.4f} "
        f"accel={hazard_acceleration:.4f} "
        f"state={frame['state']} "
        f"confidence={frame['confidence']}"
    )
    print(
        "[DRIVERS] "
        f"drift={drivers['structural_drift']:.3f} "
        f"trajectory={drivers['trajectory_strength']:.3f} "
        f"relational={drivers['relational_instability']:.3f}"
    )
    print(f"[TIME] time_to_threshold={frame['time_to_threshold']}")
    print(f"[AUDIT] future_data_used={str(audit['future_data_used']).lower()} window={audit['data_window_used']}")
    print()


def compact_frame(frame: Dict[str, object]) -> Dict[str, object]:
    return {
        "asset_id": frame["asset_id"],
        "cycle": frame["cycle"],
        "state": frame["state"],
        "hazard_score": frame["hazard_score"],
        "hazard_rate": frame["hazard_rate"],
        "time_to_threshold": frame["time_to_threshold"],
        "confidence": frame["confidence"],
        "drivers": frame["drivers"],
        "audit": frame["audit"],
        "operator_explanation": frame.get("operator_explanation"),
    }


def first_event_cycle(events: List[Dict[str, object]], event_name: str) -> int | None:
    for event in events:
        if event.get("event") == event_name:
            return int(event["cycle"])
    return None


def evaluation_summary(
    args: argparse.Namespace,
    events: List[Dict[str, object]],
    *,
    final_cycle: int | None,
    last_state: str,
    state_counts: Dict[str, int],
    actionable_reversion_count: int,
    stable_after_actionable: bool,
) -> Dict[str, object]:
    reference_cycle = args.reference_cycle
    first_watch_cycle = first_event_cycle(events, "HAZARD_WATCH_CONFIRMED")
    first_actionable_cycle = first_event_cycle(events, "HAZARD_ACTIONABLE_CONFIRMED")
    first_alert_cycle = first_event_cycle(events, "HAZARD_ALERT_CONFIRMED")
    alert_lead = reference_cycle - first_alert_cycle if reference_cycle and first_alert_cycle else None
    watch_lead = reference_cycle - first_watch_cycle if reference_cycle and first_watch_cycle else None
    actionable_lead = reference_cycle - first_actionable_cycle if reference_cycle and first_actionable_cycle else None
    alert_error_pct = (
        abs(first_alert_cycle - reference_cycle) / reference_cycle
        if reference_cycle and first_alert_cycle
        else None
    )
    actionable_error_pct = (
        abs(first_actionable_cycle - reference_cycle) / reference_cycle
        if reference_cycle and first_actionable_cycle
        else None
    )

    verdict = reference_verdict(first_alert_cycle, reference_cycle, no_event="NO_ALERT")
    actionable_verdict = reference_verdict(first_actionable_cycle, reference_cycle, no_event="NO_ACTIONABLE")
    actionable_duration_to_end = (
        final_cycle - first_actionable_cycle
        if final_cycle is not None and first_actionable_cycle is not None
        else None
    )
    actionable_persisted_to_end = (
        first_actionable_cycle is not None
        and last_state in {"ACTIONABLE", "ALERT"}
        and not stable_after_actionable
    )

    if reference_cycle and first_alert_cycle and first_alert_cycle < reference_cycle * 0.25:
        print("[WARNING] ALERT fired extremely early versus reference. Current thresholds likely too sensitive.")

    return {
        "reference_cycle": reference_cycle,
        "reference_label": args.reference_label,
        "first_watch_cycle": first_watch_cycle,
        "first_actionable_cycle": first_actionable_cycle,
        "first_alert_cycle": first_alert_cycle,
        "alert_lead_to_reference": alert_lead,
        "watch_lead_to_reference": watch_lead,
        "actionable_lead_to_reference": actionable_lead,
        "alert_error_pct_of_reference": alert_error_pct,
        "actionable_error_pct_of_reference": actionable_error_pct,
        "actionable_verdict": actionable_verdict,
        "actionable_persisted_to_end": actionable_persisted_to_end,
        "actionable_reversion_count": actionable_reversion_count,
        "actionable_duration_to_end": actionable_duration_to_end,
        "state_counts": dict(state_counts),
        "last_state": last_state,
        "final_state": last_state,
        "verdict": verdict,
        "reference_used_for_inference": False,
    }


def reference_verdict(event_cycle: int | None, reference_cycle: int | None, *, no_event: str) -> str:
    if event_cycle is None:
        return no_event
    if reference_cycle is None:
        return "NO_REFERENCE"
    if event_cycle < reference_cycle * 0.5:
        return "EARLY_FALSE_POSITIVE_RISK"
    if abs(event_cycle - reference_cycle) <= reference_cycle * 0.1:
        return "NEAR_REFERENCE"
    if reference_cycle * 0.5 <= event_cycle < reference_cycle * 0.9:
        return "EARLY_BUT_PLAUSIBLE"
    if event_cycle > reference_cycle * 1.1:
        return "LATE"
    return "NEAR_REFERENCE"


def run_bearing(
    args: argparse.Namespace,
    bearing_name: str,
    files: List[Path],
    *,
    source_name: str | None = None,
    selected_bearing: str | None = None,
) -> Dict[str, object]:
    engine = NeraiumEngine()
    previous_state = "STABLE"
    frames_written = 0
    events = []
    state_counts: Dict[str, int] = {}
    actionable_reversion_count = 0
    actionable_seen = False
    stable_after_actionable = False
    last_state = "STABLE"
    final_cycle = None
    args.output.mkdir(parents=True, exist_ok=True)
    out_path = args.output / f"{bearing_name}_neraium_frames.jsonl"

    print("=" * 80)
    print(f"IMS -> NeraiumEngine: {bearing_name} ({len(files)} files)")
    if selected_bearing:
        print(f"[BEARING] selected={selected_bearing} column={IMSDataLoader.bearing_column_index(selected_bearing)}")
    print("Forward-only mode: one timestamp packet updates one canonical outcome frame.")
    print("=" * 80)

    with out_path.open("w", encoding="utf-8") as f:
        for packet in packet_stream(
            bearing_name,
            files,
            args.max_files,
            source_name=source_name,
            selected_bearing=selected_bearing,
        ):
            frame = engine.update(packet)
            attach_validation_context(
                frame,
                known_event_cycle=args.reference_cycle,
                event_label=args.reference_label,
            )
            current_state = str(frame["state"])
            final_cycle = int(frame["cycle"])
            state_counts[current_state] = state_counts.get(current_state, 0) + 1
            if previous_state == "ACTIONABLE" and current_state in {"WATCH", "STABLE"}:
                actionable_reversion_count += 1
            if current_state == "ACTIONABLE":
                actionable_seen = True
            if actionable_seen and current_state == "STABLE":
                stable_after_actionable = True

            event = state_event(previous_state, current_state)
            if event:
                events.append({"cycle": frame["cycle"], "event": event, "state": frame["state"]})

            should_show = (
                event is not None
                or int(frame["cycle"]) == 1
                or int(frame["cycle"]) % max(args.show_every, 1) == 0
            )
            if should_show:
                if frame["cycle"] == 1:
                    for k in ["hazard_score", "hazard_rate", "hazard_acceleration", "structural_drift_score", "relational_stability_score"]:
                        print("[DEBUG TYPE]", k, repr(frame.get(k)), type(frame.get(k)))
                print_frame(frame, event)

            f.write(json.dumps(compact_frame(frame)) + "\n")
            frames_written += 1
            previous_state = current_state
            last_state = current_state
            if args.stop_at_actionable and frame["state"] in {"ACTIONABLE", "ALERT"}:
                print(f"[STOP] Hazard {frame['state'].lower()} reached after confirmation.")
                break
            time.sleep(max(args.interval, 0.0))

    print(f"[SAVED] {out_path}")
    evaluation = evaluation_summary(
        args,
        events,
        final_cycle=final_cycle,
        last_state=last_state,
        state_counts=state_counts,
        actionable_reversion_count=actionable_reversion_count,
        stable_after_actionable=stable_after_actionable,
    )
    return {
        "bearing": bearing_name,
        "frames_written": frames_written,
        "events": events,
        **evaluation,
        "output": str(out_path),
    }


def main() -> int:
    args = parse_args()
    bearings = IMSDataLoader.discover_timestamp_files(args.data_dir, debug=args.debug_discovery)
    selected_column = IMSDataLoader.bearing_column_index(args.bearing)
    if args.bearing and selected_column is None:
        bearings = {name: files for name, files in bearings.items() if name == args.bearing}
    if not bearings:
        print(f"No IMS bearing files found in {args.data_dir}", file=sys.stderr)
        return 1

    summaries = []
    if args.bearing and selected_column is not None:
        for source_name, files in bearings.items():
            summaries.append(
                run_bearing(
                    args,
                    args.bearing,
                    files,
                    source_name=source_name,
                    selected_bearing=args.bearing,
                )
            )
    else:
        for bearing_name, files in bearings.items():
            summaries.append(run_bearing(args, bearing_name, files))

    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "reference_cycle": args.reference_cycle,
                "reference_label": args.reference_label,
                "reference_used_for_inference": False,
                "bearings": summaries,
            },
            f,
            indent=2,
        )
    print(f"[SUMMARY] {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
