from __future__ import annotations

from typing import TypedDict


class EngineStageBoundary(TypedDict):
    stage: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    risk: str
    extraction_candidate: bool


def structural_engine_stage_groups() -> list[EngineStageBoundary]:
    return [
        {
            "stage": "ingress_and_history_buffers",
            "inputs": ("frame", "sensor_schema", "history_ring"),
            "outputs": ("vector", "history_matrix", "history_timestamps"),
            "risk": "low",
            "extraction_candidate": True,
        },
        {
            "stage": "warmup_and_default_payload",
            "inputs": ("frame",),
            "outputs": ("result_payload",),
            "risk": "low",
            "extraction_candidate": True,
        },
        {
            "stage": "representation_and_data_quality",
            "inputs": ("history_matrix", "history_timestamps"),
            "outputs": ("baseline_window", "recent_window", "data_quality", "temporal_features"),
            "risk": "medium",
            "extraction_candidate": True,
        },
        {
            "stage": "score_computation",
            "inputs": ("base_components", "raw_components", "confidence_factors"),
            "outputs": ("component_confidence", "weights_for_composite", "composite_score"),
            "risk": "low",
            "extraction_candidate": True,
        },
        {
            "stage": "analytics_packaging",
            "inputs": ("analytics", "unavailable_fallback_payload"),
            "outputs": ("experimental_analytics",),
            "risk": "low",
            "extraction_candidate": True,
        },
        {
            "stage": "regime_and_baseline_mutation",
            "inputs": ("regime_name", "corr_recent", "decision_state", "baseline_lock"),
            "outputs": ("regime_memory", "rolling_baseline_state"),
            "risk": "high",
            "extraction_candidate": True,
        },
        {
            "stage": "scoring_preparation_and_correlation_gating",
            "inputs": ("z_baseline", "z_recent", "valid_mask", "valid_signal_count"),
            "outputs": ("prepared_windows", "stage_features", "correlation_readiness"),
            "risk": "low",
            "extraction_candidate": True,
        },
        {
            "stage": "decision_projection_and_explanation",
            "inputs": ("scores", "causal_analysis", "history_state"),
            "outputs": ("decision", "risk_assessment", "explanation", "product_flags"),
            "risk": "medium",
            "extraction_candidate": True,
        },
    ]
