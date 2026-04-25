"""WebSocket streaming for live demo playback."""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import engine_service as es
from services.builders import build_system_state, build_metrics
from services.serialise import sf

logger = logging.getLogger(__name__)
router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT_DIR / "demo_fixtures" / "cannabis_grow_op_scenario.json"

PLAYBACK_SPEEDS = {"slow": 0.8, "normal": 0.3, "fast": 0.05}


@router.websocket("/api/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    pb = {"paused": False, "stopped": False, "speed": "slow"}

    async def _stream_demo(num: int):
        with open(FIXTURE_PATH) as f:
            fixture = json.load(f)
        asset = fixture.get("asset", {})
        asset_id = asset.get("asset_id", "demo-facility")
        site_id = asset.get("site_id", "demo-site")
        es.asset_meta()[asset_id] = {"description": asset.get("description"), "sensors": asset.get("sensors"), "site_id": site_id}
        all_frames = []
        base_ts = 1704067200.0
        for phase in fixture.get("phases", []):
            for frame in phase.get("frames", []):
                all_frames.append({
                    "timestamp": base_ts + float(frame.get("minute_offset", 0)) * 60,
                    "sensor_values": frame.get("sensor_values", {}),
                    "asset_id": asset_id, "site_id": site_id,
                })
        total = min(num, len(all_frames))
        await ws.send_json({"type": "stream_start", "total_frames": total, "run_id": es.get_run_id(), "speed": pb["speed"], "asset_id": asset_id})
        for i, fd in enumerate(all_frames[:total]):
            if pb["stopped"]:
                break
            while pb["paused"] and not pb["stopped"]:
                await asyncio.sleep(0.1)
            if pb["stopped"]:
                break
            try:
                raw = es.process_frame(asset_id, {"timestamp": fd["timestamp"], "asset_id": asset_id, "site_id": site_id, "sensor_values": fd["sensor_values"]})
                await ws.send_json({
                    "type": "frame_result",
                    "frame_index": i, "total_frames": total, "asset_id": asset_id,
                    "state": sf(build_system_state(raw)),
                    "metrics": sf(build_metrics(raw)),
                })
            except Exception as e:
                await ws.send_json({"type": "frame_error", "frame_index": i, "error": str(e)})
            await asyncio.sleep(PLAYBACK_SPEEDS.get(pb["speed"], 0.8))
        await ws.send_json({"type": "stream_complete", "total_processed": len(es.get_results(asset_id)), "run_id": es.get_run_id()})

    task: Optional[asyncio.Task] = None
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            action = msg.get("action")
            if action == "start_demo":
                if task and not task.done():
                    pb["stopped"] = True
                    await asyncio.sleep(0.05)
                    task.cancel()
                es.reset_all()
                es.set_run_id(str(uuid.uuid4())[:8])
                pb.update({"paused": False, "stopped": False, "speed": msg.get("speed", "slow")})
                task = asyncio.create_task(_stream_demo(msg.get("num_frames", 25)))
            elif action == "set_speed":
                s = msg.get("speed", "slow")
                if s in PLAYBACK_SPEEDS:
                    pb["speed"] = s
                    await ws.send_json({"type": "speed_changed", "speed": s})
            elif action == "pause":
                pb["paused"] = True
                await ws.send_json({"type": "paused"})
            elif action == "resume":
                pb["paused"] = False
                await ws.send_json({"type": "resumed"})
            elif action == "stop":
                pb["stopped"] = True
                if task and not task.done():
                    task.cancel()
                await ws.send_json({"type": "stopped"})
            elif action == "ping":
                await ws.send_json({"type": "pong"})
            else:
                await ws.send_json({"type": "error", "message": f"Unknown: {action}"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}", exc_info=True)
    finally:
        if task and not task.done():
            pb["stopped"] = True
            task.cancel()
