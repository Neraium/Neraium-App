# Neraium product UI (static frontend)

The browser app is served from `apps/api/static/` (HTML, consolidated `styles.css`, and JS modules) by the same FastAPI process as the API. There is no separate Vite/npm dev server in this repository snapshot.

## Boundaries

- **API (`/runs`, `/results`, …)** — source of truth for runs, results, and geometry payloads.
- **Web UI** — renders dashboards and run detail; calls JSON endpoints with `customer_id` / optional `site_id` query scope.
- **Three.js** — loaded via `three-init.mjs` and the import map in `index.html`; structural flow uses the shared Three namespace on `window`.

## Operational toggles

| Mechanism | Purpose |
|-----------|---------|
| `localStorage` `neraium_disable_client_errors` = `1` | Disable posting JS errors to `POST /client-errors` |
| URL `?noClientLog=1` | Same, without touching storage |
| `localStorage` `neraium_feat_<name>` = `1` or `?feat_<name>=1` | Opt-in feature flags (see `neraiumFeatureEnabled` in `app.js`) |
| `window.NERAIUM_FEATURE_ENABLED(name)` | Console/QA helper for the same flags |

## Client error reporting

The UI posts minimal error payloads (message, stack snippet, URL) to **`POST /client-errors`**, which logs a server warning. No API key is required; intended for same-origin browser traffic. Throttling is applied client-side to reduce duplicate bursts.

## Structural flow panel

Geometry is loaded when run detail loads. Heavy WebGL setup is scheduled with **`requestIdleCallback`** (or `setTimeout` fallback) so the main thread stays responsive. Loading state uses **`geometry-viewport--loading`** / **`geometry-canvas-wrap--loading`** classes for a subtle shimmer until the scene is ready.

## UI structure baseline

- Primary navigation is explicitly mapped to the three operator jobs:
  1) Monitor risk, 2) Upload telemetry, 3) Investigate run.
- Setup flows (Onboarding setup and Validation replay) remain available, but secondary.
- Run creation is intentionally de-emphasized and moved under Investigate run as an inline fallback action.

## Incremental hardening still pending

- `modules/dashboard.js` and `modules/geometry.js` are still large and should be split by responsibility once contracts stabilize.
- Add automated browser smoke tests in CI for core flows (risk, upload, investigate).
