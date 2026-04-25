from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from .types import StructuralCoherenceState


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _squash_positive(value: float, scale: float = 1.0) -> float:
    v = max(0.0, float(value))
    s = max(1e-6, float(scale))
    return float(v / (v + s))


@dataclass(frozen=True)
class LawfulStructuralState:
    """
    Canonical structural model for the engine.

    This object is the center of the runtime and stores raw structural
    magnitudes. Any bounded [0,1] views are explicitly downstream.
    """

    operator_deformation_energy: float
    residual_energy: float
    regime_distance: float
    coherence_margin_raw: float
    structural_drift_magnitude: float

    @property
    def operator_drift(self) -> float:
        # Compatibility alias for older call sites.
        return float(self.operator_deformation_energy)

    @property
    def residual_structure(self) -> float:
        # Compatibility alias for older call sites.
        return float(self.residual_energy)

    @property
    def regime_transition_pressure(self) -> float:
        # Compatibility alias for older call sites.
        return float(self.regime_distance)

    @property
    def coherence_margin(self) -> float:
        # Compatibility alias for older call sites.
        return float(self.coherence_margin_raw)

    @property
    def structural_drift(self) -> float:
        # Compatibility alias for older call sites.
        return float(self.structural_drift_magnitude)

    def as_dict(self) -> dict[str, float]:
        return {
            "operator_deformation_energy": float(self.operator_deformation_energy),
            "residual_energy": float(self.residual_energy),
            "regime_distance": float(self.regime_distance),
            "coherence_margin_raw": float(self.coherence_margin_raw),
            "structural_drift_magnitude": float(self.structural_drift_magnitude),
        }


def build_lawful_structural_state(state: StructuralCoherenceState) -> LawfulStructuralState:
    indicators = state.indicators
    raw = state.raw_components

    raw_structural = float(raw.get("structural_drift", indicators.structural_drift_score))
    raw_relational = float(raw.get("relational_instability", indicators.relational_instability_score))
    raw_graph = float(raw.get("graph_deformation", indicators.graph_deformation_score))
    operator_energy = sqrt(raw_structural * raw_structural + raw_relational * raw_relational + raw_graph * raw_graph)

    raw_mean_shift = float(raw.get("mean_shift", indicators.mean_shift_score))
    raw_cov_shift = float(raw.get("covariance_shift", indicators.covariance_shift_score))
    raw_subspace_shift = float(raw.get("subspace_rotation", indicators.subspace_rotation_score))
    raw_path_shift = float(raw.get("path_length_shift", indicators.path_length_shift_score))
    residual_energy = sqrt(
        raw_mean_shift * raw_mean_shift
        + raw_cov_shift * raw_cov_shift
        + raw_subspace_shift * raw_subspace_shift
        + raw_path_shift * raw_path_shift
    )

    regime_distance = float(state.regime.get("distance", raw.get("regime_distance", indicators.regime_distance)))
    regime_uncertainty = float(state.regime.get("uncertainty", 0.0))
    regime_pressure_energy = max(0.0, regime_distance) + 0.20 * max(0.0, regime_uncertainty)

    coherence_margin_raw = float(state.coherence_score) - max(operator_energy, regime_pressure_energy, residual_energy)
    coherence_tension_energy = max(0.0, -coherence_margin_raw)

    drift_energy = sqrt(
        operator_energy * operator_energy
        + residual_energy * residual_energy
        + regime_pressure_energy * regime_pressure_energy
        + coherence_tension_energy * coherence_tension_energy
    )

    return LawfulStructuralState(
        operator_deformation_energy=float(operator_energy),
        residual_energy=float(residual_energy),
        regime_distance=float(regime_pressure_energy),
        coherence_margin_raw=float(coherence_margin_raw),
        structural_drift_magnitude=float(drift_energy),
    )


def derived_signal_view(lawful: LawfulStructuralState) -> dict[str, Any]:
    """
    Build a secondary bounded interface layer from the raw structural state.
    """
    operator_drift_score = _clip01(_squash_positive(lawful.operator_deformation_energy, scale=sqrt(3.0)))
    residual_structure_score = _clip01(_squash_positive(lawful.residual_energy, scale=2.0))
    regime_transition_pressure_score = _clip01(_squash_positive(lawful.regime_distance, scale=0.7))
    coherence_tension = _clip01(max(0.0, -float(lawful.coherence_margin_raw)))
    structural_drift_score = _clip01(_squash_positive(lawful.structural_drift_magnitude, scale=2.0))

    composite_instability = _clip01(
        0.45 * float(structural_drift_score)
        + 0.35 * float(regime_transition_pressure_score)
        + 0.20 * float(coherence_tension)
    )
    return {
        "operator_drift_score": float(operator_drift_score),
        "residual_structure_score": float(residual_structure_score),
        "regime_transition_pressure_score": float(regime_transition_pressure_score),
        "structural_drift_score": float(structural_drift_score),
        "composite_instability": float(composite_instability),
        "coherence_tension": float(coherence_tension),
    }
