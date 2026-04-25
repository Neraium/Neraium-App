from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import numpy as np

from neraium_core.realtime.buffer import HistoryRingBuffer, TimestampDequeBuffer, VectorDequeBuffer


class IngressHistoryBufferContext(Protocol):
    frames: deque[dict[str, Any]]
    _transition_pressure_history: deque[float]
    _shock_activity_history: deque[float]
    _structural_drift_history: deque[float]
    _sensor_schema_dirty: bool
    _history_ring: HistoryRingBuffer
    _recent_vector_buffer: VectorDequeBuffer
    _recent_ts_buffer: TimestampDequeBuffer

    def _invalidate_window_caches(self) -> None: ...

    def _rebuild_incremental_buffers_after_schema_change(self) -> None: ...

    def _refresh_baseline_matrix_cache(self) -> None: ...


@dataclass(frozen=True)
class IngressAndHistoryBuffersInput:
    frame: dict[str, Any]
    vector: np.ndarray


@dataclass(frozen=True)
class IngressAndHistoryBuffersResult:
    history_transition_len_before: int
    history_shock_len_before: int
    history_drift_len_before: int
    ts_val: float
    ts_ring: float


def prepare_ingress_and_history_buffers(
    context: IngressHistoryBufferContext,
    stage_input: IngressAndHistoryBuffersInput,
    *,
    to_epoch_seconds: Callable[[object], float],
    incremental_windows_enabled: bool,
) -> IngressAndHistoryBuffersResult:
    frame = stage_input.frame
    vector = stage_input.vector
    history_transition_len_before = len(context._transition_pressure_history)
    history_shock_len_before = len(context._shock_activity_history)
    history_drift_len_before = len(context._structural_drift_history)

    stored = dict(frame)
    stored["_vector"] = vector
    context.frames.append(stored)

    try:
        ts_val = to_epoch_seconds(frame["timestamp"])
    except (TypeError, ValueError):
        ts_val = 0.0
    try:
        ts_ring = to_epoch_seconds(frame["timestamp"])
    except (TypeError, ValueError):
        ts_ring = float(len(context.frames) - 1)
    if context._sensor_schema_dirty:
        context._invalidate_window_caches()
        context._history_ring.rebuild_from_frames(list(context.frames))
        context._rebuild_incremental_buffers_after_schema_change()
        context._sensor_schema_dirty = False
    else:
        context._history_ring.append(vector, ts_ring)
        if incremental_windows_enabled:
            context._recent_vector_buffer.append(vector)
            context._recent_ts_buffer.append(ts_val)
            context._refresh_baseline_matrix_cache()

    return IngressAndHistoryBuffersResult(
        history_transition_len_before=history_transition_len_before,
        history_shock_len_before=history_shock_len_before,
        history_drift_len_before=history_drift_len_before,
        ts_val=float(ts_val),
        ts_ring=float(ts_ring),
    )
