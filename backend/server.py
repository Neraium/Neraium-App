"""Neraium SII — Real-Time System Intelligence Platform (API thin shell).

Wraps `neraium_core.sii_engine_adapter.SIIEngineAdapter` (only) and exposes
a generalised, system-agnostic API: the operator works with abstract
"systems" of multi-variable telemetry, not a specific dataset.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Make the repo root available on sys.path so `neraium_core` resolves
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger(__name__)

# Support both MONGO_URI and MONGO_URL env var names
_mongo_uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME", "neraium")

mongo_client = None
db = None

if _mongo_uri:
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_client = AsyncIOMotorClient(_mongo_uri)
    db = mongo_client[_db_name]
    _log.info("Mongo connected: %s", _db_name)
else:
    _log.warning("Mongo disabled: MONGO_URI not found")

app = FastAPI(title="Neraium SII Platform API", version="1.0.0")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {
        "name": "Neraium SII Platform",
        "version": "1.0.0",
        "engine": "neraium_core.sii_engine_adapter.SIIEngineAdapter",
        "tagline": "Real-time system intelligence — see instability before it breaks.",
    }


from routers import systems as systems_router  # noqa: E402
from routers import playback as playback_router  # noqa: E402
from routers import audit as audit_router  # noqa: E402
from routers import customers as customers_router  # noqa: E402
from routers import ingest as ingest_router  # noqa: E402
from routers import demo as demo_router  # noqa: E402
from routers import ws as ws_router  # noqa: E402

api_router.include_router(systems_router.router)
api_router.include_router(playback_router.router)
api_router.include_router(audit_router.router)
api_router.include_router(customers_router.router)
api_router.include_router(ingest_router.router)
api_router.include_router(demo_router.router)
app.include_router(api_router)
app.include_router(ws_router.router)  # WS path includes /api itself

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# Audit auto-flush (every 2s)
async def _audit_flush():
    from routers.audit import scan_and_log
    while True:
        try:
            await scan_and_log()
        except Exception:
            pass
        await asyncio.sleep(2.0)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_audit_flush())


@app.on_event("shutdown")
async def _shutdown():
    if mongo_client is not None:
        mongo_client.close()
