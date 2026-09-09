"""Hosting boundary only; the pinned App and authority sources remain unchanged."""
import asyncio
import fcntl
import json
import os
from pathlib import Path

from fastapi import Depends
from fastapi.responses import JSONResponse
from backend.workbench.api import app as workbench, authorize
from backend.workbench import authority

VERSION = json.loads(Path(__file__).with_name("version.json").read_text())
DATA = Path(os.environ["NERAIUM_WORKBENCH_DATA"])
DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
# Prevent overlapping tasks from opening the same database during replacement.
_lease = open(DATA / ".worker.lock", "a")
os.chmod(DATA / ".worker.lock", 0o600)
fcntl.flock(_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)


@workbench.get("/healthz")
def health():
    try:
        identity = authority.identity()
        if not os.access(DATA, os.W_OK):
            raise RuntimeError("Storage unavailable")
        return {"status": "ok", **VERSION, "authority_commit": identity["commit"]}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


@workbench.get("/api/version", dependencies=[Depends(authorize)])
def version():
    return VERSION


class SingleOperator:
    """Serialize complete API requests, including reads; health remains independent."""
    def __init__(self, inner):
        self.inner = inner
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            async with self.lock:
                await self.inner(scope, receive, send)
        else:
            await self.inner(scope, receive, send)


app = SingleOperator(workbench)
