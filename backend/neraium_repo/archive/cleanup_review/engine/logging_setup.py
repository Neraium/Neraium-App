"""Structured logging setup for production deployments.

Provides consistent, structured logging with timestamps, unit IDs, and log levels.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from neraium_core.engine.config import ProductionLoggingConfig


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs."""

    def __init__(self, include_timestamps: bool = True, include_caller: bool = True):
        super().__init__()
        self.include_timestamps = include_timestamps
        self.include_caller = include_caller

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.include_timestamps:
            log_obj["timestamp"] = datetime.now(tz=timezone.utc).isoformat()

        if self.include_caller:
            log_obj["source"] = f"{record.filename}:{record.lineno}"

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "asset_id"):
            log_obj["asset_id"] = record.asset_id
        if hasattr(record, "unit_id"):
            log_obj["unit_id"] = record.unit_id

        return json.dumps(log_obj)


class TextFormatter(logging.Formatter):
    """Formatter that outputs human-readable text logs."""

    def __init__(self, include_timestamps: bool = True, include_caller: bool = True):
        super().__init__()
        self.include_timestamps = include_timestamps
        self.include_caller = include_caller

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as readable text."""
        parts = []

        if self.include_timestamps:
            dt = datetime.now(tz=timezone.utc).isoformat()
            parts.append(f"[{dt}]")

        parts.append(f"[{record.levelname}]")

        if hasattr(record, "unit_id"):
            parts.append(f"[unit:{record.unit_id}]")
        if hasattr(record, "asset_id"):
            parts.append(f"[asset:{record.asset_id}]")

        parts.append(f"[{record.name}]")

        if self.include_caller:
            parts.append(f"[{record.filename}:{record.lineno}]")

        parts.append(record.getMessage())

        message = " ".join(parts)

        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


def setup_logging(config: ProductionLoggingConfig | None = None) -> logging.Logger:
    """Set up structured logging for production.

    Args:
        config: Logging configuration. If None, loads from environment.

    Returns:
        Configured root logger.
    """
    if config is None:
        config = ProductionLoggingConfig.from_env()

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(config.level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.level)

    # Choose formatter
    if "json" in config.level.lower():
        formatter = StructuredFormatter(
            include_timestamps=config.include_timestamps,
            include_caller=config.include_caller,
        )
    else:
        formatter = TextFormatter(
            include_timestamps=config.include_timestamps,
            include_caller=config.include_caller,
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str, config: ProductionLoggingConfig | None = None) -> logging.Logger:
    """Get a logger for a specific module with structured logging.

    Args:
        name: Logger name (usually __name__)
        config: Logging configuration. If None, uses root logger config.

    Returns:
        Configured logger.
    """
    if config is None:
        config = ProductionLoggingConfig.from_env()

    logger = logging.getLogger(name)
    logger.setLevel(config.level)
    return logger
