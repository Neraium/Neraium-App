# Neraium Internal Historical Evaluation Workbench

Neraium-App is the internal analyst tool for evaluating historical telemetry
supplied by a prospect or customer. It manages intake, review, provenance and
customer reports. **Neraium-1.0 owns intelligence and evidence semantics.**

Workflow: **Evaluation details → Upload reference → Upload comparison → Validate
compatibility → Confirm signal mapping → Run authoritative SII → Review evidence
→ Export report.**

This is a read-only historical evaluation tool. It does not provide live
monitoring, equipment control, failure probability, RUL, causal diagnosis, or
autonomous recommendations. No findings and insufficient evidence are valid
outcomes. A completed analysis is not a statement of equipment health.

## Local analyst setup

Use Python 3.11+ and Node 22. From this repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
cd ..
```

Configure a **separate, clean** Neraium-1.0 checkout at the supported revision:
`6e26a83a17babaea443b75c545a756835d37102b` (merged PR #136, September 8, 2026).
Do not point the workbench at a developer checkout with unfinished changes.
Install that revision's backend dependencies in a separate virtual environment.
The workbench interpreter and authority interpreter can be different.

```bash
export NERAIUM_AUTHORITY_ROOT=/absolute/path/to/clean/Neraium-1.0
unset NERAIUM_AUTHORITY_COMMIT # use the workbench's validated pin
export NERAIUM_AUTHORITY_PYTHON=/absolute/path/to/authority-venv/bin/python
export NERAIUM_WORKBENCH_DATA="$HOME/.local/share/neraium-workbench"
export NERAIUM_WORKBENCH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
.venv/bin/python launch.py
```

Open `http://127.0.0.1:3006` and enter the token from your launch shell. The token
is held in tab memory, not local storage. Environment variables must be exported;
`.env.example` is reference documentation, not an automatically loaded file.
Empty optional environment variables should be omitted.

The launcher binds both processes to loopback. This version is for **one local
analyst and one backend worker**, not a public or multi-user service. Do not use
`--workers`, expose it on a public interface, or deploy the legacy Docker/AWS
configuration. No MongoDB, customer API key, live provider, or cloud credentials
are required. The old Compose configuration has been removed.

## Running an evaluation

1. Choose **New Evaluation** and enter customer, facility, physical system and
   scope. New evaluations use paired reference/comparison mode. Previously saved
   single-dataset evaluations remain accessible.
2. Upload UTF-8 CSV, TSV or a JSON array of flat row objects. Limits: 10 MiB,
   10,000 rows, 64 columns, at most 24 selected analysis signals. Use one system
   per evaluation. Larger inputs require an explicitly scoped upstream extract;
   the workbench never silently samples or truncates a source.
3. Select the timestamp column and format: timezone-aware ISO, Unix seconds or
   Unix milliseconds. Review missing/invalid cells, constant signals, duplicate
   timestamps and ordering. Invalid/ambiguous/duplicate/unordered times block
   mapping. Upload a corrected source as a new source; earlier bytes remain.
4. Explicitly include/exclude every signal, enter confirmed meanings and supplied
   units, explain exclusions, and record system context and unknowns. Blank units
   remain unknown. Optionally restrict the historical time interval. No unit
   conversion, zero filling, resampling or causal-prior generation occurs.
5. Preview the **authority's** analysis classifications and approve them. Correct
   a mistaken meaning or exclude an unsuitable signal. A changed source,
   validation or mapping requires renewed approval.
6. Run analysis. In single-dataset mode, the engine owns baseline/comparison selection within the selected
   interval; the workbench does not declare the baseline healthy. Inspect its
   windows, relationship changes, persistence, uncertainty and module limitations.
7. Download the full run evidence JSON. Record an analyst review to generate a
   printable HTML customer report (browser Print → Save as PDF). Deliver the
   report with its evidence JSON. Prior runs/reports remain accessible after
   subsequent uploads, and report content is frozen when reviewed.

## Paired reference/comparison

Upload reference and comparison independently into one evaluation, then validate
both timestamp columns/formats. Both original files and hashes remain independent.
Confirm one shared inclusion/exclusion mapping, identical physical signal identities,
meanings and supplied units, and the same physical system. This is an analyst
attestation against source documentation; the App cannot establish physical identity
or units from telemetry values. Different signal schemas, unknown included units,
unconfirmed compatibility and invalid timestamps block paired analysis. Use explicit
`dimensionless` units when applicable. Paired mode uses both full periods; it does
not merge files, restrict intervals, fill, resample or normalize input rows.

