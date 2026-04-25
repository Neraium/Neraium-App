"""Temporal coherence and feature extraction.

Responsibilities:
- Temporal feature extraction from recent window
- Temporal quality signals and lag-based features
- Time-to-instability forecasting
- Temporal coherence stage scoring

Note: Delegates to existing temporal_features and temporal_quality modules.
"""

from typing import Dict, Any, List, Optional
import numpy as np

from neraium_core.temporal_features import derive_temporal_rate_features
from neraium_core.temporal_quality import derive_temporal_quality_signals
from neraium_core.directional import lagged_correlation_matrix, directional_metrics
from neraium_core.forecasting import time_to_instability


def compute_temporal_metrics(
    z_recent_valid: np.ndarray,
    timestamps: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Compute all temporal coherence metrics.

    Args:
        z_recent_valid: Normalized recent data (valid sensors only)
        timestamps: Timestamps for recent window

    Returns:
        Dictionary with temporal metrics
    """
    # Temporal rate features (velocity, acceleration, etc.)
    temporal_features = derive_temporal_rate_features(
        recent_window=z_recent_valid,
        timestamps=timestamps,
    )

    # Temporal quality signals
    temporal_quality = derive_temporal_quality_signals(timestamps) if timestamps else {}

    # Directional metrics from lagged correlations
    try:
        lagged_corr = lagged_correlation_matrix(z_recent_valid, lag=1)
        directional = directional_metrics(lagged_corr)
    except Exception:
        directional = {"divergence": 0.0}

    # Time to instability forecast
    try:
        tti = time_to_instability(z_recent_valid)
    except Exception:
        tti = {"time_to_instability": None}

    return {
        "temporal_features": temporal_features,
        "temporal_quality": temporal_quality,
        "directional": directional,
        "time_to_instability": tti,
    }
