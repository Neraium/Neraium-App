"""Seed the Neraium cannabis grow operation demo.

Replays a deterministic multi-phase grow scenario through the Neraium API,
demonstrating structural instability detection across 8 environmental sensors:
temperature, humidity, CO2, VPD, pH, EC, PPFD, and irrigation volume.

Usage:
    python tools/seed_grow_op_demo.py
    python tools/seed_grow_op_demo.py --base-url https://your-deployment.up.railway.app
    python tools/seed_grow_op_demo.py --phase baseline_stable          # baseline only
    python tools/seed_grow_op_demo.py --phase hvac_degradation         # show drift
    python tools/seed_grow_op_demo.py --phase heat_stress_buildup      # full alert
    python tools/seed_grow_op_demo.py --phase recovery_stabilization
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_SCENARIO_PATH = Path("examples/demo/cannabis_grow_op_scenario.json")


@dataclass(frozen=True)
class ScenarioFrame:
    phase: str
    minute_offset: int
    sensor_values: dict[str, float]


def load_scenario(
    path: Path, phase_filter: str | None = None
) -> tuple[dict[str, str], list[ScenarioFrame]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    asset = raw.get("asset") if isinstance(raw.get("asset"), dict) else {}
    phases = raw.get("phases") if isinstance(raw.get("phases"), list) else []
    frames: list[ScenarioFrame] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        phase_name = str(phase.get("name") or "unlabeled")
        if phase_filter and phase_name != phase_filter:
            continue
        for frame in phase.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            sensor_values = frame.get("sensor_values")
            if not isinstance(sensor_values, dict):
                continue
            frames.append(
                ScenarioFrame(
                    phase=phase_name,
                    minute_offset=int(frame.get("minute_offset", 0)),
                    sensor_values={k: float(v) for k, v in sensor_values.items()},
                )
            )
    return {
        "site_id": str(asset.get("site_id") or "grow-op-facility-01"),
        "asset_id": str(asset.get("asset_id") or "canopy-zone-A"),
    }, frames


def request_json(
    method: str,
    base_url: str,
    path: str,
    params: dict[str, str],
    payload: dict[str, Any] | None = None,
    retries: int = 4,
) -> dict[str, Any]:
    query = urlencode(params)
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    for attempt in range(retries + 1):
        req = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (502, 503, 504) and attempt < retries:
                wait = 2 ** attempt
                print(f"    [retry {attempt + 1}/{retries}] HTTP {exc.code}, waiting {wait}s…")
                time.sleep(wait)
                continue
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
                print(f"    [HTTP {exc.code}] {url}")
                print(f"    {err_body[:500]}")
            except Exception:
                pass
            raise


def clip_text(text: str, limit: int = 220) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


PHASE_LABELS = {
    "baseline_stable": "Stable Veg (baseline)",
    "night_cycle_recovery": "Night Cycle Recovery",
    "hvac_degradation": "Drift Onset (HVAC degrading)",
    "heat_stress_buildup": "Heat Stress Buildup",
    "critical_alert": "Critical Alert",
    "operator_intervention": "Operator Intervention",
    "recovery_stabilization": "Recovery & Stabilization",
}

SENSOR_LABELS = {
    "temperature_f": ("Canopy Temp", "°F"),
    "humidity_rh": ("Humidity", "%"),
    "co2_ppm": ("CO₂", "ppm"),
    "vpd_kpa": ("VPD", "kPa"),
    "ph": ("pH", ""),
    "ec_ms": ("EC", "mS/cm"),
    "ppfd_umol": ("PPFD", "µmol"),
    "irrigation_ml": ("Irrigation", "mL"),
}


def ensure_run(base_url: str, customer_id: str) -> str:
    """Return the active run_id for the customer, creating one if none exists."""
    active = request_json("GET", base_url, "/runs/active", {"customer_id": customer_id})
    if active.get("run") and active["run"].get("run_id"):
        return str(active["run"]["run_id"])
    created = request_json(
        "POST",
        base_url,
        "/runs",
        {"customer_id": customer_id},
        {"name": "Cannabis Grow Op Demo", "config": {"source": "seed-script"}, "activate": True},
    )
    return str(created["run"]["run_id"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the Neraium cannabis grow operation demo."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customer-id", default="grow-op-demo")
    parser.add_argument(
        "--phase",
        default=None,
        choices=[
            "baseline_stable",
            "night_cycle_recovery",
            "hvac_degradation",
            "heat_stress_buildup",
            "critical_alert",
            "operator_intervention",
            "recovery_stabilization",
        ],
        help="Replay only a specific phase (default: all phases)",
    )
    parser.add_argument(
        "--scenario",
        default=str(DEFAULT_SCENARIO_PATH),
        help="Path to scenario JSON",
    )
    parser.add_argument(
        "--output-json",
        default="outputs/grow_op_demo_result.json",
        help="Path to write result bundle",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print each frame as it is seeded"
    )
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")

    asset_meta, scenario_frames = load_scenario(scenario_path, phase_filter=args.phase)
    if not scenario_frames:
        raise ValueError("No frames loaded — check --phase filter or scenario path.")

    print("\nNeraium Cannabis Grow Op Demo")
    print(f"{'='*50}")
    print(f"  Endpoint : {args.base_url}")
    run_id = ensure_run(args.base_url, args.customer_id)

    params = {
        "customer_id": args.customer_id,
        "run_id": run_id,
    }

    print(f"  Site     : {asset_meta['site_id']}")
    print(f"  Zone     : {asset_meta['asset_id']}")
    print(f"  Run      : {run_id}")
    print(f"  Frames   : {len(scenario_frames)}")
    print(f"  Phase    : {args.phase or 'all'}")
    print()

    base_time = datetime.now(timezone.utc) - timedelta(minutes=scenario_frames[-1].minute_offset + 5)
    cycle_summaries: list[dict[str, Any]] = []
    current_phase = None

    for i, frame in enumerate(scenario_frames):
        if frame.phase != current_phase:
            current_phase = frame.phase
            label = PHASE_LABELS.get(frame.phase, frame.phase)
            print(f"  Phase: {label}")

        timestamp = (base_time + timedelta(minutes=frame.minute_offset)).isoformat()
        payload = {
            "timestamp": timestamp,
            "site_id": asset_meta["site_id"],
            "asset_id": asset_meta["asset_id"],
            "sensor_values": frame.sensor_values,
        }

        result = request_json("POST", args.base_url, "/ingest", params, payload)

        latest = result.get("latest") or result
        risk = latest.get("risk_assessment") or {}
        recommendation = latest.get("operational_recommendation") or {}
        instability = risk.get("composite_instability", 0.0)
        alert = recommendation.get("recommended_action", "")

        cycle_summaries.append(
            {
                "frame": i,
                "phase": frame.phase,
                "minute_offset": frame.minute_offset,
                "instability": instability,
                "alert": alert,
                "sensors": frame.sensor_values,
            }
        )

        if args.verbose or (i % 10 == 0):
            temp = frame.sensor_values.get("temperature_f", 0)
            rh = frame.sensor_values.get("humidity_rh", 0)
            vpd = frame.sensor_values.get("vpd_kpa", 0)
            co2 = frame.sensor_values.get("co2_ppm", 0)
            print(
                f"    [{i+1:>3}/{len(scenario_frames)}] "
                f"T={temp:.1f}°F  RH={rh:.1f}%  VPD={vpd:.2f}kPa  "
                f"CO2={co2:.0f}ppm  instability={instability:.3f}"
            )

    print()
    print("Fetching final state and reports...")

    state = request_json("GET", args.base_url, "/state", params)
    current = state.get("state") or {}

    explain = request_json(
        "POST",
        args.base_url,
        "/assistant/explain",
        {},
        {"customer_id": args.customer_id, "run_id": run_id, "mode": "why_recommended", "history_limit": 20},
    )
    client_report = request_json(
        "POST",
        args.base_url,
        "/assistant/report",
        {},
        {"customer_id": args.customer_id, "run_id": run_id, "mode": "client_report", "history_limit": 20},
    )
    technician_summary = request_json(
        "POST",
        args.base_url,
        "/assistant/report",
        {},
        {"customer_id": args.customer_id, "run_id": run_id, "mode": "technician_summary", "history_limit": 20},
    )

    memory = current.get("memory_recall") or {}
    novelty = memory.get("novelty") or {}
    nearest = memory.get("nearest_match") or {}

    summary = {
        "scope": params,
        "scenario": args.scenario,
        "phase_filter": args.phase,
        "frames_seeded": len(scenario_frames),
        "cycle_summaries": cycle_summaries,
        "latest_state": {
            "timestamp": current.get("timestamp"),
            "cycle": current.get("cycle"),
            "risk_assessment": current.get("risk_assessment"),
            "operational_recommendation": current.get("operational_recommendation"),
            "explanation_text": current.get("explanation_text"),
            "events": current.get("events"),
        },
        "outputs": {
            "recommendation": (current.get("operational_recommendation") or {}).get("recommended_action"),
            "explanation": explain.get("text"),
            "memory_recall": {
                "is_novel": novelty.get("is_novel"),
                "reason": novelty.get("reason"),
                "nearest_match_found": nearest.get("found"),
                "nearest_match_similarity": nearest.get("similarity"),
            },
            "client_report": client_report.get("report_text"),
            "technician_summary": technician_summary.get("report_text"),
        },
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nRecommendation")
    print(f"  {summary['outputs']['recommendation']}")
    print("\nExplanation")
    print(f"  {clip_text(summary['outputs']['explanation'])}")
    print("\nMemory recall")
    print(
        f"  is_novel={summary['outputs']['memory_recall']['is_novel']}  "
        f"nearest_found={summary['outputs']['memory_recall']['nearest_match_found']}  "
        f"similarity={summary['outputs']['memory_recall']['nearest_match_similarity']}"
    )
    print("\nClient report excerpt")
    print(f"  {clip_text(summary['outputs']['client_report'])}")
    print("\nTechnician summary excerpt")
    print(f"  {clip_text(summary['outputs']['technician_summary'])}")
    print(f"\nOutput bundle written to {output_path}")


if __name__ == "__main__":
    main()
