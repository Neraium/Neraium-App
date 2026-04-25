from __future__ import annotations

from typing import Any, Mapping

from .calibration import SIICalibrationConfig
from .config import SIIConfig
from .engine import SIIEngine
from .ingestion import canonical_records_from_payloads
from .reporting import (
    STRUCTURAL_SIGNAL_FIELDS,
    compute_structural_signal_ranking,
    compute_structural_temporal_validation,
    evaluate_structural_risk_decision_policy,
)


def _raw_structural_magnitudes_from_latest(result: Mapping[str, Any] | None) -> dict[str, float]:
    latest = result if isinstance(result, Mapping) else {}
    structural_state = latest.get("structural_state") if isinstance(latest.get("structural_state"), Mapping) else {}

    out: dict[str, float] = {}
    for field in STRUCTURAL_SIGNAL_FIELDS:
        source = latest.get(field, structural_state.get(field, 0.0))
        try:
            out[field] = float(source)
        except (TypeError, ValueError):
            out[field] = 0.0
    return out


def run_structural_pipeline(data: list[dict[str, Any]], config: Mapping[str, Any] | SIIConfig | None = None) -> dict[str, Any]:
    """
    Thin end-to-end structural orchestration entrypoint.

    Execution order:
    1) ingest ordered telemetry payloads
    2) compute structural state sequence via SII engine
    3) compute temporal validation diagnostics
    4) rank structural signals from validation outputs
    5) evaluate structural risk decision policy
    """
    if isinstance(config, SIIConfig):
        sii_config = config
    elif isinstance(config, Mapping):
        sii_config = SIIConfig(**dict(config))
    else:
        sii_config = SIIConfig()

    records = canonical_records_from_payloads(
        data,
        source_type="payload",
        source_name="run_structural_pipeline",
    )
    engine = SIIEngine(config=sii_config)
    frame_results = engine.process_records(records)

    validation_results = compute_structural_temporal_validation(
        frame_results,
        lead_window=int(
            getattr(
                sii_config,
                "lead_window",
                getattr(sii_config, "structural_temporal_lead_window", 3),
            )
        ),
    )
    calibration_source: Mapping[str, Any] | None = None
    if isinstance(config, Mapping):
        calibration_source = config
    elif isinstance(config, SIIConfig):
        calibration_source = {
            "lead_window": getattr(config, "lead_window", 3),
            "min_lead_recall": getattr(config, "min_lead_recall", 0.3),
            "min_lead_precision": getattr(config, "min_lead_precision", 0.3),
            "top_k_rank_window": getattr(config, "top_k_rank_window", 2),
            "spike_threshold_multiplier": getattr(config, "spike_threshold_multiplier", 1.0),
            "decision_thresholds": getattr(config, "decision_thresholds", {"default": 1.0}),
        }
    calibration = SIICalibrationConfig.from_obj(calibration_source)
    signal_ranking = compute_structural_signal_ranking(validation_results, config=calibration)

    latest = frame_results[-1] if frame_results else {}
    decision_output = evaluate_structural_risk_decision_policy(
        signal_ranking=signal_ranking,
        raw_structural_magnitudes=_raw_structural_magnitudes_from_latest(latest),
        min_lead_recall=float(getattr(sii_config, "structural_policy_min_lead_recall", 0.3)),
        min_lead_precision=float(getattr(sii_config, "structural_policy_min_lead_precision", 0.3)),
        max_eligible_rank=int(getattr(sii_config, "structural_policy_max_eligible_rank", 2)),
        config=calibration,
    )

    return {
        "structural_state": dict(latest.get("structural_state") or {}),
        "validation_results": validation_results,
        "signal_ranking": signal_ranking,
        "decision_output": decision_output,
        "frame_results": frame_results,
    }
