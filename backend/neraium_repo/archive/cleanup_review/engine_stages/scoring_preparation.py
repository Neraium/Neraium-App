from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from neraium_core.geometry import correlation_matrix
from neraium_core.staged_pipeline import FeatureExtractionStage


class ScoringPreparationContext(Protocol):
    _rolling_baseline_corr: np.ndarray | None


@dataclass(frozen=True)
class ScoringPreparationInput:
    z_baseline: np.ndarray
    z_recent: np.ndarray
    valid_mask: np.ndarray
    valid_signal_count: int


@dataclass(frozen=True)
class ScoringPreparationResult:
    should_proceed_scoring: bool
    correlation_ready: bool
    covariance_ready: bool
    minimum_sample_ready: bool
    shape_compatible: bool
    z_baseline_valid: np.ndarray | None
    z_recent_valid: np.ndarray | None
    stage_features: dict[str, Any] | None
    corr_baseline: np.ndarray | None
    corr_recent: np.ndarray | None
    baseline_corr_used: np.ndarray | None
    baseline_mode: str | None


def prepare_scoring_inputs(
    context: ScoringPreparationContext,
    stage_input: ScoringPreparationInput,
) -> ScoringPreparationResult:
    correlation_ready = stage_input.valid_signal_count >= 2
    covariance_ready = correlation_ready
    minimum_sample_ready = correlation_ready

    if not correlation_ready:
        return ScoringPreparationResult(
            should_proceed_scoring=False,
            correlation_ready=correlation_ready,
            covariance_ready=covariance_ready,
            minimum_sample_ready=minimum_sample_ready,
            shape_compatible=False,
            z_baseline_valid=None,
            z_recent_valid=None,
            stage_features=None,
            corr_baseline=None,
            corr_recent=None,
            baseline_corr_used=None,
            baseline_mode=None,
        )

    z_base_valid = stage_input.z_baseline[:, stage_input.valid_mask]
    z_recent_valid = stage_input.z_recent[:, stage_input.valid_mask]
    stage_features = FeatureExtractionStage.extract(z_base_valid, z_recent_valid)

    corr_baseline = correlation_matrix(z_base_valid)
    corr_recent = correlation_matrix(z_recent_valid)

    baseline_corr_used = corr_baseline
    baseline_mode = "fixed"
    if context._rolling_baseline_corr is not None and context._rolling_baseline_corr.shape == corr_recent.shape:
        baseline_corr_used = context._rolling_baseline_corr
        baseline_mode = "rolling"

    shape_compatible = bool(corr_baseline.shape == corr_recent.shape == baseline_corr_used.shape)
    should_proceed_scoring = bool(correlation_ready and covariance_ready and minimum_sample_ready and shape_compatible)

    return ScoringPreparationResult(
        should_proceed_scoring=should_proceed_scoring,
        correlation_ready=correlation_ready,
        covariance_ready=covariance_ready,
        minimum_sample_ready=minimum_sample_ready,
        shape_compatible=shape_compatible,
        z_baseline_valid=z_base_valid,
        z_recent_valid=z_recent_valid,
        stage_features=stage_features,
        corr_baseline=corr_baseline,
        corr_recent=corr_recent,
        baseline_corr_used=baseline_corr_used,
        baseline_mode=baseline_mode,
    )
