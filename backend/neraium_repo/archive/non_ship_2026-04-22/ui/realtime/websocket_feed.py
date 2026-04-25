from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any, AsyncIterator, Callable


@dataclass(frozen=True)
class RealtimeFeed:
    endpoint: str
    enabled: bool
    reason: str | None = None


@dataclass(frozen=True)
class RealtimeRuntime:
    status: RealtimeFeed
    stream_factory: Callable[[], AsyncIterator[dict[str, Any]]] | None = None


async def _disabled_stream() -> AsyncIterator[dict[str, Any]]:
    if False:
        yield {}


async def _ws_stream(endpoint: str) -> AsyncIterator[dict[str, Any]]:
    import websockets

    async with websockets.connect(endpoint) as socket:
        async for message in socket:
            yield {"raw": message}


def create_realtime_feed(endpoint: str) -> RealtimeRuntime:
    if find_spec("websockets") is None:
        return RealtimeRuntime(
            status=RealtimeFeed(endpoint=endpoint, enabled=False, reason="websockets dependency unavailable"),
            stream_factory=_disabled_stream,
        )
    return RealtimeRuntime(status=RealtimeFeed(endpoint=endpoint, enabled=True), stream_factory=lambda: _ws_stream(endpoint))
