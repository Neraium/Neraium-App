from __future__ import annotations

import numpy as np

from neraium_core.sii.config import SIIConfig
from neraium_core.sii.dependence import estimate_dependence
from neraium_core.sii.dynamic_graph import compute_dynamic_graph_metrics
from neraium_core.sii.geometry_layer import build_geometry_state
from neraium_core.sii.hypothesis_scoring import score_structural_hypothesis
from neraium_core.sii.regime_model import RegimeModel, RegimeObservation
from neraium_core.sii.risk import assess_forward_risk


def test_dependence_backends_coexist_and_partial_runs() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(size=200)
    y = 0.75 * x + rng.normal(scale=0.2, size=200)
    z = rng.normal(size=200)
    w = np.column_stack([x, y, z])

    pearson = estimate_dependence(w, backend="pearson").matrix
    spearman = estimate_dependence(w, backend="spearman").matrix
    partial = estimate_dependence(w, backend="partial").matrix

    assert pearson.shape == spearman.shape == partial.shape == (3, 3)
    assert float(abs(spearman[0, 1])) > 0.5
    assert np.all(np.isfinite(partial))


def test_geometry_layer_accepts_dependence_backend() -> None:
    rng = np.random.default_rng(9)
    b = rng.normal(size=(60, 4))
    r = b.copy()
    r[:, 1] = np.tanh(r[:, 0] * 1.6) + rng.normal(scale=0.1, size=60)

    features = build_geometry_state(b, r, dependence_backend="spearman", dependence_lag=1)
    assert features.recent_corr.shape == (4, 4)
    assert features.structural_drift >= 0.0


def test_regime_model_emits_confidence_and_uncertainty(tmp_path) -> None:
    cfg = SIIConfig(regime_store_path=str(tmp_path / "regimes.json"))
    model = RegimeModel(config=cfg)

    g = np.array([0.1, 0.2, 0.3], dtype=float)
    gr = np.array([0.2, 0.1], dtype=float)
    first = model.observe(RegimeObservation(geometry_signature=g, graph_signature=gr, feature_names=["a"]))
    second = model.observe(RegimeObservation(geometry_signature=g + 0.01, graph_signature=gr + 0.01, feature_names=["a"]))

    assert 0.0 <= first.regime_confidence <= 1.0
    assert 0.0 <= second.regime_uncertainty <= 1.0


def test_transition_risk_reports_hazard_uncertainty() -> None:
    history = [0.2, 0.25, 0.31, 0.4, 0.52, 0.61, 0.72, 0.81]
    out = assess_forward_risk(
        composite_history=history,
        structural_score=0.74,
        regime_score=0.62,
        coupling_score=0.66,
    )
    assert "hazard" in out.evidence
    assert "uncertainty" in out.evidence
    assert out.projected_score >= out.risk_score - 0.2


def test_dynamic_graph_and_hypothesis_scoring() -> None:
    prev = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=float)
    curr = np.array([[0, 1, 1], [1, 0, 0], [1, 0, 0]], dtype=float)
    dg = compute_dynamic_graph_metrics(
        current_adj=curr,
        prev_adj=prev,
        current_degree_centrality={"a": 1.0, "b": 0.5, "c": 0.5},
        prev_degree_centrality={"a": 0.5, "b": 1.0, "c": 0.5},
        structural_drift=0.6,
        coupling_score=0.5,
    )
    assert dg.edge_birth_rate > 0.0
    assert 0.0 <= dg.fragility_score <= 1.0

    hypo = score_structural_hypothesis(
        leading_sensor="pump_pressure",
        localization=0.8,
        persistence=0.7,
        subsystem_coherence=0.6,
        robustness=0.65,
        multi_signal_agreement=0.75,
    )
    assert "pump_pressure" in hypo.hypothesis
    assert 0.0 <= hypo.confidence <= 1.0
