"""WebSocket: live snapshot of all systems on every tick.

Client connects, sends {action: subscribe, interval_ms: 500} (optional),
and we push a {systems: [...]} payload at that cadence reflecting the
latest unified state from `sii_state`.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import sii_state as ss
from services.serialise import sf

router = APIRouter()


@router.websocket("/api/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    interval = 0.5
    stop = False
    push_task = None

    async def _push_loop():
        while not stop:
            payload = {
                "type": "snapshot",
                "systems": [
                    {
                        "system_id": rec.system_id,
                        "label": rec.label,
                        "template": rec.template,
                        "frame_count": len(rec.history),
                        "latest": rec.history[-1] if rec.history else None,
                    }
                    for rec in ss.all_systems()
                ],
            }
            try:
                await ws.send_json(sf(payload))
            except Exception:
                return
            await asyncio.sleep(interval)

    push_task = asyncio.create_task(_push_loop())
    try:
        while True:
            txt = await ws.receive_text()
            try:
                msg = json.loads(txt)
            except Exception:
                continue
            action = msg.get("action")
            if action == "subscribe":
                ms = int(msg.get("interval_ms", 500))
                interval = max(0.1, ms / 1000.0)
                await ws.send_json({"type": "subscribed", "interval_ms": int(interval * 1000)})
            elif action == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        stop = True
        if push_task:
            push_task.cancel()
