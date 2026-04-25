"""
Demonstrate market and sports payloads flowing through data connectors + StructuralEngine.

Run from repo root:
  python examples/live_feed_demo.py
"""

from __future__ import annotations

from neraium_core.data_connectors import build_frame_from_market_payload, build_frame_from_sports_payload
from neraium_core.live_runner import process_market_payload, process_sports_payload
from neraium_core.alignment import StructuralEngine


def main() -> None:
    # Use a dedicated engine per feed: mixing unrelated sensor schemas on one engine
    # would expand ``sensor_order`` and break downstream geometry bookkeeping.
    market_engine = StructuralEngine(baseline_window=12, recent_window=6)
    sports_engine = StructuralEngine(baseline_window=12, recent_window=6)

    market_raw = {
        "symbol": "DEMO",
        "timestamp": "2026-04-02T15:30:00Z",
        "open": 100.0,
        "high": 101.5,
        "low": 99.5,
        "close": 100.75,
        "volume": 500000.0,
        "spread": 0.01,
        "momentum": 0.02,
    }
    print("Normalized market frame:", build_frame_from_market_payload(market_raw))

    sports_raw = {
        "game_id": "demo-nfl-001",
        "timestamp": "2026-04-02T18:00:00Z",
        "spread": -2.5,
        "total": 47.5,
        "implied_probability": 0.55,
        "pace": 65.0,
        "score_diff": 3.0,
    }
    print("Normalized sports frame:", build_frame_from_sports_payload(sports_raw))

    # Feed a short sequence so the engine moves past trivial warmup.
    for i in range(30):
        market_raw["close"] = 100.75 + i * 0.01
        market_raw["high"] = max(market_raw["high"], market_raw["close"])
        r = process_market_payload(market_raw, engine=market_engine)
    print("Last market engine keys (sample):", sorted(list(r.keys()))[:12], "...")
    print("action_signal:", r.get("action_signal"))

    for i in range(30):
        sports_raw["spread"] = -2.5 + i * 0.02
        sports_raw["total"] = 47.5 + i * 0.01
        r2 = process_sports_payload(sports_raw, engine=sports_engine)
    print("Last sports action_signal:", r2.get("action_signal"))


if __name__ == "__main__":
    main()
