# Production Audit Report (Code + UI) — Neraium

Date: 2026-04-22

This report documents a ship-readiness audit focused on:
- API ingestion routes and request safety
- Authentication defaults in production mode
- Baseline security headers and operational safeguards
- UI/demo readiness on `http://localhost:3004`

## Executive Summary

Completed:
- Hardened production authentication defaults (API key required in production).
- Eliminated unbounded multipart CSV upload memory usage; enforced size caps during streaming upload.
- Added HSTS-on-HTTPS + Permissions Policy security headers.
- Verified frontend builds (TypeScript typecheck) and homepage route points to Tesla operator console UI.
- Standardized v2 decision contract endpoints (`/v2/state`, `/v2/recommendation`, `/v2/history`, `/v2/results/latest`).
- Fixed a NumPy runtime crash in SII preprocessing (`np.asarray(..., copy=True)`).

Known blockers / follow-ups:
- Test suite health: `pytest -q` currently reports many failures in legacy/non-shipping validation + phase-gated suites. Treat this as a ship blocker unless you explicitly narrow the shipping test scope and/or retire/fix those suites.

## Scope: Active Services and Entry Points

Backend (FastAPI):
- `apps/api/main.py` (`create_app()`)
- Routers: `apps/api/routers/{health,ingest,geometry,alerts,integrations,onboarding,ui_replay,...}.py`

Frontend (Next.js, port 3004):
- `frontend/app/page.tsx` renders `TeslaAutopilotInterface` only
- Primary UI component: `frontend/components/TeslaAutopilotInterface.tsx`
- Facility view: `frontend/components/FacilityLinkLayer.tsx`

## Findings + Remediations

### 1) Authentication in production

Finding:
- API key enforcement previously allowed missing/weak `NERAIUM_API_KEY` in production (logged, but did not fail startup).

Fix:
- `apps/api/main.py` now fails startup in `production` mode if `NERAIUM_API_KEY` is missing or weak.

Operational note:
- Set `NERAIUM_RUNTIME_MODE=production` + `NERAIUM_API_KEY=<strong random key>` for production.

### 2) CSV upload ingestion safety

Finding:
- `/ingest/csv/upload` read the entire uploaded CSV into memory (`await file.read()`), and multipart requests bypassed the global body-size middleware.
- This combination could lead to unbounded memory/disk usage.

Fix:
- `apps/api/routers/ingest.py` now streams the upload to a tempfile and enforces the configured request body limit even when `Content-Length` is missing.
- `apps/api/services/ingest_jobs.py` added `max_bytes` enforcement during streaming.
- Oversize uploads return `413` and mark the ingest job as failed.

### 3) Security headers baseline

Finding:
- Response security headers were present but minimal.

Fix:
- `apps/api/middleware/security_headers.py` now adds:
  - `permissions-policy` (camera/microphone/geolocation disabled)
  - `cache-control: no-store` for JSON API responses (e.g. `/health`)
  - `strict-transport-security` when serving HTTPS

### 4) Test hermeticity (local developer DB isolation)

Finding:
- FastAPI TestClient runs could accidentally pick up persisted operational state from the default `NERAIUM_DB_PATH` (e.g. pull-integrations resuming and attempting network calls).

Fix:
- `apps/api/main.py` now uses a temp DB path automatically when running under pytest unless `NERAIUM_DB_PATH` is explicitly set.

### 5) Decision contract v2 endpoints

Finding:
- The repo had a `build_decision_contract_v2(...)` canonicalizer but no API endpoints exposing it.

Fix:
- Added v2 endpoints returning the canonical operator-facing decision contract surface:
  - `GET /v2/state`
  - `GET /v2/recommendation`
  - `GET /v2/history`
  - `GET /v2/results/latest`

## Required Production Configuration (Minimum)

- `NERAIUM_RUNTIME_MODE=production`
- `NERAIUM_API_KEY=<strong random value, >= 16 chars>`
- `NERAIUM_DB_PATH=<persistent writable path>`
- CORS (if needed): `NERAIUM_CORS_ALLOW_ORIGINS` or `NERAIUM_CORS_ALLOW_ORIGIN_REGEX`

## Local Verification Commands

Frontend:
- `cd frontend`
- `.\node_modules\.bin\tsc.cmd --noEmit --incremental false`
- Start demo: `C:\Users\Owner\Documents\run_new_demo.bat`
- Open: `http://localhost:3004`

Backend (Python 3.11):
- `C:\Users\Owner\neraium-core\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- `C:\Users\Owner\neraium-core\.venv\Scripts\python.exe -m py_compile apps\api\main.py apps\api\routers\ingest.py neraium_core\sii\preprocessing.py`
- Targeted API tests (recommended baseline for ship readiness):
  - `C:\Users\Owner\neraium-core\.venv\Scripts\pytest.exe -q tests\test_api_*.py`

Backend (syntax check):
- `python -m py_compile apps\api\main.py apps\api\routers\ingest.py`

## UI Ship Readiness Notes (Tesla Console)

The current homepage/demo route loads the Tesla operator console UI only. The UI is designed to be decision-first:
- Global state + “what’s happening now” + “DO NOW” is the primary scan path.
- Facility relationship view shows propagation and stable zones with minimal clutter.
- Tetrahedron geometry remains the central visual, with metrics demoted to compact secondary pills.