Paired mode calls the pinned `evaluate_sii` with separate `reference_rows` and
`comparison_rows`, approved signal names and shared `signal_units`. It preserves
the complete authoritative result, including governed `analysis_result`/findings,
relationship changes, temporal onset evidence, persistence, uncertainty, limitations
and supplied-reference provenance. Consequence is retained only when supplied by
authority. Stable, no-material-change and insufficient-evidence outcomes are valid.
No saved baseline is activated or persistent memory updated.

The authority derives fresh classification and operating context; it rejects
injected catalogs and free-text context configuration. Approved analyst context
remains in the immutable App input/report, not an engineering prior. Filenames and
customer metadata are not sent to analytical calls. Analysts must exclude outcome
labels. The authority requires at least 16 rows per period, finite numeric values
and no cumulative counters; unsupported input fails without imputation or fallback.

### Intake limit audit

The intake bound is now 10,000 rows **per file**, with unchanged 10 MiB/file,
64-column and 24-selected-signal bounds. There is no transport-level 5,000-row bound
in the direct authority subprocess. The single-dataset temporal module *does* default
to the last 5,000 rows; the adapter now sets its supported `temporal_config.max_rows`
to the complete input length. Other authority-selected analysis windows remain
engine semantics and are retained in evidence; intact intake does not imply every
engine module uses every row. Paired SII supports 16–12,000 rows per period with a 12,000-row temporal default;
the App retains its stricter 10,000-row intake bound. Authority module limits remain
visible in evidence.
The 120-second analysis, 30-second preview and 150-second client timeouts remain;
timeouts fail explicitly with no sampling or substituted result. Capacity at maximum
rows/signals has not been benchmarked. Focused intake tests cover 8,640 and 10,000
rows without running a large authority workload.

## Authority and traceability

`backend/workbench/authority_worker.py` imports
`app.engine.sii_engine.evaluate_sii` from the configured Neraium-1.0 checkout in
an isolated subprocess. Preview also uses that checkout's profile/classification
helpers. No analysis algorithm is copied into this repository. No App legacy
engine is imported by the active server or included in the installed package.

Both pre- and post-execution checks verify the clean pinned commit. Incompatible
versions, missing dependencies, malformed output, timeouts and engine failures
produce explicit errors; there is no synthetic or legacy fallback. Revision
updates require a focused adapter contract check and an explicit pin change.

The workbench is pinned to the merged Neraium-1.0 PR #136 authority commit
`6e26a83a17babaea443b75c545a756835d37102b`. The optional
`NERAIUM_AUTHORITY_COMMIT` environment variable is only an assertion of this pin;
leave it unset or set it to the same SHA. Existing run/report identities remain
unchanged when the supported authority revision changes.

Source bytes, hashes, validation, mapping approval, selected interval, transformed
input rows, request hash, engine output/hash, authority commit, adapter hash,
Python/package versions, reviews and report hashes are stored locally in private
SQLite storage **outside the repository**. Back up and protect that directory
according to the customer's handling agreement; storage is not encrypted by this
application. Never commit customer files, evidence exports, tokens or secrets.

Cross-run behavioral memory and engineering priors are deliberately unconfigured;
associated authoritative limitations are retained. Context is recorded as supplied
context, not converted into physical laws. There is no verified consequence
attachment workflow yet, so reports do not invent cost, energy or failure impacts.
An interrupted server may leave a `running` record; it is not reportable. Start a
new run to retry; preserved records are not overwritten.

## Focused verification

```bash
.venv/bin/python -m pytest tests/workbench -q
cd frontend
CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.js
CI=true npm run build
```

To include the tiny real-authority integration test, set
`NERAIUM_TEST_AUTHORITY_ROOT` to the clean supported checkout and
`NERAIUM_AUTHORITY_PYTHON` to its dependency-equipped interpreter. That test uses
24 generated single-dataset rows or 64 generated paired contract-test rows, never customer or benchmark datasets. Without
this configuration, CI skips the external integration and checks transport,
validation, failure behavior, report safety and provenance using explicit stubs.

See [architecture](ARCHITECTURE.md), [original audit](docs/HISTORICAL_WORKBENCH_AUDIT.md)
and [legacy inventory](docs/WORKBENCH_LEGACY_BOUNDARY.md). Older Grow, demo,
production-deployment, benchmark and research documents do not describe the
active workbench. Retained legacy sources are historical reference only.

## app.neraium.com deployment boundary

The dedicated production stack and reproducible deployment configuration are in
[deploy/production](deploy/production/README.md). It serves the pinned App through
a new CloudFront distribution, with a private single-worker backend. Cloudflare
DNS remains unchanged; the custom-domain certificate validation and alias steps
are documented there. CI validates changes; it does not deploy the application.
The [original deployment handoff](docs/APP_DEPLOYMENT_HANDOFF.md) records the
pre-deployment findings.
