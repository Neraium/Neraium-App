"""Structural drift detection and state machine.

Responsibilities:
- Compute drift score from correlation matrix changes
- EMA smoothing of drift signal
- Calibrate watch/alert thresholds from baseline samples
- Drift state machine: STABLE → WATCH → ALERT
- Alert persistence and unlatching logic
"""

from typing import Tuple
from collections import deque
import numpy as np

from .config import DEFAULT_DRIFT_EMA_ALPHA, DEFAULT_DRIFT_SMOOTHING_WINDOW


class DriftStateMachine:
    """Manages drift score and alert state transitions."""

    def __init__(
        self,
        smoothing_window: int = DEFAULT_DRIFT_SMOOTHING_WINDOW,
        watch_quantile: float = 0.65,
        alert_quantile: float = 0.85,
        watch_persistence: int = 5,
        alert_persistence: int = 3,
        fast_trigger_multiplier: float = 1.25,
        alert_latch_enabled: bool = True,
        unlatch_ratio: float = 0.75,
    ):
        self.smoothing_window = int(smoothing_window)
        self.watch_quantile = float(watch_quantile)
        self.alert_quantile = float(alert_quantile)
        self.watch_persistence = int(watch_persistence)
        self.alert_persistence = int(alert_persistence)
        self.fast_trigger_multiplier = float(fast_trigger_multiplier)
        self.alert_latch_enabled = bool(alert_latch_enabled)
        self.unlatch_ratio = float(unlatch_ratio)

        # Rolling smoothing buffer (O(1) rolling mean)
        self._smoothing_buffer: deque[float] = deque(maxlen=smoothing_window)
        self._smoothing_sum: float = 0.0

        # EMA smoothing
        self._ema_alpha = DEFAULT_DRIFT_EMA_ALPHA
        self._smoothed_ema: float | None = None
        self._prev_smoothed: float | None = None

        # State machine counters
        self._watch_counter: int = 0
        self._alert_counter: int = 0
        self._alert_latched: bool = False
        self._current_state: str = "STABLE"

        # Threshold calibration
        self._thresholds: Tuple[float, float] | None = None
        self._baseline_samples: deque[float] = deque(maxlen=256)

    def update(self, drift_score: float) -> Tuple[str, float]:
        """Process a drift score and return (alert_state, smoothed_score).

        Args:
            drift_score: Raw structural drift score [0, 1]

        Returns:
            (alert_state: str, smoothed_score: float)
            alert_state in {"STABLE", "WATCH", "ALERT"}
        """
        raw = float(drift_score)

        # O(1) rolling mean smoothing
        if len(self._smoothing_buffer) < self._smoothing_buffer.maxlen:
            self._smoothing_buffer.append(raw)
            self._smoothing_sum += raw
        else:
            dropped = float(self._smoothing_buffer.popleft())
            self._smoothing_sum -= dropped
            self._smoothing_buffer.append(raw)
            self._smoothing_sum += raw

        smooth = raw
        if self._smoothing_buffer:
            smooth = float(self._smoothing_sum / len(self._smoothing_buffer))

        # Collect baseline samples for threshold calibration
        self._baseline_samples.append(smooth)

        # Apply EMA smoothing
        if self._smoothed_ema is None:
            self._smoothed_ema = smooth
        else:
            alpha = self._ema_alpha
            self._smoothed_ema = alpha * smooth + (1.0 - alpha) * self._smoothed_ema

        smoothed = float(self._smoothed_ema)

        # Until thresholds are calibrated, stay STABLE
        if self._thresholds is None:
            self._current_state = "STABLE"
            return self._current_state, smoothed

        watch_thr, alert_thr = self._thresholds

        # Update persistence counters
        if smoothed > alert_thr:
            self._alert_counter += 1
        else:
            self._alert_counter = max(0, self._alert_counter - 1)

        if smoothed > watch_thr:
            self._watch_counter += 1
        else:
            self._watch_counter = max(0, self._watch_counter - 1)

        # Fast trigger: immediately latch if spike exceeds threshold
        if self._alert_counter >= self.alert_persistence:
            self._alert_latched = True
        if smoothed > (alert_thr * self.fast_trigger_multiplier):
            self._alert_latched = True
            self._alert_counter = max(self._alert_counter, self.alert_persistence)

        # Unlatch logic
        if not self.alert_latch_enabled and smoothed <= alert_thr:
            self._alert_latched = False

        if self._alert_latched and smoothed < (watch_thr * self.unlatch_ratio):
            self._alert_latched = False
            self._alert_counter = 0

        # State determination
        if self._alert_latched:
            self._current_state = "ALERT"
        elif self._alert_counter >= self.alert_persistence:
            self._current_state = "ALERT"
        elif self._watch_counter >= self.watch_persistence:
            self._current_state = "WATCH"
        else:
            self._current_state = "STABLE"

        self._prev_smoothed = smoothed
        return self._current_state, smoothed

    def calibrate_thresholds(self) -> None:
        """Calibrate watch/alert thresholds from collected baseline samples."""
        if len(self._baseline_samples) < 28:  # MIN_BASELINE_SAMPLES_FOR_CALIBRATION
            return

        baseline_window = list(self._baseline_samples)[-min(30, len(self._baseline_samples)) :]
        watch_thr = float(np.percentile(baseline_window, 100.0 * self.watch_quantile))
        alert_thr = float(np.percentile(baseline_window, 100.0 * self.alert_quantile))

        if alert_thr < watch_thr:
            watch_thr, alert_thr = alert_thr, watch_thr

        self._thresholds = (watch_thr, alert_thr)

    def get_thresholds(self) -> Tuple[float, float] | None:
        """Get current (watch, alert) thresholds or None if not calibrated."""
        return self._thresholds

    def get_state(self) -> str:
        """Get current alert state."""
        return self._current_state

    def get_velocity(self) -> float:
        """Get drift velocity (absolute change from previous smoothed score)."""
        if self._prev_smoothed is None:
            return 0.0
        return abs(float(self._smoothed_ema or 0.0) - self._prev_smoothed)
