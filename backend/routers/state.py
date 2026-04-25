"""State / read-only routes — system_state, metrics, intelligence, rooms, decisions."""
from fastapi import APIRouter

from services import engine_service as es
from services.builders import (
    build_system_state, build_metrics, build_intelligence, build_rooms,
    build_future_path_map, build_operator_decision, reconcile,
)
from services.serialise import sf, sfloat

router = APIRouter()


@router.get("/operator/decision")
async def operator_decision(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    if not aid or not results:
        return {"available": False, "now": "No system data. Run scenario or ingest data.", "do_this": "Start the engine."}
    return sf(build_operator_decision(results[-1]))


@router.get("/system/state")
async def system_state(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    if not aid or not results:
        return {"available": False, "reason": "No results. Run demo or ingest data."}
    return sf(build_system_state(results[-1]))


@router.get("/rooms")
async def rooms(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    if not aid or not results:
        return {"sensors": [], "sensor_count": 0}
    return sf(build_rooms(results[-1]))


@router.get("/metrics")
async def metrics(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    if not aid or not results:
        return {"available": False}
    return sf(build_metrics(results[-1]))


@router.get("/metrics/history")
async def metrics_history(asset_id: str = "", limit: int = 200):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    series = []
    for r in results[-limit:]:
        series.append({
            "index": r.get("_index", 0),
            "timestamp": r.get("timestamp"),
            "state": r.get("state"),
            "regime": r.get("regime"),
            "urgency": r.get("urgency"),
            "structural_drift_score": sfloat(r.get("structural_drift_score")),
            "instability_score": sfloat(r.get("instability_score")),
            "transition_pressure": sfloat(r.get("transition_pressure")),
            "drift_velocity": sfloat(r.get("drift_velocity")),
            "confidence_score": sfloat(r.get("confidence_score")),
            "system_health": int(round(max(0.0, 1.0 - sfloat(r.get("instability_score"))) * 100)),
            # Watch/alert thresholds derived from detection_threshold (constant)
            "watch_threshold": 0.45,
            "alert_threshold": 0.65,
        })
    return {"asset_id": aid, "count": len(series), "series": sf(series)}


@router.get("/intelligence")
async def intelligence(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    results = es.get_results(aid) if aid else []
    if not aid or not results:
        return {"available": False}
    return sf(build_intelligence(results[-1]))


@router.get("/future-path-map")
async def future_path_map(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    if not aid:
        return {"available": False, "reason": "No asset"}
    return sf(build_future_path_map(aid))


@router.get("/fleet/overview")
async def fleet_overview():
    assets = []
    for aid, results in es.all_results().items():
        if not results:
            continue
        last = results[-1]
        rec = reconcile(last)
        instability = sfloat(last.get("instability_score"))
        assets.append(sf({
            "asset_id": aid,
            "state": last.get("state"),
            "regime": last.get("regime"),
            "urgency": last.get("urgency"),
            "interpreted_state": last.get("regime"),
            "phase": last.get("phase"),
            "confidence_score": sfloat(last.get("confidence_score")),
            "operational_risk": rec["operational_risk"],
            "situation_summary": rec["situation_summary"],
            "structural_drift_score": sfloat(last.get("structural_drift_score")),
            "instability_score": instability,
            "transition_pressure": sfloat(last.get("transition_pressure")),
            "transition_state": last.get("transition_state"),
            "system_health": int(round(max(0.0, 1.0 - instability) * 100)),
            "display_health": int(round(max(0.0, 1.0 - instability) * 100)),
            "frame_count": len(results),
            "sensor_count": len(last.get("sensor_relationships", [])),
            "meta": es.asset_meta().get(aid),
        }))
    return {"assets": assets, "run_id": es.get_run_id()}
