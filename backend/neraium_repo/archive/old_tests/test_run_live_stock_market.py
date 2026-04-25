from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from run_live_stock_market import (
    _append_csv_row,
    _build_connector,
    _fetch_bars_per_symbol,
    _load_replay_bars,
    _validate_bar,
    parse_args,
)
from neraium_core.data_connectors import LiveConnectorError


def test_parse_args_supports_required_live_flags(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_live_stock_market.py",
            "--tickers",
            "AAPL,MSFT",
            "--interval",
            "2",
            "--output",
            "logs/live.csv",
            "--mock",
            "--max-iterations",
            "1",
        ],
    )
    args = parse_args()
    assert args.tickers == "AAPL,MSFT"
    assert args.interval == 2.0
    assert args.output == "logs/live.csv"
    assert args.mock is True


def test_build_connector_uses_mock_shortcut(monkeypatch) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    args = type(
        "Args",
        (),
        {
            "mock": True,
            "provider": "polygon",
            "api_key": None,
            "provider_interval": "1min",
        },
    )()
    connector = _build_connector(args)
    assert connector.__class__.__name__ == "MockLiveConnector"


def test_append_csv_row_creates_header_once(tmp_path: Path) -> None:
    output_path = tmp_path / "signals.csv"
    row = {
        "timestamp": "2026-04-02T00:00:00+00:00",
        "ticker": "AAPL",
        "state": "NORMAL",
        "trading_signal": "HOLD",
        "confidence": 0.8,
        "structural_drift_score": 0.2,
        "latest_instability": 0.2,
        "reason": "signal_eligible",
        "transition": False,
        "cooldown_remaining_seconds": 0.0,
        "emitted": True,
    }
    _append_csv_row(str(output_path), row)
    _append_csv_row(str(output_path), row)

    text = output_path.read_text(encoding="utf-8")
    assert text.count("timestamp,ticker,state,trading_signal,confidence") == 1
    assert text.count("AAPL") == 2


def test_validate_bar_rejects_missing_fields() -> None:
    bar, error = _validate_bar({"ticker": "AAPL", "timestamp": "2026-04-02T12:00:00+00:00"})
    assert bar is None
    assert "missing_fields" in str(error)


def test_load_replay_bars_filters_and_sorts(tmp_path: Path) -> None:
    csv_path = tmp_path / "replay.csv"
    csv_path.write_text(
        "timestamp,ticker,open,high,low,close,volume\n"
        "2026-04-02T12:01:00+00:00,MSFT,1,2,0.5,1.3,100\n"
        "2026-04-02T12:00:00+00:00,AAPL,1,2,0.5,1.4,100\n",
        encoding="utf-8",
    )

    rows = _load_replay_bars(str(csv_path), ["AAPL"])
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"


def test_fetch_bars_per_symbol_tolerates_partial_connector_failure() -> None:
    class _Connector:
        def fetch_latest_bars(self, tickers: list[str]) -> list[dict[str, object]]:
            ticker = tickers[0]
            if ticker == "MSFT":
                raise LiveConnectorError("provider hiccup")
            return [
                {
                    "timestamp": "2026-04-02T12:00:00+00:00",
                    "ticker": ticker,
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 100.0,
                }
            ]

    bars = _fetch_bars_per_symbol(_Connector(), ["AAPL", "MSFT"], cycle_started=datetime.now(timezone.utc))
    assert len(bars) == 1
    assert bars[0]["ticker"] == "AAPL"
