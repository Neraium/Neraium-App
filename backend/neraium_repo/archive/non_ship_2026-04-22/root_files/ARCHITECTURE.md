# Neraium Core Architecture

_Last updated: April 10, 2026._

## Runtime surfaces

1. **API runtime**: `apps.api.main:app` (FastAPI) for ingest, state, alerts, and integration endpoints.
2. **Replacement UI runtime**: `ui` package (Gradio-optional) for pilot/operations/demo visualization payloads.

The legacy static UI (`apps/api/static`) is intentionally removed and is not part of the runtime.

## UI package structure

- `ui/app.py`: entry points for import-safe app state construction and lazy Gradio construction.
- `ui/config.py`: environment-backed UI configuration.
- `ui/core_integration.py`: canonical field mapping from Neraium outputs to UI payloads.
- `ui/components/*`: semantic view widgets (alert FSM, structural flow, causal inspector, attribution, mode selector, regime timeline).
- `ui/layouts/*`: pilot, operations, and demo views with responsive composition helpers.
- `ui/realtime/websocket_feed.py`: optional realtime feed abstraction that degrades safely if websocket dependencies are unavailable.
- `ui/themes/neraium_dark.css`: replacement visual theme.

## Canonical output fields used in UI

- `timestamp`
- `site_id`
- `asset_id`
- `state`
- `regime_name`
- `structural_drift_score`
- `relational_stability_score`
- `system_health`
- `drift_alert` / `alert`
- `confidence` / `confidence_score`

## Import safety and startup behavior

- `ui` imports are safe without Gradio.
- Gradio is imported lazily only inside `ui.app.create_gradio_app`.
- Realtime websocket integration is optional-safe and returns a disabled state when unavailable.
