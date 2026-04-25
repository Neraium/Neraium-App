from __future__ import annotations

from neraium_core.markets.regime.confidence import score_confidence
from neraium_core.markets.regime.interpretive_gate import should_emit_signal
from neraium_core.markets.regime.regime_rules import classify_regime


def test_regime_and_confidence_and_gate() -> None:
    regime, contradiction = classify_regime(0.8, 0.8, 0.3, 0.05, -0.01)
    assert regime.value in {"risk_off_transition", "liquidity_stress", "high_vol_transition"}
    conf = score_confidence(0.8, 0.7, 0.9, contradiction)
    assert conf > 0.55
    assert should_emit_signal(conf, 0.8, 0.8)
    assert not should_emit_signal(0.3, 0.9, 0.9)
