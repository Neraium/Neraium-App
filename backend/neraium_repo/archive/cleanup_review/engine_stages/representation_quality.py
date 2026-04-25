from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from neraium_core.context_invariant_representation import (
    TemporalRepresentation,
    TemporalRepresentationConfig,
    build_temporal_representation,
)
from neraium_core.data_quality import (
    DataQualityReport,
    compute_data_quality,
    data_quality_summary,
    impute_missing_simple,
    should_use_degraded_analytics,
)
from neraium_core.geometry import normalize_window
from neraium_core.temporal_features import derive_temporal_rate_features
from neraium_core.temporal_quality import derive_temporal_quality_signals


class RepresentationAndQualityContext(Protocol):
    baseline_window: int
    recent_window: int
    window_stride: int
    sensor_order: list[str]
    representation_config: TemporalRepresentationConfig

    def _get_baseline_timestamps(self, frames_list: list[dict] | None = None) -> list[float] | None: ...

    def _get_recent_timestamps(self, frames_list: list[dict] | None = None) -> list[float] | None: ...


@dataclass(frozen=True)
class RepresentationAndQualityInput:
    history_matrix: np.ndarray
    history_timestamps: np.ndarray | None


@dataclass(frozen=True)
class RepresentationAndQualityResult:
    representation: TemporalRepresentation
    baseline_window: np.ndarray
    recent_window: np.ndarray
    z_baseline: np.ndarray
    z_recent: np.ndarray
    baseline_mean: np.ndarray
    baseline_std: np.ndarray
    recent_mean: np.ndarray
    recent_std: np.ndarray
    ts_baseline: list[float] | None
    ts_recent: list[float] | None
    temporal_quality: dict[str, float]
    temporal_features: dict[str, object]
    data_quality_report: DataQualityReport
    dq_summary: dict[str, object]
    valid_mask: np.ndarray
    valid_signal_count: int
    use_degraded: bool


def build_representation_and_quality(
    context: RepresentationAndQualityContext,
    stage_input: RepresentationAndQualityInput,
) -> RepresentationAndQualityResult:
    history_ts = stage_input.history_timestamps
    rep = build_temporal_representation(
        stage_input.history_matrix,
        context.representation_config,
        timestamps=history_ts,
    )
    transformed_history = rep.transformed
    baseline_window = np.asarray(
        transformed_history[: context.baseline_window][:: context.window_stride],
        dtype=float,
    )
    recent_window = np.asarray(
        transformed_history[-context.recent_window :][:: context.window_stride],
        dtype=float,
    )
    ts_baseline = context._get_baseline_timestamps(None)
    ts_recent = context._get_recent_timestamps(None)
    temporal_quality = derive_temporal_quality_signals(ts_recent)

    data_quality_report = compute_data_quality(
        baseline_window,
        recent_window,
        sensor_names=context.sensor_order,
        timestamps_baseline=ts_baseline,
        timestamps_recent=ts_recent,
    )
    dq_summary = data_quality_summary(data_quality_report)

    use_degraded = (not data_quality_report.gate_passed) and should_use_degraded_analytics(data_quality_report)
    if not data_quality_report.gate_passed and use_degraded:
        baseline_window = impute_missing_simple(baseline_window, method="column_mean")
        recent_window = impute_missing_simple(recent_window, method="column_mean")

    z_baseline, baseline_mean, baseline_std = normalize_window(baseline_window)
    z_recent, recent_mean, recent_std = normalize_window(recent_window)
    temporal_features = derive_temporal_rate_features(recent_window=z_recent, timestamps=ts_recent)

    valid_mask = (np.nan_to_num(recent_std) > 1e-12) | (np.nan_to_num(baseline_std) > 1e-12)
    valid_signal_count = int(np.sum(valid_mask))
    valid_signal_count = min(valid_signal_count, len(context.sensor_order))

    return RepresentationAndQualityResult(
        representation=rep,
        baseline_window=baseline_window,
        recent_window=recent_window,
        z_baseline=z_baseline,
        z_recent=z_recent,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
        recent_mean=recent_mean,
        recent_std=recent_std,
        ts_baseline=ts_baseline,
        ts_recent=ts_recent,
        temporal_quality=temporal_quality,
        temporal_features=temporal_features,
        data_quality_report=data_quality_report,
        dq_summary=dq_summary,
        valid_mask=valid_mask,
        valid_signal_count=valid_signal_count,
        use_degraded=use_degraded,
    )
