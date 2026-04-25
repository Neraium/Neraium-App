# Live Stock Market Runner (Polling)

> **Safety mode:** analytics/signals only. This runner does **not** place trades.

## Runtime path (source-of-truth flow)

`connector -> stock_market_adapter -> live_runner -> trading_signals -> compact output/logging`

- `neraium_core/data_connectors.py`: provider fetch and canonical bar mapping.
- `neraium_core/stock_market_adapter.py`: ingress frame generation.
- `neraium_core/live_runner.py`: frame handoff into engine.
- `neraium_core/trading_signals.py`: signal derivation + intraday noise controls.
- `neraium_core/intraday_output.py`: compact trader-facing output contract.
- `run_live_stock_market.py`: orchestration, guardrails, logging, replay mode.

## Guardrails included

- malformed/incomplete bars are dropped with explicit runtime messages
- duplicate or out-of-order timestamps are suppressed per ticker
- per-symbol connector failures are isolated (other symbols continue)
- provider hiccup fallback (`--fallback-to-mock`) remains available
- empty converted frames are rejected with visibility

## Providers

- `massive` (Polygon-compatible endpoint)
- `polygon`
- `alphavantage`
- `mock`

## Environment variables

- `MASSIVE_API_KEY` or `POLYGON_API_KEY`
- `ALPHAVANTAGE_API_KEY`
- optional defaults: `LIVE_DATA_PROVIDER`, `LIVE_POLL_INTERVAL`, `ALPHAVANTAGE_INTERVAL`

## Live command

```bash
python run_live_stock_market.py \
  --tickers AAPL,MSFT \
  --provider massive \
  --interval 15 \
  --min-confidence 0.50 \
  --cooldown-seconds 60 \
  --warmup-bars 8 \
  --output logs/live_signals.csv
```

## Replay command (paper-trading validation)

```bash
python run_live_stock_market.py \
  --tickers AAPL,MSFT \
  --replay-csv data/sample_market_data.csv \
  --min-confidence 0.50 \
  --cooldown-seconds 60 \
  --output logs/replay_signals.csv
```

## Compact output fields

- `timestamp`
- `ticker`
- `state`
- `trading_signal`
- `confidence`
- `structural_drift_score`
- `latest_instability`
- `reason`
- `transition`
- `cooldown_remaining_seconds`
- `emitted`

## Noise-control knobs

- `--min-confidence`
- `--cooldown-seconds`
- `--state-change-only`
- `--warmup-bars`

These controls are configurable and default-safe for non-executing intraday support.
