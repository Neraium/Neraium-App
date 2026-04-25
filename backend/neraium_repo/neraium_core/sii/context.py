from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ExternalContextSnapshot:
    """
    Optional non-core context for future integration layers (external timing or metadata).

    This context is read-only metadata and must never trigger control actions.
    """

    source: str
    payload: dict[str, Any]


class ExternalContextProvider(Protocol):
    """
    Optional extension boundary for context enrichment.
    """

    def snapshot(self, frame: dict[str, Any]) -> ExternalContextSnapshot | None:
        ...


# Backward/engine naming aliases for optional boundary.
OptionalContextProvider = ExternalContextProvider


class FutureExternalContextBoundary(Protocol):
    """
    Optional future ingestion boundary for external context sources.

    This is intentionally a protocol-only contract and not an active dependency.
    """

    def ingest_context(self, frame: dict[str, Any]) -> dict[str, Any] | None:
        ...


class NoOpContextProvider:
    def snapshot(self, frame: dict[str, Any]) -> ExternalContextSnapshot | None:
        _ = frame
        return None


def snapshot_to_dict(snapshot: ExternalContextSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "source": snapshot.source,
        "payload": dict(snapshot.payload),
    }

