"""Window extraction and baseline caching layer.

Responsibilities:
- Extract baseline and recent windows from chronological history
- Cache and validate window matrices
- Manage incremental window updates
- Handle schema changes and incremental buffer rebuilds
"""

from typing import Optional
import numpy as np
from collections import deque


class WindowValidator:
    """Validates window matrices for readiness."""

    @staticmethod
    def is_valid_window_matrix(m: np.ndarray | None, *, min_rows: int = 2) -> bool:
        """Check if matrix is non-empty, 2D, and meets row/col minimums."""
        if m is None:
            return False
        if not isinstance(m, np.ndarray):
            return False
        if m.ndim != 2:
            return False
        rows, cols = int(m.shape[0]), int(m.shape[1])
        return rows >= int(min_rows) and cols >= 1

    @staticmethod
    def windows_ready(
        baseline: np.ndarray | None, recent: np.ndarray | None
    ) -> bool:
        """Both windows valid, same feature dimension."""
        if (
            not WindowValidator.is_valid_window_matrix(baseline)
            or not WindowValidator.is_valid_window_matrix(recent)
        ):
            return False
        return (
            baseline is not None
            and recent is not None
            and baseline.shape[1] == recent.shape[1]
        )


class WindowExtractor:
    """Extracts baseline and recent windows from chronological data."""

    def __init__(
        self,
        baseline_window: int,
        recent_window: int,
        window_stride: int = 1,
    ):
        self.baseline_window = baseline_window
        self.recent_window = recent_window
        self.window_stride = max(1, window_stride)

    def extract_from_chronological(
        self, m: np.ndarray
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Baseline / recent slices from a chronological (oldest→newest) matrix.

        Args:
            m: 2D matrix where rows are chronological (first row = oldest)

        Returns:
            (baseline_window, recent_window) or (None, None) if invalid
        """
        if m.ndim != 2:
            return None, None
        if m.shape[0] < self.baseline_window or m.shape[0] < self.recent_window:
            return None, None

        bl = m[: self.baseline_window][:: self.window_stride]
        rc = m[-self.recent_window :][:: self.window_stride]

        if not WindowValidator.windows_ready(bl, rc):
            return None, None

        return bl, rc

    def get_baseline_timestamps(
        self, frames: list[dict] | deque | None = None, max_frames: int | None = None
    ) -> Optional[list[float]]:
        """Extract timestamps for baseline window."""
        if frames is None:
            return None

        frame_list = list(frames) if isinstance(frames, deque) else frames
        if len(frame_list) < self.baseline_window:
            return None

        ts_vals: list[float] = []
        for f in frame_list[: self.baseline_window]:
            try:
                ts_vals.append(float(f.get("timestamp", 0.0)))
            except (TypeError, ValueError):
                pass

        return ts_vals if len(ts_vals) >= 2 else None

    def get_recent_timestamps(
        self, frames: list[dict] | deque | None = None
    ) -> Optional[list[float]]:
        """Extract timestamps for recent window."""
        if frames is None:
            return None

        frame_list = list(frames) if isinstance(frames, deque) else frames
        if len(frame_list) < self.recent_window:
            return None

        ts_vals: list[float] = []
        for f in frame_list[-self.recent_window :]:
            try:
                ts_vals.append(float(f.get("timestamp", 0.0)))
            except (TypeError, ValueError):
                pass

        return ts_vals if len(ts_vals) >= 2 else None
