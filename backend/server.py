"""Neraium SII Engine Console — API Server (thin shell).

Wraps `neraium_core.sii_engine_adapter.SIIEngineAdapter` (single source of truth
for regime + urgency + instability_score). All business logic lives in
`routers/` and `services/`.
"""
import os
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

app = FastAPI(title="Neraium SII Console API", version="6.0.0")

api_router = APIRouter(prefix="/api")

from routers import engine as engine_router  # noqa: E402
from routers import demo as demo_router  # noqa: E402
from routers import state as state_router  # noqa: E402
from routers import audit as audit_router  # noqa: E402
from routers import ws as ws_router  # noqa: E402


@api_router.get("/")
async def root():
    return {
        "name": "Neraium SII Operator Console",
        "version": "6.0.0",
        "engine": "neraium_core.sii_engine_adapter.SIIEngineAdapter",
    }


api_router.include_router(state_router.router)
api_router.include_router(engine_router.router)
api_router.include_router(demo_router.router)
api_router.include_router(audit_router.router)
app.include_router(api_router)

# WebSocket router declares full /api path itself
app.include_router(ws_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    mongo_client.close()


# Periodic audit flush — write any new urgency transitions to Mongo every 2s
from routers.audit import scan_and_log as _audit_scan  # noqa: E402
from services.builders import build_operator_decision  # noqa: E402
from services import engine_service as es  # noqa: E402


async def _audit_flush_loop():
    while True:
        try:
            for aid in list(es.all_results().keys()):
                await _audit_scan(aid, build_operator_decision)
        except Exception:
            pass
        await asyncio.sleep(2.0)


@app.on_event("startup")
async def _start_audit_loop():
    asyncio.create_task(_audit_flush_loop())
