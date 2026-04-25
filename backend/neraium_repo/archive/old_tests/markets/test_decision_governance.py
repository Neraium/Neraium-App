from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from neraium_core.engine_stages import (
    ActionGovernanceInput,
    DecisionValidityInput,
    FragilityInput,
    RiskGuidanceInput,
    evaluate_action_governance,
    evaluate_decision_validity,
    evaluate_fragility,
    evaluate_risk_guidance,
)
from neraium_core.markets.evidence.evidence_log import EvidenceLog
from neraium_core.markets.replay import run_signal_replay
from neraium_core.markets.signals.emission_control import EmissionControlConfig, SignalEmissionController
from neraium_core.markets.signals.signal_generator import generate_signal_for_asset


def _make_state(
    *,
    periods: int = 100,
    return_level: float = 0.003,
    vol_level: float = 0.010,
    advancer_ratio: float = 0.62,
    vix_change: float = -0.005,
    noise: float = 0.0,
) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=periods, freq="15min", tz="UTC")
    rng = np.random.default_rng(42)
    ret = return_level + rng.normal(0.0, noise, periods)
    vol = vol_level + np.abs(rng.normal(0.0, noise / 2 if noise else 0.0003, periods))
    return pd.DataFrame(
        {
            "ret_SPY": ret,
            "ret_QQQ": ret * 1.1,
            "ret_IWM": ret * 0.9,
            "vol_SPY": vol,
            "vol_QQQ": vol * 1.05,
            "vol_IWM": vol * 1.15,
            "advancer_ratio": np.full(periods, advancer_ratio),
            "vix_change": np.full(periods, vix_change),
            "spy_qqq_corr": np.full(periods, 0.8),
            "spy_iwm_corr": np.full(periods, 0.75),
        },
        index=idx,
    )


def test_phase1_valid_stable_state() -> None:
    result = evaluate_decision_validity(
        DecisionValidityInput(
            asset="SPY",
            timeframe="15m",
            regime="trend",
            state="stable",
            structural_drift_score=0.24,
            instability_score=0.20,
            coherence_score=0.82,
            confidence_score=0.78,
            data_quality_score=0.95,
            persistence_score=0.74,
            breadth_score=0.61,
            sample_count=100,
            drift_components={"correlation_geometry": 0.22, "lag_relationships": 0.18},
        )
    )
    assert result.is_valid
    assert result.action_permission == "ACT"
    assert not result.abstain
    assert result.justification


def test_phase1_invalid_unstable_state() -> None:
    result = evaluate_decision_validity(
        DecisionValidityInput(
            asset="SPY",
            timeframe="15m",
            regime="high_vol_transition",
            state="unstable",
            structural_drift_score=0.84,
            instability_score=0.88,
            coherence_score=0.31,
            confidence_score=0.42,
            data_quality_score=0.93,
            persistence_score=0.40,
            breadth_score=0.39,
            vix_change=0.04,
            sample_count=100,
        )
    )
    assert not result.is_valid
    assert result.abstain
    assert result.action_permission in {"REDUCE", "AVOID"}
    assert result.invalidating_factors


def test_phase1_low_data_abstention() -> None:
    result = evaluate_decision_validity(
        DecisionValidityInput(
            asset="SPY",
            timeframe="15m",
            regime="trend",
            state="stable",
            structural_drift_score=0.22,
            instability_score=0.18,
            coherence_score=0.74,
            confidence_score=0.70,
            data_quality_score=0.35,
            persistence_score=0.70,
            sample_count=22,
        )
    )
    assert result.abstain
    assert result.action_permission == "AVOID"


def test_phase1_low_confidence_abstention() -> None:
    result = evaluate_decision_validity(
        DecisionValidityInput(
            asset="SPY",
            timeframe="15m",
            regime="trend",
            state="stable",
            structural_drift_score=0.28,
            instability_score=0.24,
            coherence_score=0.79,
            confidence_score=0.33,
            data_quality_score=0.95,
            persistence_score=0.55,
            sample_count=100,
        )
    )
    assert result.abstain
    assert "confidence" in " ".join(result.invalidating_factors)


