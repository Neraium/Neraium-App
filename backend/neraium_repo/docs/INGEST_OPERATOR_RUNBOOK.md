# Ingest Operator Runbook

Operational reference for interpreting ingestion states and responding to each outcome. Not a theory document — each section ends with **what to do first**.

---

## 1. UI states and what each means

| UI state | Lifecycle phase | Meaning |
|---|---|---|
| `idle` | — | No file selected. Nothing in progress. |
| `file_selected` | — | File chosen. Preview not started yet. |
| `previewing` | — | Sampling first 64 KB of file, calling `/ingest/csv/preview`. |
| `preview_blocked` | — | Preview returned `requires_confirmation=true` or hard issues. Upload is blocked until mapping is confirmed. |
| `preview_ready` | — | Mapping auto-detected. Upload can proceed. |
| `uploading` | `uploading` | File bytes streaming to server. |
| `ingesting` | `queued` / `processing` | File received. Background worker processing rows. |
| `completed` | `terminal` | All rows processed, all succeeded. |
| `partial_success` | `terminal` | Rows processed; at least one row failed. |
| `failed` | `terminal` | Job ended with zero successful rows. |

---

## 2. Interpreting each terminal outcome

### Full success (`completed`)

All rows were parsed, mapped, and accepted by the structural analysis engine.

**What you see:** Progress panel shows `Ingest completed`. Row counts: `N processed · N succeeded · 0 failed`. No error list.

**What it means:** Every row in the CSV produced a valid telemetry frame and was accepted by the monitoring engine for the active run. The dashboard will reflect updated structural state.

**What to do first:** Nothing is broken. Navigate to the dashboard to confirm the active run shows updated telemetry. If expected signals do not appear in the run detail, check that the `run_id` in the upload form matched the run you intended to update.

---

### Partial success (`partial_success`)

Some rows succeeded; some failed. At least one valid telemetry frame was ingested.

**What you see:** Progress panel shows `Ingest partial success`. Row counts: `N processed · M succeeded · K failed`. A short error sample list shows up to four failed rows with row number and message.

**What it means:** The CSV was well-formed enough for the engine to process part of it. Failed rows were rejected at one of:
- **Timestamp parse** — row has an invalid or missing timestamp value.
- **Signal type** — a sensor column has a non-numeric value (`SENSOR_FAULT`, `N/A`, empty string).
- **Missing identity** — row missing asset_id / site_id after column mapping was applied.

**What to do first:**
1. Click **Export errors** (see §5) to download the full error sample as JSON.
2. Open the original CSV and go to the failed row numbers listed.
3. Check the message: `invalid_timestamp` → fix the date column. `invalid_signal_values` → the sensor reading was a string, not a number. `missing_asset_id` → the asset column was empty or not mapped.
4. Fix the failed rows, re-export from the source system, and upload again.
5. If the failed rows are expected gaps (sensor offline), that is acceptable — the succeeded rows are already ingested.

---

### All failed (`failed`)

Zero rows succeeded. The job is terminal with no ingested data.

**What you see:** Progress panel shows `Ingest failed`. Row counts: `N processed · 0 succeeded · N failed`. Error samples show the first few failures.

**What it means:** The file had structural problems that prevented any row from producing a valid frame. Common causes:
- Column mapping was applied but the wrong column was chosen for timestamp or asset.
- All rows have non-numeric sensor values (e.g., the file is a report/export rather than raw telemetry).
- The file encoding caused all rows to parse incorrectly (BOM, wrong line endings).

**What to do first:**
1. Export errors (§5).
2. Look at the first error message. `missing_timestamp` → the timestamp column was not correctly mapped. `invalid_signal_values` → no numeric sensor columns were selected.
3. Re-run preview (clear file and re-select it). Check that the auto-detected mapping selects the right columns. Override if needed.
4. If the file content itself is wrong, export raw telemetry from the source system rather than a report.

---

### Structural failure / preview blocked (`preview_blocked`)

The preview could not establish a valid mapping. Upload is blocked.

**What you see:** Upload button is disabled. The mapping panel shows a warning. Status message: "Preview found ambiguous mapping. Review timestamp, asset/entity, and sensor columns before upload." OR "CSV preview could not find a header row."

