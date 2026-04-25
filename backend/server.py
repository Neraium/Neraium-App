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
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Make the sibling /app available on sys.path so `neraium_core` resolves
_REPO_ROOT = ROOT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

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
from routers import ws as ws_router  # noqa: E402

api_router.include_router(systems_router.router)
api_router.include_router(playback_router.router)
api_router.include_router(audit_router.router)
api_router.include_router(customers_router.router)
api_router.include_router(ingest_router.router)
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
    mongo_client.close()
