from __future__ import annotations

from datetime import datetime, timezone

from neraium_core.sports_betting_adapter import build_betting_frame
from neraium_core.stock_market_adapter import build_stock_frame


def test_build_stock_frame_keeps_only_numeric_sensor_values() -> None:
    frame = build_stock_frame(
        timestamp=1712055000,
        ticker="AAPL",
        row_dict={
            "open": "123.4",
            "high": 125,
            "low": 122.1,
            "close": "124.0",
            "volume": "1000",
            "value": 124000,
            "note": "ignore-me",
            "halted": False,
        },
    )

    assert set(frame.keys()) == {"timestamp", "customer_id", "site_id", "asset_id", "sensor_values", "sensor_quality", "aligned", "anomaly"}
    assert frame["site_id"] == "market"
    assert frame["asset_id"] == "AAPL"
    assert frame["timestamp"] == datetime.fromtimestamp(1712055000, tz=timezone.utc).isoformat()
    assert frame["customer_id"] == "default-customer"
    assert frame["sensor_quality"] == {
        "open": "ok",
        "high": "ok",
        "low": "ok",
        "close": "ok",
        "volume": "ok",
        "value": "ok",
    }
    assert frame["aligned"] == []
    assert frame["anomaly"] is False
    assert frame["sensor_values"] == {
        "open": 123.4,
        "high": 125.0,
        "low": 122.1,
        "close": 124.0,
        "volume": 1000.0,
        "value": 124000.0,
    }


def test_build_betting_frame_keeps_only_numeric_sensor_values() -> None:
    frame = build_betting_frame(
        timestamp="1712055001",
        market_id="NBA-LAL-BOS",
        row_dict={
            "home_odds": "1.95",
            "away_odds": 2.1,
            "draw_odds": None,
            "market_status": "open",
            "live": True,
        },
    )

    assert set(frame.keys()) == {"timestamp", "site_id", "asset_id", "sensor_values"}
    assert frame["site_id"] == "sportsbook"
    assert frame["asset_id"] == "NBA-LAL-BOS"
    assert frame["timestamp"] == float(1712055001)
    assert frame["sensor_values"] == {
        "home_odds": 1.95,
        "away_odds": 2.1,
    }
