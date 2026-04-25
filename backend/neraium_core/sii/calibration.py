from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from .errors import SIIIOError


@dataclass(frozen=True)
class SIICalibrationConfig:
    lead_window: int = 3
    min_lead_recall: float = 0.3
    min_lead_precision: float = 0.3
    top_k_rank_window: int = 2
    spike_threshold_multiplier: float = 1.0
    decision_thresholds: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.lead_window < 1:
            raise ValueError("lead_window must be >= 1")
        if self.top_k_rank_window < 1:
            raise ValueError("top_k_rank_window must be >= 1")
        if self.spike_threshold_multiplier <= 0.0:
            raise ValueError("spike_threshold_multiplier must be > 0")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision_thresholds"] = dict(self.decision_thresholds or {"default": 1.0})
        return payload

    @staticmethod
    def from_obj(config: Mapping[str, Any] | "SIICalibrationConfig" | None) -> "SIICalibrationConfig":
        if isinstance(config, SIICalibrationConfig):
            return config
        if isinstance(config, Mapping):
            return SIICalibrationConfig(
                lead_window=int(config.get("lead_window", 3)),
                min_lead_recall=float(config.get("min_lead_recall", 0.3)),
                min_lead_precision=float(config.get("min_lead_precision", 0.3)),
                top_k_rank_window=int(config.get("top_k_rank_window", 2)),
                spike_threshold_multiplier=float(config.get("spike_threshold_multiplier", 1.0)),
                decision_thresholds=dict(config.get("decision_thresholds") or {"default": 1.0}),
            )
        return SIICalibrationConfig()


def derive_calibration_from_validation(validation_results: Mapping[str, Any]) -> dict[str, Any]:
    signals = validation_results.get("signals")
    if not isinstance(signals, dict) or not signals:
        return SIICalibrationConfig().to_dict()

    transition_count = max(1, int(validation_results.get("transition_count") or 0))
    sample_count = max(1, int(validation_results.get("sample_count") or 0))
    lead_recalls: list[float] = []
    lead_precisions: list[float] = []
    spike_threshold_ratios: list[float] = []
    decision_thresholds: dict[str, float] = {}
    leading_candidates = 0

    for signal, raw_metrics in signals.items():
        metrics = raw_metrics if isinstance(raw_metrics, Mapping) else {}
        lead_recall = float(metrics.get("lead_recall") or 0.0)
        lead_precision = float(metrics.get("lead_precision") or 0.0)
        mean_abs_change = abs(float(metrics.get("mean_abs_change") or 0.0))
        spike_threshold = abs(float(metrics.get("spike_threshold") or 0.0))
        spike_steps = metrics.get("spike_steps")
        spike_count = len(spike_steps) if isinstance(spike_steps, list) else 0
        spike_ratio = spike_count / max(1, transition_count)
        if lead_recall > 0.0:
            lead_recalls.append(lead_recall)
        if lead_precision > 0.0:
            lead_precisions.append(lead_precision)
        if mean_abs_change > 0.0 and spike_threshold > 0.0:
            spike_threshold_ratios.append(spike_threshold / mean_abs_change)
        if lead_recall >= 0.2:
            leading_candidates += 1

        decision_multiplier = 1.0
        if spike_ratio > 2.0:
            decision_multiplier = 1.25
        elif spike_ratio < 0.5 and lead_recall > 0.0:
            decision_multiplier = 0.9
        decision_thresholds[str(signal)] = round(decision_multiplier, 6)

    lead_window = max(1, min(6, int(round(sample_count / max(2, transition_count * 4)))))
    min_lead_recall = round(sum(lead_recalls) / max(1, len(lead_recalls)), 6)
    min_lead_precision = round(sum(lead_precisions) / max(1, len(lead_precisions)), 6)
    spike_threshold_multiplier = round(sum(spike_threshold_ratios) / max(1, len(spike_threshold_ratios)), 6)
    spike_threshold_multiplier = min(3.0, max(0.5, spike_threshold_multiplier))
    top_k_rank_window = min(5, max(1, leading_candidates))
    decision_thresholds["default"] = 1.0

    return SIICalibrationConfig(
        lead_window=lead_window,
        min_lead_recall=min(0.95, max(0.05, min_lead_recall)),
        min_lead_precision=min(0.95, max(0.05, min_lead_precision)),
        top_k_rank_window=top_k_rank_window,
        spike_threshold_multiplier=spike_threshold_multiplier,
        decision_thresholds=decision_thresholds,
    ).to_dict()


def save_config(config: Mapping[str, Any] | SIICalibrationConfig, path: str | Path) -> None:
    payload = SIICalibrationConfig.from_obj(config).to_dict()
    output_path = Path(path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        raise SIIIOError(f"Failed to save calibration config: {output_path}") from exc


def load_config(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SIIIOError(f"Failed to load calibration config: {input_path}") from exc
    return SIICalibrationConfig.from_obj(payload).to_dict()
