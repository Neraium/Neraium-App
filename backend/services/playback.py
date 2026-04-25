"""Live playback orchestrator.

A single asyncio task ticks a set of `System` simulators on a fixed cadence,
ingesting each new sensor vector into `SIIEngineAdapter`. This is the
"live system" the operator sees — multi-system, multi-variable, with
real coupling.

Speed presets control the tick interval. Stop / reset are explicit.
"""
from __future__ import annotations
import asyncio
import time
import uuid
from typing import Dict, List, Optional, Any

from . import sii_state as ss
from . import synthetic_systems as syn


SPEED = {"slow": 0.8, "normal": 0.3, "fast": 0.05}

_state: Dict[str, Any] = {
    "running": False,
    "speed": "normal",
    "cycle": 0,
    "systems": [],            # list of synthetic_systems.System
    "started_at": None,
    "task": None,
    "stop_flag": False,
    "run_id": None,
}


def status() -> Dict[str, Any]:
    return {
        "running": _state["running"],
        "speed": _state["speed"],
        "cycle": _state["cycle"],
        "system_count": len(_state["systems"]),
        "started_at": _state["started_at"],
        "run_id": _state["run_id"],
    }


def list_templates() -> List[Dict[str, Any]]:
    return syn.list_templates()


def _build_systems(specs: List[Dict[str, Any]]) -> List[syn.System]:
    """Build N synthetic systems from a spec list. Each spec:
       {system_id, template, drift_at?, drift_severity?, drift_duration?, seed?}
    """
    built = []
    for i, spec in enumerate(specs):
        sid = spec.get("system_id") or f"sys-{i+1:02d}"
        template = spec.get("template") or "industrial"
        seed = spec.get("seed", 42 + i)
        drift_at = spec.get("drift_at", 80 + i * 12)
        severity = float(spec.get("drift_severity", 0.85))
        duration = int(spec.get("drift_duration", 240))
        sched = syn.standard_drift_schedule(start=drift_at, severity=severity, duration=duration) if severity > 0 else []
        sysobj = syn.make_system(sid, template=template, seed=seed, drift_schedule=sched)
        ss.register_system(
            system_id=sid, template=template,
            label=spec.get("label") or f"{template.capitalize()} {sid}",
            variables=sysobj.variables, units=sysobj.units,
        )
        built.append(sysobj)
    return built


async def _run_loop():
    while not _state["stop_flag"]:
        ts = time.time()
        for sysobj in _state["systems"]:
            try:
                sv = syn.tick(sysobj)
                ss.ingest_frame(sysobj.system_id, sv, ts)
            except Exception:
                pass
        _state["cycle"] += 1
        delay = SPEED.get(_state["speed"], 0.3)
        await asyncio.sleep(delay)
    _state["running"] = False


async def start(specs: Optional[List[Dict[str, Any]]] = None, speed: str = "normal") -> Dict[str, Any]:
    """Start (or restart) live playback. Resets all SII state."""
    await stop()
    ss.reset_all()
    _state["systems"] = _build_systems(specs or _default_specs())
    _state["speed"] = speed if speed in SPEED else "normal"
    _state["cycle"] = 0
    _state["stop_flag"] = False
    _state["running"] = True
    _state["started_at"] = time.time()
    _state["run_id"] = str(uuid.uuid4())[:8]
    _state["task"] = asyncio.create_task(_run_loop())
    return {"status": "started", **status()}


async def stop() -> Dict[str, Any]:
    _state["stop_flag"] = True
    task = _state.get("task")
    if task and not task.done():
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
    _state["running"] = False
    _state["task"] = None
    return {"status": "stopped", **status()}


def set_speed(speed: str) -> Dict[str, Any]:
    if speed in SPEED:
        _state["speed"] = speed
    return {"speed": _state["speed"]}


def _default_specs() -> List[Dict[str, Any]]:
    """Default playback: 4 systems across 3 templates; drift cascades over time."""
    return [
        {"system_id": "sys-A1", "template": "industrial", "drift_at": 70, "drift_severity": 0.85, "drift_duration": 220},
        {"system_id": "sys-A2", "template": "industrial", "drift_at": 0,  "drift_severity": 0.0},
        {"system_id": "sys-E1", "template": "environmental", "drift_at": 110, "drift_severity": 0.75, "drift_duration": 260},
        {"system_id": "sys-G1", "template": "generic", "drift_at": 0, "drift_severity": 0.0},
    ]
