from __future__ import annotations


class SIIError(Exception):
    """Base error for Systemic Infrastructure Intelligence."""


class SIIValidationError(SIIError):
    """Raised when telemetry input cannot be normalized safely."""


class SIIConfigurationError(SIIError):
    """Raised when SII configuration is invalid."""


class SIIIOError(SIIError):
    """Raised when safe input/output operations fail."""


class SIIProcessingError(SIIError):
    """Raised when the engine cannot process telemetry safely."""

