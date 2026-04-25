"""Demo routes — runs the canonical fixture, optionally appends, and seeds a fleet."""
import asyncio
import json
import uuid
import random
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException

from services import engine_service as es
from routers.models import DemoRunRequest, FleetDemoRequest

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT_DIR / "demo_fixtures" / "cannabis_grow_op_scenario.json"

router = APIRouter()

_demo_task = None
_demo_progress = {"running": False, "processed": 0, "total": 0, "error": None}


def _load_fixture_frames():
    if not FIXTURE_PATH.exists():
        raise HTTPException(status_code=500, detail="Demo fixture not found")
    with open(FIXTURE_PATH) as f:
        fixture = json.load(f)
    asset = fixture.get("asset", {})
    asset_id = asset.get("asset_id", "demo-facility")
    site_id = asset.get("site_id", "demo-site")
    frames: List[Dict[str, Any]] = []
    base_ts = 1704067200.0
    for phase in fixture.get("phases", []):
        for frame in phase.get("frames", []):
            offset = float(frame.get("minute_offset", 0)) * 60
            frames.append({
                "timestamp": base_ts + offset,
                "sensor_values": frame.get("sensor_values", {}),
                "asset_id": asset_id,
                "site_id": site_id,
            })
    return asset, frames


@router.post("/demo/run")
async def run_demo(req: DemoRunRequest):
    global _demo_task

    asset, all_frames = _load_fixture_frames()
    asset_id = asset.get("asset_id", "demo-facility")
    site_id = asset.get("site_id", "demo-site")

    existing_count = len(es.get_results(asset_id))
    append_mode = bool(req.append) and existing_count > 0

    if not append_mode:
        es.reset_all()
        es.set_run_id(str(uuid.uuid4())[:8])
        existing_count = 0

    _demo_progress.update({"running": True, "processed": 0, "total": 0, "error": None})

    async def _bg():
        try:
            es.asset_meta()[asset_id] = {
                "description": asset.get("description"),
                "sensors": asset.get("sensors"),
                "site_id": site_id,
            }
            start_idx = existing_count
            end_idx = min(start_idx + req.num_frames, len(all_frames))
            total = max(0, end_idx - start_idx)
            _demo_progress["total"] = total

            def _process_all():
                for fd in all_frames[start_idx:end_idx]:
                    es.process_frame(asset_id, {
                        "timestamp": fd["timestamp"], "asset_id": asset_id, "site_id": site_id,
                        "sensor_values": fd["sensor_values"],
                    })
                    _demo_progress["processed"] += 1

            await asyncio.get_event_loop().run_in_executor(None, _process_all)
            _demo_progress["running"] = False
        except Exception as e:
            _demo_progress["error"] = str(e)
            _demo_progress["running"] = False

    if _demo_task and not _demo_task.done():
        _demo_task.cancel()
    _demo_task = asyncio.create_task(_bg())
    return {"status": "started", "run_id": es.get_run_id(), "append": append_mode, "start_index": existing_count}


@router.post("/fleet/run-demo")
async def run_fleet_demo(req: FleetDemoRequest):
    """Seed N synthetic assets so the FLEET tab has live data."""
    global _demo_task

    asset, all_frames = _load_fixture_frames()
    site_id = asset.get("site_id", "demo-site")

    es.reset_all()
    es.set_run_id(str(uuid.uuid4())[:8])
    _demo_progress.update({"running": True, "processed": 0, "total": 0, "error": None})

    n = max(1, min(req.asset_count, 6))
    base_names = ["grow-room-A", "grow-room-B", "grow-room-C", "grow-room-D", "grow-room-E", "grow-room-F"][:n]
    slice_specs = [
        (0, 25),
        (0, 75),
        (0, 200),
        (0, 320),
        (0, 120),
        (0, 260),
    ][:n]

    profiles = []
    for i, name in enumerate(base_names):
        start, end = slice_specs[i]
        end = min(end, len(all_frames), start + req.num_frames * 4)
        noise = 0.0 if i == 0 else 0.015 + i * 0.018
        profiles.append({"asset_id": name, "start": start, "end": end, "noise": noise, "rng_seed": 42 + i})

    _demo_progress["total"] = sum(p["end"] - p["start"] for p in profiles)

    async def _bg():
        try:
            def _process_all():
                for prof in profiles:
                    aid = prof["asset_id"]
                    es.asset_meta()[aid] = {
                        "description": f"{aid} (synthetic)",
                        "sensors": asset.get("sensors"),
                        "site_id": site_id,
                    }
                    local_rng = random.Random(prof["rng_seed"])
                    for fd in all_frames[prof["start"]:prof["end"]]:
                        sv = dict(fd["sensor_values"])
                        if prof["noise"] > 0:
                            sv = {
                                k: v * (1.0 + local_rng.uniform(-prof["noise"], prof["noise"]))
                                for k, v in sv.items()
                            }
                        es.process_frame(aid, {
                            "timestamp": fd["timestamp"], "asset_id": aid, "site_id": site_id,
                            "sensor_values": sv,
                        })
                        _demo_progress["processed"] += 1

            await asyncio.get_event_loop().run_in_executor(None, _process_all)
            _demo_progress["running"] = False
        except Exception as e:
            _demo_progress["error"] = str(e)
            _demo_progress["running"] = False

    if _demo_task and not _demo_task.done():
        _demo_task.cancel()
    _demo_task = asyncio.create_task(_bg())
    return {"status": "started", "run_id": es.get_run_id(), "assets": [p["asset_id"] for p in profiles]}


@router.get("/demo/status")
async def demo_status():
    fixture_total = 0
    try:
        if FIXTURE_PATH.exists():
            with open(FIXTURE_PATH) as f:
                fx = json.load(f)
            for phase in fx.get("phases", []):
                fixture_total += len(phase.get("frames", []))
    except Exception:
        fixture_total = 0
    processed_total = sum(len(rs) for rs in es.all_results().values())
    return {
        "running": _demo_progress["running"],
        "processed": _demo_progress["processed"],
        "total": _demo_progress["total"],
        "error": _demo_progress["error"],
        "run_id": es.get_run_id(),
        "frames_in_engine": processed_total,
        "fixture_total_frames": fixture_total,
        "frames_remaining_in_fixture": max(0, fixture_total - processed_total),
    }
