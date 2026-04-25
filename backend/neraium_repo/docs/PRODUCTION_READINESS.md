## Neraium Production Readiness (Operator Quick Guide)

This is the canonical deployment/readiness checklist for controlled live startup.

### Required environment variables

- `NERAIUM_API_KEY` (required in production)
- `NERAIUM_RUNTIME_MODE=production`
- `NERAIUM_DB_PATH` (must point to writable persistent path, e.g. `/data/neraium.db`)
- `HOST` (typically `0.0.0.0`)
- `PORT` (typically `8000`)
- `NERAIUM_LOG_LEVEL` (e.g. `INFO`)

Common optional production vars:

- `NERAIUM_INTEGRATION_CONFIG_PATH` (e.g. `/config/integration.json`)
- `NERAIUM_MAX_REQUEST_BODY_BYTES`
- `NERAIUM_UVICORN_H11_MAX_INCOMPLETE_EVENT_SIZE`

### Official production startup command

Use this command for direct host startup:

```bash
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Containerized startup uses the same command via `docker/entrypoint.sh`.

### Readiness validation commands

1) Targeted production-hardening/API tests

```bash
python -m pytest -q tests/test_runtime_config.py tests/test_api_db_path_fallback.py tests/test_sii_cli.py tests/test_api_validation_errors.py tests/test_api_product_basics.py
```

2) API startup + health smoke

```bash
python test_predeploy.py
```

3) FD004 validation

```bash
python -m pytest -q tests/test_fd004_real.py
```

4) IMS validation

```bash
python -m pytest -q tests/test_ims_state_transitions.py
```

### Health check steps

After startup:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

- HTTP `200`
- `status=ok`
- runtime diagnostics present (including persistence/runtime flags)

### Writable path requirements

Production startup will fail fast when runtime assumptions are not met:

- Parent directory of `NERAIUM_DB_PATH` must be writable.
- Temp/upload directory must be writable.
- In production mode, persistence must be available.

### Common startup failure modes

- **Persistence unavailable in production mode**
  - Fix: set `NERAIUM_DB_PATH` to a writable persistent location.
- **Database path directory is not writable**
  - Fix: create/chmod/chown the parent directory used by `NERAIUM_DB_PATH`.
- **Temporary upload directory is not writable**
  - Fix: ensure container/host temp directory is writable.
- **Import/startup failure (`apps.api.main`)**
  - Fix: install dependencies via `pip install .` and start with the official command above.
