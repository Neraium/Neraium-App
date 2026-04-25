# Customer-hosted deployment guide

This guide is the **production path** for running Neraium inside a customer environment.

## Hosting model

When deployed customer-side:

- Neraium runs on customer VM / server / container
- Neraium pulls or receives telemetry from customer APIs
- SII computation runs locally in that environment
- Result storage stays local (`NERAIUM_DB_PATH`)
- Operator UI/API are served locally (internal network / VPN / reverse proxy)
- No control/writeback path is exposed by this product

## 1) Configure environment

Use `.env.customer.example` as a template:

```bash
cp .env.customer.example .env
```

Set at minimum:

- `NERAIUM_API_KEY`
- `NERAIUM_DB_PATH`
- `HOST`
- `PORT`

Set integration-related values when using pull mode:

- `NERAIUM_CUSTOMER_API_BASE_URL` (optional default for start endpoint)
- `NERAIUM_CUSTOMER_API_AUTH_TYPE` (`none|basic|bearer`)
- `NERAIUM_CUSTOMER_API_USERNAME` / `NERAIUM_CUSTOMER_API_PASSWORD` (basic)
- `NERAIUM_CUSTOMER_API_TOKEN` (bearer)
- `NERAIUM_PULL_POLLING_INTERVAL_SECONDS` (recommended default)
- `NERAIUM_INTEGRATION_CONFIG_PATH` (mapping configuration file path)

Set alerting-related values (optional, minimal defaults are applied automatically):

- `NERAIUM_ALERT_INSTABILITY_THRESHOLD` (default `1.5`)
- `NERAIUM_ALERT_RAPID_DRIFT_DELTA` (default `0.2`)
- `NERAIUM_ALERT_WEBHOOK_URL` (stub logging only)
- `NERAIUM_ALERT_EMAIL_TO` (stub logging only)

## 2) Run with Docker

Build:

```bash
docker build -t neraium:latest .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data:/data" \
  -v "$(pwd)/config:/config:ro" \
  neraium:latest
```

Then open:

- UI: `http://localhost:8000/`
- Health: `http://localhost:8000/health`

## 3) Run with docker-compose

```bash
docker compose up --build
```

Default exposed endpoint: `http://localhost:8000`

## 4) Configure pull integration

Start pull integration for a customer:

```bash
curl -X POST "http://localhost:8000/integrations/pull/start?customer_id=acme" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${NERAIUM_API_KEY}" \
  -d '{
    "endpoint_url": "https://customer.internal/api/telemetry",
    "polling_interval_seconds": 30,
    "auth_type": "bearer",
    "token": "REPLACE_ME",
    "retry_max_attempts": 3,
    "retry_backoff_seconds": 1.0,
    "request_timeout_seconds": 10.0
  }'
```

Check status:

```bash
curl "http://localhost:8000/integrations/pull/status?customer_id=acme"
```

Stop:

```bash
curl -X POST "http://localhost:8000/integrations/pull/stop?customer_id=acme" \
  -H "x-api-key: ${NERAIUM_API_KEY}"
```

## 5) Integration mapping config

Mapping is config-driven via `NERAIUM_INTEGRATION_CONFIG_PATH`.

See:

- `config/integration.customer.sample.json`

Supports:

- alias field names
- field renaming
- case/spacing normalization
- sensor extraction from nested object

This keeps customer payload differences out of the engine code.

## 5.1) One-command startup

After creating `.env` and adding the integration sample config:

```bash
mkdir -p data config
cp config/integration.customer.sample.json config/integration.json
docker compose up --build
```

This starts the API and UI at `http://localhost:8000` with local persistence in `./data`.

## 6) Security posture notes

- Run Neraium behind customer network boundaries (private subnet, VPN, reverse proxy).
- Keep API key enabled in production (`NERAIUM_API_KEY`).
- Do not expose internal endpoints publicly unless explicitly required.
- Mount config/token sources securely (secrets manager, protected env injection, etc).

## 7) Basic alerting

Alerts are generated on ingest and can be listed via API:

```bash
curl "http://localhost:8000/alerts?customer_id=acme&limit=20"
```

Triggers:

- risk transition to `HIGH`
- composite instability crossing `NERAIUM_ALERT_INSTABILITY_THRESHOLD`
- rapid drift delta over `NERAIUM_ALERT_RAPID_DRIFT_DELTA`

Optional stub endpoint for smoke checks:

```bash
curl -X POST "http://localhost:8000/alerts/test?customer_id=acme" \
  -H "x-api-key: ${NERAIUM_API_KEY}"
```

If `NERAIUM_ALERT_WEBHOOK_URL` or `NERAIUM_ALERT_EMAIL_TO` is set, Neraium logs
webhook/email stub events for each alert (no outbound delivery implementation yet).

## 8) Kubernetes (later)

Current packaging is container-ready and works well as a base for Kubernetes:

- image from provided Dockerfile
- env vars from secrets/config maps
- persistent volume for `NERAIUM_DB_PATH`
- internal service exposure only