def test_phase1_transition_state_suppression() -> None:
    result = evaluate_decision_validity(
        DecisionValidityInput(
            asset="SPY",
            timeframe="15m",
            regime="risk_off_transition",
            state="transitioning",
            structural_drift_score=0.72,
            instability_score=0.64,
            coherence_score=0.59,
            confidence_score=0.61,
            data_quality_score=0.93,
            persistence_score=0.62,
            breadth_score=0.41,
            vix_change=0.03,
            sample_count=100,
        )
    )
    assert result.transition_state == "transition"
    assert result.action_permission in {"WAIT", "REDUCE", "AVOID"}


def test_phase2_action_governance_differentiates_action_types() -> None:
    result = evaluate_action_governance(
        ActionGovernanceInput(
            regime="trend",
            state="stable",
            action_permission="ACT",
            validity_score=0.78,
            confidence_score=0.74,
            fragility_score=0.32,
            structural_drift_score=0.28,
            instability_score=0.22,
            transition_state="settled",
            abstain=False,
        )
    )
    assert result.best_action in {"breakout_entry", "trend_continuation", "add_to_position"}
    assert result.action_quality["breakout_entry"] > result.action_quality["mean_reversion"]


def test_phase2_unstable_transitions_block_aggressive_actions() -> None:
    result = evaluate_action_governance(
        ActionGovernanceInput(
            regime="high_vol_transition",
            state="transitioning",
            action_permission="AVOID",
            validity_score=0.31,
            confidence_score=0.46,
            fragility_score=0.81,
            structural_drift_score=0.74,
            instability_score=0.77,
            transition_state="transition",
            abstain=True,
        )
    )
    blocked = {item["action_type"] for item in result.blocked_actions}
    allowed = {item["action_type"] for item in result.allowed_actions}
    assert "breakout_entry" in blocked
    assert "trend_continuation" in blocked
    assert {"reduce_position", "exit_position", "no_action"} & allowed


def test_phase3_fragility_outputs_present() -> None:
    result = evaluate_fragility(
        FragilityInput(
            regime="trend",
            state="stable",
            drift_score=0.18,
            instability_score=0.17,
            coherence_score=0.84,
            confidence_score=0.78,
            data_quality_score=0.95,
            validity_score=0.80,
            transition_state="settled",
            breadth_score=0.62,
        )
    )
    assert result.fragility_state == "ROBUST"
    assert result.invalidation_conditions
    assert result.edge_dependencies


def test_phase3_fragile_unstable_state() -> None:
    result = evaluate_fragility(
        FragilityInput(
            regime="liquidity_stress",
            state="unstable",
            drift_score=0.81,
            instability_score=0.86,
            coherence_score=0.34,
            confidence_score=0.41,
            data_quality_score=0.70,
            validity_score=0.28,
            transition_state="transition",
            breadth_score=0.38,
            vix_change=0.05,
            invalidating_factors=["transition pressure is too elevated"],
        )
    )
    assert result.fragility_state == "FRAGILE"
    assert "transition" in " ".join(result.fragility_sources)


def test_phase4_cooldown_and_duplicate_suppression() -> None:
    controller = SignalEmissionController(
        EmissionControlConfig(cooldown_frames=3, duplicate_tolerance=0.05, warmup_bars=10)
    )
    first = controller.evaluate(
        "SPY:15m",
        frame_index=10,
        sample_count=10,
        confidence=0.68,
        action_permission="WAIT",
        best_action="hold_only",
        validity_score=0.58,
        market_state="trend",
        transition_state="settled",
        abstain=True,
    )
    assert first.emit
    controller.mark_emitted(
        "SPY:15m",
        frame_index=10,
        action_permission="WAIT",
        best_action="hold_only",
        validity_score=0.58,
        market_state="trend",
        transition_state="settled",
    )
    second = controller.evaluate(
        "SPY:15m",
        frame_index=11,
        sample_count=11,
        confidence=0.69,
        action_permission="WAIT",
        best_action="hold_only",
        validity_score=0.59,
        market_state="trend",
        transition_state="settled",
        abstain=True,
    )
    assert not second.emit
    assert second.cooldown_status in {"duplicate", "cooldown"}


