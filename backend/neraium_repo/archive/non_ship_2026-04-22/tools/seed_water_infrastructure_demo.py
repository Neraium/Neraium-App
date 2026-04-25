from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ScenarioFrame:
    phase: str
    minute_offset: int
    sensor_values: dict[str, float]


DEFAULT_SCENARIO_PATH = Path("examples/demo/water_infrastructure_scenario.json")


def load_scenario(path: Path) -> tuple[dict[str, str], list[ScenarioFrame]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    asset = raw.get("asset") if isinstance(raw.get("asset"), dict) else {}
    phases = raw.get("phases") if isinstance(raw.get("phases"), list) else []
    frames: list[ScenarioFrame] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        phase_name = str(phase.get("name") or "unlabeled_phase")
        for frame in phase.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            sensor_values = frame.get("sensor_values")
            if not isinstance(sensor_values, dict):
                continue
            minute_offset = int(frame.get("minute_offset", 0))
            frames.append(
                ScenarioFrame(
                    phase=phase_name,
                    minute_offset=minute_offset,
                    sensor_values={k: float(v) for k, v in sensor_values.items()},
                )
            )
    return {
        "site_id": str(asset.get("site_id") or "site-water-west-01"),
        "asset_id": str(asset.get("asset_id") or "pump-17A"),
    }, frames


def request_json(method: str, base_url: str, path: str, params: dict[str, str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urlencode(params)
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, method=method, headers=headers)
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def clip_text(text: str, limit: int = 220) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a deterministic water-infrastructure pump degradation demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customer-id", default="contractor-water-demo")
    parser.add_argument("--run-id", default="run-water-pump-demo-v1")
    parser.add_argument(
        "--start-time",
        default="2026-01-15T09:00:00+00:00",
        help="ISO-8601 timestamp for first frame. Default is fixed for reproducible playback.",
    )
    parser.add_argument(
        "--output-json",
        default="reports/water_demo_outputs.json",
        help="Path to write a JSON summary with generated demo outputs.",
    )
    parser.add_argument(
        "--scenario-file",
        default=str(DEFAULT_SCENARIO_PATH),
        help="JSON scenario definition (phase + frame sequence).",
    )
    args = parser.parse_args()

    asset, scenario_frames = load_scenario(Path(args.scenario_file))
    if not scenario_frames:
        raise ValueError(f"No scenario frames found in {args.scenario_file}")

    params = {"customer_id": args.customer_id, "run_id": args.run_id}
    start = datetime.fromisoformat(args.start_time)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    cycle_summaries: list[dict[str, Any]] = []
    print(f"Seeding deterministic water demo into run_id={args.run_id} customer_id={args.customer_id}")
    for frame in scenario_frames:
        payload = {
            "timestamp": (start + timedelta(minutes=frame.minute_offset)).isoformat(),
            "site_id": asset["site_id"],
            "asset_id": asset["asset_id"],
            "customer_id": args.customer_id,
            "sensor_values": frame.sensor_values,
        }
        out = request_json("POST", args.base_url, "/ingest/frame", params, payload)
        risk = (out.get("risk_assessment") or {}).get("risk_level")
        rec = (out.get("operational_recommendation") or {}).get("recommended_action")
        events = out.get("events") or []
        entry = {
            "phase": frame.phase,
            "cycle": out.get("cycle"),
            "risk": risk,
            "recommendation": rec,
            "events": events,
        }
        cycle_summaries.append(entry)
        print(
            f"  phase={frame.phase:<14} cycle={entry['cycle']} risk={risk} "
            f"recommendation={rec or '-'} events={','.join(events) if events else '-'}"
        )

    state = request_json("GET", args.base_url, "/state", params)
    current = state.get("state") or {}

    explain = request_json(
        "POST",
        args.base_url,
        "/assistant/explain",
        {},
        {"customer_id": args.customer_id, "run_id": args.run_id, "mode": "why_recommended", "history_limit": 20},
    )
    handoff = request_json(
        "POST",
        args.base_url,
        "/assistant/handoff",
        {},
        {"customer_id": args.customer_id, "run_id": args.run_id, "history_limit": 20},
    )
    client_report = request_json(
        "POST",
        args.base_url,
        "/assistant/report",
        {},
        {"customer_id": args.customer_id, "run_id": args.run_id, "mode": "client_report", "history_limit": 20},
    )
    technician_summary = request_json(
        "POST",
        args.base_url,
        "/assistant/report",
        {},
        {"customer_id": args.customer_id, "run_id": args.run_id, "mode": "technician_summary", "history_limit": 20},
    )
    handoff_note = request_json(
        "POST",
        args.base_url,
        "/assistant/report",
        {},
        {"customer_id": args.customer_id, "run_id": args.run_id, "mode": "handoff_note", "history_limit": 20},
    )

    memory = current.get("memory_recall") or {}
    novelty = memory.get("novelty") or {}
    nearest = memory.get("nearest_match") or {}

    summary = {
        "scope": params,
        "frames_seeded": len(scenario_frames),
        "phases": [frame.phase for frame in scenario_frames],
        "cycle_summaries": cycle_summaries,
        "latest_state": {
            "timestamp": current.get("timestamp"),
            "cycle": current.get("cycle"),
            "risk_assessment": current.get("risk_assessment"),
            "operational_recommendation": current.get("operational_recommendation"),
            "explanation_text": current.get("explanation_text"),
            "events": current.get("events"),
            "memory_recall": current.get("memory_recall"),
        },
        "outputs": {
            "recommendation": (current.get("operational_recommendation") or {}).get("recommended_action"),
            "explanation": explain.get("text"),
            "memory_recall": {
                "is_novel": novelty.get("is_novel"),
                "reason": novelty.get("reason"),
                "nearest_match_found": nearest.get("found"),
                "nearest_match_summary": nearest.get("summary"),
                "nearest_match_similarity": nearest.get("similarity"),
            },
            "client_report": client_report.get("report_text"),
            "technician_summary": technician_summary.get("report_text"),
            "handoff_note": handoff_note.get("report_text"),
            "assistant_handoff": handoff.get("text"),
        },
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nLatest recommendation")
    print(f"  {summary['outputs']['recommendation']}")
    print("Explanation excerpt")
    print(f"  {clip_text(summary['outputs']['explanation'])}")
    print("Memory recall")
    print(
        "  "
        f"is_novel={summary['outputs']['memory_recall']['is_novel']} "
        f"nearest_match_found={summary['outputs']['memory_recall']['nearest_match_found']} "
        f"similarity={summary['outputs']['memory_recall']['nearest_match_similarity']}"
    )
    print("Client report excerpt")
    print(f"  {clip_text(summary['outputs']['client_report'])}")
    print("Technician summary excerpt")
    print(f"  {clip_text(summary['outputs']['technician_summary'])}")
    print("Handoff note excerpt")
    print(f"  {clip_text(summary['outputs']['handoff_note'])}")
    print(f"\nWrote reproducible output bundle to {output_path}")


if __name__ == "__main__":
    main()
