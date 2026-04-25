"""Engine ingest routes — single, batch, CSV upload, reset, readiness, export."""
import io
import time
import uuid
import logging
import numpy as np
import pandas as pd

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from services import engine_service as es
from services.serialise import sf
from routers.models import ProcessRequest, BatchProcessRequest, ResetRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/engine/process")
async def engine_process(req: ProcessRequest):
    if es.get_run_id() is None:
        es.set_run_id(str(uuid.uuid4())[:8])
    frame = {"timestamp": req.timestamp, "asset_id": req.asset_id, "site_id": "production", "sensor_values": req.sensor_values}
    try:
        raw = es.process_frame(req.asset_id, frame)
        return {"status": "ok", "result": sf(raw)}
    except Exception as e:
        logger.error(f"Process error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine/process/batch")
async def engine_process_batch(req: BatchProcessRequest):
    if es.get_run_id() is None:
        es.set_run_id(str(uuid.uuid4())[:8])
    processed, errors, start = 0, [], time.time()
    for i, f in enumerate(req.frames):
        frame = {"timestamp": f.timestamp, "asset_id": f.asset_id, "site_id": "production", "sensor_values": f.sensor_values}
        try:
            es.process_frame(f.asset_id, frame)
            processed += 1
        except Exception as e:
            errors.append(f"Frame {i}: {e}")
    return {"status": "ok", "processed": processed, "errors": errors[:10],
            "processing_time_seconds": round(time.time() - start, 3)}


@router.post("/engine/upload")
async def upload_csv(file: UploadFile = File(...)):
    es.reset_all()
    es.set_run_id(str(uuid.uuid4())[:8])
    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")
    if "unit" in df.columns and "asset_id" not in df.columns:
        df["asset_id"] = df["unit"].astype(str)
    elif "asset_id" not in df.columns:
        df["asset_id"] = "unit-1"
    if "cycle" in df.columns and "timestamp" not in df.columns:
        df["timestamp"] = df["cycle"].astype(float)
    elif "timestamp" not in df.columns:
        df["timestamp"] = range(len(df))
    skip = {"timestamp", "asset_id", "site_id", "unit", "cycle", "id", "time"}
    sensor_cols = [c for c in df.columns if c not in skip and df[c].dtype in [np.float64, np.int64, float, int]]
    if not sensor_cols:
        raise HTTPException(status_code=400, detail="No numeric sensor columns")
    processed = 0
    for _, row in df.iterrows():
        sensors = {c: float(row[c]) for c in sensor_cols if np.isfinite(float(row[c]))}
        if not sensors:
            continue
        aid = str(row["asset_id"])
        es.process_frame(aid, {"timestamp": float(row["timestamp"]), "asset_id": aid, "site_id": "production", "sensor_values": sensors})
        processed += 1
    return {"status": "ok", "processed": processed, "sensor_columns": sensor_cols, "run_id": es.get_run_id()}


@router.get("/engine/readiness")
async def engine_readiness(asset_id: str = ""):
    aid = asset_id or es.first_asset()
    if aid:
        return es.asset_readiness(aid)
    return {"assets": es.all_asset_ids(), "total_results": sum(len(r) for r in es.all_results().values())}


@router.post("/engine/reset")
async def reset_engine(req: ResetRequest):
    if req.confirm:
        es.reset_all()
        return {"status": "ok"}
    return {"status": "skipped"}


@router.get("/engine/export")
async def export_results(asset_id: str = ""):
    if asset_id:
        results = es.get_results(asset_id)
    else:
        results = [r for rs in es.all_results().values() for r in rs]
    if not results:
        raise HTTPException(status_code=404, detail="No results")
    return JSONResponse(content=sf({"run_id": es.get_run_id(), "total_frames": len(results), "results": results}))
