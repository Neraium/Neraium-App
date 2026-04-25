from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import numpy as np

from neraium_core.geometry import structural_drift


class RegimeMutationContext(Protocol):
    regime_baselines: dict[str, dict[str, object]]
    baseline_locked: bool
    baseline_adaptation_alpha: float
    transition_aware_enabled: bool
    _rolling_baseline_corr: np.ndarray | None
    _stable_manifold_corr: np.ndarray | None
    _baseline_set_at: str | None
    _baseline_coverage_samples: int

    def _persist_regime_state(self) -> None: ...


@dataclass(frozen=True)
class RegimeMutationInput:
    regime_name: str | None
    signature: np.ndarray
    corr_recent: np.ndarray
    baseline_window: int
    valid_signal_count: int
    transition_state: str
    transition_pressure: float
    decision_interpreted_state: str | None
    apply_regime_library_mutation: bool = True
    apply_rolling_baseline_mutation: bool = True


@dataclass(frozen=True)
class RegimeMutationResult:
    regime_drift: float
    regime_memory_state: dict[str, object]
    persisted_regime_state: bool
    rolling_baseline_updated: bool
    stable_manifold_updated: bool


def mutate_regime_state(
    context: RegimeMutationContext,
    stage_input: RegimeMutationInput,
) -> RegimeMutationResult:
    regime_drift = 0.0
    persisted_regime_state = False

    if stage_input.apply_regime_library_mutation and stage_input.regime_name is not None:
        regime_name = stage_input.regime_name
        if regime_name not in context.regime_baselines:
            context.regime_baselines[regime_name] = {
                "signature": stage_input.signature.tolist(),
                "correlation": stage_input.corr_recent.tolist(),
                "count": 1,
            }
            persisted_regime_state = True
        else:
            regime_corr = np.asarray(context.regime_baselines[regime_name]["correlation"], dtype=float)
            if regime_corr.shape == stage_input.corr_recent.shape:
                regime_drift = float(structural_drift(stage_input.corr_recent, regime_corr, norm="fro"))
                alpha = 0.88
                updated = alpha * regime_corr + (1.0 - alpha) * stage_input.corr_recent
                context.regime_baselines[regime_name]["correlation"] = updated.tolist()
                regime_count = int(context.regime_baselines[regime_name].get("count", 0)) + 1
                context.regime_baselines[regime_name]["count"] = regime_count
                persisted_regime_state = (regime_count % 16) == 0
            else:
                context.regime_baselines[regime_name] = {
                    "signature": stage_input.signature.tolist(),
                    "correlation": stage_input.corr_recent.tolist(),
                    "count": 1,
                }
                regime_drift = 0.0
                persisted_regime_state = True

        if persisted_regime_state:
            context._persist_regime_state()

    rolling_baseline_updated = False
    stable_manifold_updated = False
    transition_blocks_baseline = (
        context.transition_aware_enabled
        and stage_input.transition_state != "WARMUP"
        and (
            stage_input.transition_state != "NONE"
            or float(stage_input.transition_pressure) >= 0.85
        )
    )
    if (
        stage_input.apply_rolling_baseline_mutation
        and stage_input.valid_signal_count >= 2
        and not context.baseline_locked
        and stage_input.decision_interpreted_state in {"NOMINAL_STRUCTURE", "COUPLING_INSTABILITY_OBSERVED"}
        and not transition_blocks_baseline
    ):
        if context._rolling_baseline_corr is None or context._rolling_baseline_corr.shape != stage_input.corr_recent.shape:
            context._rolling_baseline_corr = np.array(stage_input.corr_recent, dtype=float, copy=True)
            context._baseline_set_at = datetime.now(timezone.utc).isoformat()
            context._baseline_coverage_samples = stage_input.baseline_window
        else:
            alpha = context.baseline_adaptation_alpha
            context._rolling_baseline_corr = alpha * context._rolling_baseline_corr + (1.0 - alpha) * stage_input.corr_recent
        rolling_baseline_updated = True

        if context._stable_manifold_corr is None or context._stable_manifold_corr.shape != stage_input.corr_recent.shape:
            context._stable_manifold_corr = np.array(stage_input.corr_recent, dtype=float, copy=True)
        else:
            manifold_alpha = min(0.985, max(0.90, context.baseline_adaptation_alpha + 0.03))
            context._stable_manifold_corr = (
                manifold_alpha * context._stable_manifold_corr + (1.0 - manifold_alpha) * stage_input.corr_recent
            )
        stable_manifold_updated = True

    regime_memory_state = {
        "regime_name": stage_input.regime_name,
        "library_size": len(getattr(context, "regime_signatures", [])),
        "baseline_count": (
            int(context.regime_baselines.get(stage_input.regime_name, {}).get("count", 0))
            if stage_input.regime_name
            else None
        ),
    }

    return RegimeMutationResult(
        regime_drift=regime_drift,
        regime_memory_state=regime_memory_state,
        persisted_regime_state=persisted_regime_state,
        rolling_baseline_updated=rolling_baseline_updated,
        stable_manifold_updated=stable_manifold_updated,
    )