**What it means:** The CSV does not match the ingestion contract in a way that can be auto-resolved:
- **No header row** — the file starts with data, not column names.
- **Ambiguous mapping** — multiple columns look like timestamps, or multiple look like asset identifiers.
- **No recognizable columns** — the file uses field names that do not match any known alias for timestamp, asset, site, or sensor.

Known timestamp aliases: `timestamp`, `time`, `ts`, `recorded_at`, `event_time`
Known asset aliases: `asset_id`, `asset`, `entity_id`, `entity`, `device_id`, `machine`, `unit`
Known site aliases: `site_id`, `site`, `system_id`, `location`, `plant`

**What to do first:**
1. Check the mapping panel. If the system found multiple candidates for timestamp or asset, deselect the wrong one.
2. If no mapping was detected at all: rename the columns in the source file to use a recognized alias (e.g., rename `datetime` → `timestamp`, `device` → `asset_id`), then re-select the file.
3. If the file has no header row, add one as the first line.

---

### Truncation

Long CSV files are handled by the streaming upload worker. Truncation is not a UI state — it is an operational condition visible in the row counts and error samples.

**What you see:** Fewer rows succeeded than the file contains. Error samples show rows above a certain number failing with a message like `stream_limit_exceeded` or the job ending earlier than expected.

**What to do first:**
1. Split the CSV into smaller chunks (500–2 000 rows per file is a reliable range for the current environment).
2. Upload each chunk separately, mapping to the same run.
3. Confirm total `rows_succeeded` across all uploads matches the expected row count.

---

## 3. REST JSON ingest outcomes

For operators or integrations using the REST JSON endpoints (`POST /ingest`, `/ingest/batch`, `/ingest/frame`):

| Response | Meaning |
|---|---|
| HTTP 200, `status: ok` | All frames accepted. |
| HTTP 200, `status: partial_success` | At least one item failed. See `errors` array in response. |
| HTTP 400, `status: error`, `type: validation_error` | All items failed normalization. No frames ingested. |
| HTTP 422, Pydantic validation error | Request shape was invalid — missing required fields or wrong types. See `detail` field. |
| HTTP 500, `type: internal_error` | Unexpected server failure. Retry once; if it persists escalate with the `correlation_id`. |

**Structural failure (JSON):** Occurs when the payload uses field names with no recognized canonical alias (e.g., `zone_id` instead of `site_id`, `alert_code` instead of sensor values, `triggered_at` instead of `timestamp`). The normalizer raises `missing_timestamp` or `missing_asset_id` for every item and the whole batch is rejected. Fix: re-export from the source system using the canonical field names or add explicit mapping.

---

## 4. How to use the replay fixtures

Fixtures are in `fixtures/`. The replay script is `tools/replay_fixtures.py`.

```
# Start the dev server first
uvicorn apps.api.main:app --reload

# In a second terminal, replay all fixtures
python tools/replay_fixtures.py

# Replay one fixture
python tools/replay_fixtures.py --fixture clean_csv
python tools/replay_fixtures.py --fixture partial_success_csv
python tools/replay_fixtures.py --fixture structural_failure_json

# Against a non-local environment
python tools/replay_fixtures.py --base-url https://myapp.example.com --api-key mykey
```

Each fixture prints HTTP status, key response fields, and any error details. Use the output to confirm the system responds as expected before ingesting real pilot data.

---

## 5. Exporting errors from the UI

After any ingest that ends in `partial_success` or `failed`, an **Export errors** button appears in the upload progress panel. Clicking it downloads a `.json` file containing:

- `job_id`, `status`, `exported_at`
- `rows_processed`, `rows_succeeded`, `rows_failed`
- `message` (terminal job message)
- `error_samples` — up to 25 row-level errors with row number and message

Use this file for:
- Sharing with the data owner to identify which rows need fixing.
- Attaching to a support escalation alongside the `correlation_id` from the job message.
- Cross-referencing row numbers against the original CSV to locate bad data.

---

## 6. Escalation checklist

When a failure cannot be resolved by the above steps, provide the following to support or on-call:

- [ ] `correlation_id` from the error message in the UI (format: `ref <id>`)
- [ ] `job_id` from the exported errors JSON
- [ ] `run_id` from the active run shown in the upload panel
- [ ] `customer_id` (visible in the topbar tenant indicator)
- [ ] Exported errors JSON (§5)
- [ ] A sanitized sample of 3–5 failed rows from the original CSV
- [ ] The `/health` endpoint response at the time of failure