def test_phase4_hysteresis_prevents_flip_flopping() -> None:
    controller = SignalEmissionController(EmissionControlConfig(hysteresis_margin=0.08))
    controller.mark_emitted(
        "SPY:15m",
        frame_index=20,
        action_permission="WAIT",
        best_action="hold_only",
        validity_score=0.54,
        market_state="trend",
        transition_state="settled",
    )
    stabilized = controller.stabilize_permission("SPY:15m", "ACT", 0.59)
    assert stabilized == "WAIT"


def test_phase5_compact_output_shape_and_reason_presence() -> None:
    signal = generate_signal_for_asset("SPY", "15m", _make_state(), 0.97)
    assert signal is not None
    assert signal.trader_output is not None
    payload = signal.trader_output.model_dump(mode="json")
    assert payload["ticker"] == "SPY"
    assert payload["one_line_reason"]
    assert "action_permission" in payload


def test_phase5_missing_field_resilience() -> None:
    signal = generate_signal_for_asset("SPY", "15m", _make_state(advancer_ratio=0.5, vix_change=0.0), 0.85)
    assert signal is not None
    assert signal.trader_output is not None
    assert isinstance(signal.trader_output.invalidation_conditions, list)


def test_phase6_exposure_guidance() -> None:
    robust = evaluate_risk_guidance(
        RiskGuidanceInput(
            action_permission="ACT",
            validity_score=0.80,
            confidence_score=0.76,
            fragility_score=0.24,
            transition_state="settled",
            data_quality_score=0.94,
            regime_stability_score=0.82,
        )
    )
    fragile = evaluate_risk_guidance(
        RiskGuidanceInput(
            action_permission="REDUCE",
            validity_score=0.46,
            confidence_score=0.50,
            fragility_score=0.74,
            transition_state="transition",
            data_quality_score=0.90,
            regime_stability_score=0.44,
        )
    )
    invalid = evaluate_risk_guidance(
        RiskGuidanceInput(
            action_permission="AVOID",
            validity_score=0.20,
            confidence_score=0.30,
            fragility_score=0.82,
            transition_state="transition",
            data_quality_score=0.70,
            regime_stability_score=0.22,
        )
    )
    assert robust.exposure_guidance == "FULL"
    assert fragile.exposure_guidance in {"PROBE", "REDUCED"}
    assert invalid.exposure_guidance == "NO_EXPOSURE"


def test_phase7_replay_sample_run_and_output_shape(tmp_path: Path) -> None:
    evidence = EvidenceLog(tmp_path / "evidence.jsonl")
    rows = run_signal_replay(
        Path("neraium_core/markets/sample_data"),
        evidence,
        timeframe="15m",
        csv_output_path=tmp_path / "replay.csv",
    )
    assert rows
    assert (tmp_path / "replay.csv").exists()
    assert {"ticker", "action_permission", "best_action", "cooldown_status"} <= rows[0].keys()


def test_phase7_long_sequence_resilience_with_malformed_intervals(tmp_path: Path) -> None:
    data_dir = tmp_path / "sample"
    frame_dir = data_dir / "15m"
    frame_dir.mkdir(parents=True)
    idx = pd.date_range("2026-01-01", periods=90, freq="15min", tz="UTC").tolist()
    idx[10] = idx[9]
    prices = np.linspace(100, 104, len(idx))
    assets = ["SPY", "QQQ", "IWM", "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "VIX", "US2Y", "US10Y", "DXY", "CRUDE", "GOLD"]
    for asset in assets:
        pd.DataFrame({"timestamp": idx, "close": prices}).to_csv(frame_dir / f"{asset.lower()}.csv", index=False)
    evidence = EvidenceLog(tmp_path / "evidence2.jsonl")
    rows = run_signal_replay(data_dir, evidence, timeframe="15m")
    assert isinstance(rows, list)
