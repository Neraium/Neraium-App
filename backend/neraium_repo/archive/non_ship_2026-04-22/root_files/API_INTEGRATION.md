# API Integration for Replacement UI

_Last updated: April 10, 2026._

## Purpose

This guide documents how the `ui` package consumes Neraium API outputs after static router removal.

## Data contract expected by UI

The replacement UI expects records with these keys (missing values are tolerated):

- `timestamp`
- `site_id`
- `asset_id`
- `state`
- `regime_name`
- `structural_drift_score`
- `relational_stability_score`
- `system_health`
- `drift_alert` or `alert`
- `confidence` or `confidence_score`

## Integration path

1. API outputs (for example ingest/result endpoints) produce canonical result records.
2. `ui.core_integration.compact_record` maps records into stable UI payloads.
3. `ui.layouts` composes pilot/operations/demo views.
4. `ui.realtime.create_realtime_feed` may provide websocket-backed status when dependency support exists.

## Notes

- There is no `apps/api/static` UI fallback.
- The API runtime remains independent of the UI package.
- UI launch is optional (`python -m ui.app`) and should be treated as a separate process from the API service.
- UI demo hydration now loads greenhouse-first records via `ui.demo_data.load_greenhouse_demo_records`, preferring `greenhouse_demo/run_grow_demo_ultrafast.py` when present and falling back to canonical scenario JSON.
- UI summary payload now includes `summary.replay_story` with concise progression signals (state transitions, drift/stability/confidence trends, and a headline) for investor/operator readability.

## Demo replay source

- Historical demo replay is greenhouse-first and uses the canonical scenario at `apps/api/demo_data/cannabis_grow_op_scenario.json`.
- Preferred API start endpoint: `POST /demo/greenhouse/start` (`/demo/cmapss/start` remains as a compatibility alias).
- Status/proof endpoints follow the same pattern: `/demo/greenhouse/status` and `/demo/greenhouse/proof-summary` with CMAPSS routes retained as aliases.
