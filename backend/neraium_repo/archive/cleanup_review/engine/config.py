"""Configuration constants for the structural detection engine.

These values are locked for production compatibility (Phase-1 FD004 policy).
Changing these constants requires careful regression testing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Baseline adaptation: how quickly rolling baseline responds to new data.
# Locked at 0.92 to avoid absorbing instability signals.
DEFAULT_BASELINE_ADAPTATION_ALPHA = 0.92

# Composite score must be below this AND system in nominal state for baseline update.
BASELINE_UPDATE_MAX_COMPOSITE = 0.85

# Number of recent interpreted states used to compute classification stability.
CLASSIFICATION_STABILITY_WINDOW = 15

# Transition memory window size for historical tracking.
TRANSITION_MEMORY_WINDOW = 8

# Transition pressure thresholds for emerging/sustained classification.
TRANSITION_EMERGING_THRESHOLD = 0.85
TRANSITION_SUSTAINED_THRESHOLD = 1.15

# Fast mode geometry computation interval and downsampling.
FAST_MODE_GEOMETRY_UPDATE_INTERVAL = 3
FAST_MODE_GEOMETRY_DOWNSAMPLE_STEP = 2

# Minimum baseline samples collected before alert thresholds can be calibrated.
# Prevents early single-sample spikes from triggering alerts.
MIN_BASELINE_SAMPLES_FOR_CALIBRATION = 28

# FD004 policy defaults (locked for Phase-1 compatibility).
# These drive the drift-score state machine behavior.
LOCKED_FD004_POLICY_DEFAULTS = {
    "drift_smoothing_window": 25,
    "watch_quantile": 0.65,
    "alert_quantile": 0.85,
    "watch_persistence": 5,
    "alert_persistence": 3,
    "fast_trigger_multiplier": 1.25,
    "alert_latch_enabled": True,
    "unlatch_ratio": 0.75,
}

# Unpack FD004 defaults for backward compatibility.
DEFAULT_DRIFT_SMOOTHING_WINDOW = LOCKED_FD004_POLICY_DEFAULTS["drift_smoothing_window"]
DEFAULT_WATCH_QUANTILE = LOCKED_FD004_POLICY_DEFAULTS["watch_quantile"]
DEFAULT_ALERT_QUANTILE = LOCKED_FD004_POLICY_DEFAULTS["alert_quantile"]
DEFAULT_WATCH_PERSISTENCE = LOCKED_FD004_POLICY_DEFAULTS["watch_persistence"]
DEFAULT_ALERT_PERSISTENCE = LOCKED_FD004_POLICY_DEFAULTS["alert_persistence"]
DEFAULT_FAST_TRIGGER_MULTIPLIER = LOCKED_FD004_POLICY_DEFAULTS["fast_trigger_multiplier"]
DEFAULT_ALERT_LATCH_ENABLED = LOCKED_FD004_POLICY_DEFAULTS["alert_latch_enabled"]
DEFAULT_UNLATCH_RATIO = LOCKED_FD004_POLICY_DEFAULTS["unlatch_ratio"]

# Sensor value normalization.
DEFAULT_SENSOR_NORMALIZATION_ALPHA = 0.01

# Drift EMA smoothing coefficient.
DEFAULT_DRIFT_EMA_ALPHA = 0.2

# Default transition persistence length.
DEFAULT_TRANSITION_PERSISTENCE = 3


@dataclass(frozen=True)
class ProductionEngineConfig:
    """Production engine configuration with environment variable support.

    All values have safe defaults suitable for continuous production monitoring.
    This is the primary configuration interface for production deployments.
    """

    # Window sizes (in frames)
    baseline_window: int = 24  # Early frames to build baseline model
    recent_window: int = 8     # Recent frames for drift comparison
    max_frames: int = 500      # Maximum frames to retain in memory

    # Scoring weights
    mahal_weight: float = 0.65  # Weight for Mahalanobis distance
    cov_weight: float = 0.35    # Weight for covariance drift

    # Smoothing
    smoothing_window: int = 3
    enable_vector_smoothing: bool = True

    def validate(self) -> None:
        """Validate configuration consistency.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.baseline_window < 4:
            raise ValueError("baseline_window must be >= 4")
        if self.recent_window < 3:
            raise ValueError("recent_window must be >= 3")
        if self.baseline_window < self.recent_window:
            raise ValueError("baseline_window must be >= recent_window")
        if self.max_frames < (self.baseline_window + self.recent_window + 100):
            raise ValueError(
                f"max_frames ({self.max_frames}) too small for window config "
                f"(baseline={self.baseline_window}, recent={self.recent_window})"
            )
        if (self.mahal_weight + self.cov_weight) <= 0:
            raise ValueError("mahal_weight + cov_weight must be > 0")
        if self.smoothing_window < 1:
            raise ValueError("smoothing_window must be >= 1")

    @staticmethod
    def from_env() -> ProductionEngineConfig:
        """Load configuration from environment variables.

        Supported environment variables:
        - NERAIUM_BASELINE_WINDOW: int, default 24
        - NERAIUM_RECENT_WINDOW: int, default 8
        - NERAIUM_MAX_FRAMES: int, default 500
        - NERAIUM_MAHAL_WEIGHT: float, default 0.65
        - NERAIUM_COV_WEIGHT: float, default 0.35
        """

        def get_int(name: str, default: int, *, minimum: int = 1) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                val = int(str(raw).strip())
                if val < minimum:
                    raise ValueError(f"{name} must be >= {minimum}")
                return val
            except ValueError as e:
                raise ValueError(f"Invalid {name}: {e}") from e

        def get_float(name: str, default: float, *, minimum: float = 0.0) -> float:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                val = float(str(raw).strip())
                if val < minimum:
                    raise ValueError(f"{name} must be >= {minimum}")
                return val
            except ValueError as e:
                raise ValueError(f"Invalid {name}: {e}") from e

        cfg = ProductionEngineConfig(
            baseline_window=get_int("NERAIUM_BASELINE_WINDOW", 24, minimum=4),
            recent_window=get_int("NERAIUM_RECENT_WINDOW", 8, minimum=3),
            max_frames=get_int("NERAIUM_MAX_FRAMES", 500, minimum=100),
            mahal_weight=get_float("NERAIUM_MAHAL_WEIGHT", 0.65),
            cov_weight=get_float("NERAIUM_COV_WEIGHT", 0.35),
        )
        cfg.validate()
        return cfg

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "baseline_window": self.baseline_window,
            "recent_window": self.recent_window,
            "max_frames": self.max_frames,
            "mahal_weight": self.mahal_weight,
            "cov_weight": self.cov_weight,
            "smoothing_window": self.smoothing_window,
            "enable_vector_smoothing": self.enable_vector_smoothing,
        }


@dataclass(frozen=True)
class ProductionLoggingConfig:
    """Production logging configuration."""

    level: str = "INFO"  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    include_timestamps: bool = True
    include_caller: bool = True

    @staticmethod
    def from_env() -> ProductionLoggingConfig:
        """Load logging configuration from environment variables."""
        level = os.getenv("NERAIUM_LOG_LEVEL", "INFO").strip().upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Invalid NERAIUM_LOG_LEVEL: {level}")

        return ProductionLoggingConfig(
            level=level,
            include_timestamps=os.getenv("NERAIUM_LOG_TIMESTAMPS", "1").strip().lower() in {"1", "true"},
            include_caller=os.getenv("NERAIUM_LOG_CALLER", "1").strip().lower() in {"1", "true"},
        )

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "level": self.level,
            "include_timestamps": self.include_timestamps,
            "include_caller": self.include_caller,
        }
