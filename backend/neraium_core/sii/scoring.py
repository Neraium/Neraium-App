from __future__ import annotations

from dataclasses import dataclass

from .types import StructuralIndicators


@dataclass(frozen=True)
class ComponentScores:
    structural_departure: float
    relational_instability: float
    graph_deformation: float
    regime_distance: float
    coherence_loss: float
    coupling_instability: float

    def as_dict(self) -> dict[str, float]:
        return {
            "structural_departure": float(self.structural_departure),
            "relational_instability": float(self.relational_instability),
            "graph_deformation": float(self.graph_deformation),
            "regime_distance": float(self.regime_distance),
            "coherence_loss": float(self.coherence_loss),
            "coupling_instability": float(self.coupling_instability),
        }


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, x)))


def component_scores(
    *,
    geometry_departure: float,
    graph_departure: float,
    regime_distance: float,
    graph_snapshot: object,
    geometry_snapshot: object,
) -> ComponentScores:
    structural = _clip(float(geometry_departure))
    graph_def = _clip(float(graph_departure))
    regime = _clip(float(regime_distance))
    coherence_score = float(getattr(geometry_snapshot, "coherence_score", 1.0))
    coherence_loss = _clip(1.0 - coherence_score)
    relational = _clip(0.70 * structural + 0.30 * coherence_loss)
    coupling = _clip(0.50 * graph_def + 0.30 * relational + 0.20 * coherence_loss)
    return ComponentScores(
        structural_departure=structural,
        relational_instability=relational,
        graph_deformation=graph_def,
        regime_distance=regime,
        coherence_loss=coherence_loss,
        coupling_instability=coupling,
    )


@dataclass(frozen=True)
class StructuralScoringModel:
    # Regime and geometry departures are primary; graph/coherence support interpretation.
    w_structural: float = 0.24
    w_relational: float = 0.16
    w_graph: float = 0.16
    w_regime: float = 0.28
    w_coherence: float = 0.10
    w_coupling: float = 0.08

    def composite_departure_score(self, indicators: ComponentScores | StructuralIndicators) -> float:
        # Accept both ComponentScores and StructuralIndicators-compatible objects.
        structural = float(
            getattr(indicators, "structural_departure", getattr(indicators, "structural_drift_score", 0.0))
        )
        relational = float(
            getattr(indicators, "relational_instability", getattr(indicators, "relational_instability_score", 0.0))
        )
        regime = float(getattr(indicators, "regime_distance", 0.0))
        graph_def = float(
            getattr(indicators, "graph_deformation", getattr(indicators, "graph_deformation_score", 0.0))
        )
        coherence_loss = float(
            getattr(indicators, "coherence_loss", getattr(indicators, "coherence_loss_score", 0.0))
        )
        coupling = float(
            getattr(indicators, "coupling_instability", getattr(indicators, "coupling_instability_score", 0.0))
        )
        score = (
            self.w_structural * structural
            + self.w_relational * relational
            + self.w_graph * graph_def
            + self.w_regime * regime
            + self.w_coherence * coherence_loss
            + self.w_coupling * coupling
        )
        return _clip(float(score), 0.0, 1.0)


def composite_structural_score(scores: ComponentScores | dict[str, float]) -> float:
    model = StructuralScoringModel()
    if isinstance(scores, ComponentScores):
        return model.composite_departure_score(scores)
    return model.composite_departure_score(
        ComponentScores(
            structural_departure=float(scores.get("structural_departure", 0.0)),
            relational_instability=float(scores.get("relational_instability", 0.0)),
            graph_deformation=float(scores.get("graph_deformation", 0.0)),
            regime_distance=float(scores.get("regime_distance", 0.0)),
            coherence_loss=float(scores.get("coherence_loss", 0.0)),
            coupling_instability=float(scores.get("coupling_instability", 0.0)),
        )
    )

