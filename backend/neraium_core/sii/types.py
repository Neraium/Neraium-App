from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

import numpy as np


InterpretedState = Literal[
    "NOMINAL_STRUCTURE",
    "REGIME_SHIFT_OBSERVED",
    "COUPLING_INSTABILITY_OBSERVED",
    "STRUCTURAL_INSTABILITY_OBSERVED",
    "COHERENCE_UNDER_CONSTRAINT",
]
DecisionState = Literal["STABLE", "WATCH", "ALERT"]
ConfidenceLevel = Literal["low", "medium", "high"]

ALLOWED_INTERPRETED_STATES: set[str] = {
    "NOMINAL_STRUCTURE",
    "REGIME_SHIFT_OBSERVED",
    "COUPLING_INSTABILITY_OBSERVED",
    "STRUCTURAL_INSTABILITY_OBSERVED",
    "COHERENCE_UNDER_CONSTRAINT",
}
ALLOWED_STATES: set[str] = {"STABLE", "WATCH", "ALERT"}
ALLOWED_CONFIDENCE: set[str] = {"low", "medium", "high"}

# Compatibility aliases used by other modules/tests.
INTERPRETED_STATES = ALLOWED_INTERPRETED_STATES
STATES = ALLOWED_STATES
CONFIDENCE_LEVELS = ALLOWED_CONFIDENCE


class StructuralTelemetryFrame(TypedDict):
    timestamp: str
    site_id: str
    system_id: str
    asset_id: str
    node_id: str
    variables: dict[str, float | int | str | None]
    sensor_values: dict[str, float | int | str | None]
    quality_metadata: dict[str, Any]
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class IngestionQualityMetadata:
    missingness_rate: float
    stale_signal: bool
    flatlined_variables: list[str]
    source_status: str
    validation_issues: list[str] = field(default_factory=list)
    completeness_score: float = 1.0


@dataclass(frozen=True)
class IngestionSourceMetadata:
    source_type: str
    source_name: str
    source_record_id: str | None = None
    source_schema_version: str | None = None
    request_id: str | None = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalIngestionRecord:
    """
    Source-agnostic canonical record shape for SII ingestion.
    """

    timestamp: str
    site_id: str
    system_id: str
    asset_id: str
    node_id: str
    variables: dict[str, float | None]
    quality_metadata: IngestionQualityMetadata
    source_metadata: IngestionSourceMetadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sensor_values(self) -> dict[str, float | None]:
        # Compatibility with legacy field naming.
        return dict(self.variables)


@dataclass(frozen=True)
class SIIFrame:
    timestamp: str
    site_id: str
    system_id: str
    asset_id: str
    node_id: str
    sensor_values: dict[str, float | None]
    quality_metadata: IngestionQualityMetadata = field(
        default_factory=lambda: IngestionQualityMetadata(
            missingness_rate=0.0,
            stale_signal=False,
            flatlined_variables=[],
            source_status="ok",
            validation_issues=[],
            completeness_score=1.0,
        )
    )
    source_metadata: IngestionSourceMetadata = field(
        default_factory=lambda: IngestionSourceMetadata(
            source_type="unknown",
            source_name="unknown",
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)


# Backward-compatible name used by some internal modules.
TelemetryFrame = SIIFrame


@dataclass(frozen=True)
class CanonicalAnalysisTable:
    """
    Canonical internal tabular shape for SII windowed analysis.
    """

    records: list[CanonicalIngestionRecord]
    variable_names: list[str]
    epoch_timestamps: np.ndarray
    values: np.ndarray
    quality_mask: np.ndarray
    site_ids: list[str]
    system_ids: list[str]
    asset_ids: list[str]
    node_ids: list[str]

    @property
    def row_count(self) -> int:
        return int(self.values.shape[0])

    @property
    def variable_count(self) -> int:
        return int(self.values.shape[1]) if self.values.ndim == 2 else 0


@dataclass(frozen=True)
class CanonicalAnalysisWindow:
    """
    Canonical analysis window/system-state object for geometry/graph layers.
    """

    baseline_table: CanonicalAnalysisTable
    recent_table: CanonicalAnalysisTable
    baseline_matrix: np.ndarray
    recent_matrix: np.ndarray
    variable_names: list[str]
    focal_site_id: str
    focal_system_id: str
    focal_asset_id: str
    focal_node_id: str
    time_range_start: str | None
    time_range_end: str | None
    quality_summary: dict[str, Any]


@dataclass(frozen=True)
class StructuralIndicators:
    structural_drift_score: float
    relational_instability_score: float
    regime_distance: float
    coherence_loss_score: float
    graph_deformation_score: float
    coupling_instability_score: float
    mean_shift_score: float = 0.0
    covariance_shift_score: float = 0.0
    subspace_rotation_score: float = 0.0
    path_length_shift_score: float = 0.0


@dataclass(frozen=True)
class DecisionResult:
    interpreted_state: InterpretedState
    state: DecisionState
    confidence: ConfidenceLevel
    confidence_score: float
    reason: str


@dataclass(frozen=True)
class GraphState:
    adjacency: np.ndarray
    feature_names: list[str]
    density: float = 0.0
    avg_degree: float = 0.0
    l1_deformation: float = 0.0


@dataclass(frozen=True)
class GraphSnapshot:
    adjacency: np.ndarray
    node_count: int
    edge_count: int
    density: float
    mean_abs_weight: float
    spectral_radius: float
    laplacian_trace: float
    degree_centrality: dict[str, float]


class SIIResult(TypedDict):
    timestamp: str
    site_id: str
    asset_id: str
    state: DecisionState
    interpreted_state: InterpretedState
    confidence: ConfidenceLevel
    structural_drift_score: float
    relational_instability_score: float
    regime_distance: float
    coherence_score: float
    graph_deformation_score: float
    dominant_drivers: list[str]
    confidence_reasoning: list[str]
    explanation: str
    read_only: bool
    system_health: int
    attribution: dict[str, Any]
    regime_memory: dict[str, Any]
    risk_assessment: dict[str, Any]
    operator_guidance: dict[str, Any]
    causal_analysis: dict[str, Any]
    decision: dict[str, Any]
    data_quality_summary: dict[str, Any]
    experimental_analytics: dict[str, Any]
    structural_system_intelligence: dict[str, Any]


def ingestion_record_to_frame(record: CanonicalIngestionRecord) -> SIIFrame:
    """
    Convert canonical ingestion record into engine frame shape.
    """
    return SIIFrame(
        timestamp=str(record.timestamp),
        site_id=str(record.site_id),
        system_id=str(record.system_id),
        asset_id=str(record.asset_id),
        node_id=str(record.node_id),
        sensor_values=dict(record.variables),
        quality_metadata=record.quality_metadata,
        source_metadata=record.source_metadata,
        metadata=dict(record.metadata),
    )


def frame_to_ingestion_record(frame: SIIFrame) -> CanonicalIngestionRecord:
    """
    Convert engine frame shape into canonical ingestion record.
    """
    return CanonicalIngestionRecord(
        timestamp=str(frame.timestamp),
        site_id=str(frame.site_id),
        system_id=str(frame.system_id),
        asset_id=str(frame.asset_id),
        node_id=str(frame.node_id),
        variables={str(k): v for k, v in frame.sensor_values.items()},
        quality_metadata=frame.quality_metadata,
        source_metadata=frame.source_metadata,
        metadata=dict(frame.metadata),
    )
