# Internal historical evaluation architecture

The active application is `backend.server:app` → `backend/workbench/api.py` and
`frontend/src/App.js`. All legacy live, demo, system-state and customer-key routers
are disconnected. The installed Python package contains the workbench only.

## Ownership

| Owner | Responsibilities |
|---|---|
| Neraium-App | Internal access, evaluation identity, original source preservation, bounded parsing/quality validation, mapping review, run orchestration, artifact storage, evidence presentation, reviewed report export |
| Neraium-1.0 | Numeric profiling, classification proposals, baseline/comparison selection, authoritative SII analysis, relationship/persistence evidence, uncertainty, evidence semantics |

The authority is the clean pinned source revision documented in README. App's
adapter calls `app.engine.sii_engine.evaluate_sii` in a separate interpreter,
using JSON stdin/stdout. It does not call App's old SII engines or copy 1.0 math.
`shared/neraium-intelligence` is added to the authority's import path for contracts;
it is not incorrectly treated as a standalone complete engine.

## Data flow

1. The analyst's token gates all `/api` customer-data endpoints. The supported
   runtime is a local loopback process with one operator and one worker.
2. Upload accepts a bounded raw body, validates tabular shape and preserves exact
   bytes in the `sources` table. No original source is updated or deleted by API.
3. Explicit timestamp selection produces a quality report. Source timestamps and
   cells remain unmodified. Duplicate/ambiguous/unordered times block progression.
4. Mapping requires every signal to be included or excluded, confirmed meanings,
   explicit unknown/supplied units, exclusion reasons and supplied system context.
   Input generation preserves nulls, parses numbers, converts explicit timestamps
   to UTC, projects approved signals and restricts an optional inclusive interval.
5. An authoritative preview proposes analysis categories. Approval is bound to
   that preview, input hash and authority identity. Revisions invalidate approval;
   concurrent edits during preview are rejected.
6. A run snapshots evaluation/source/validation/mapping/input before invoking the
   authority. One analysis executes at a time; processing has a 120-second timeout.
   Full source data never passes through live/demo state or a rolling 600-row store.
7. Result status and payload remain authoritative. A complete result is not a
   positive finding; limited and failed states are retained. No fallback scoring,
   inferred physical consequence or generated causal narrative exists in App.
8. Evidence downloads contain provenance and exact input/result snapshots.
   Reviews and escaped HTML reports are append-only; reviewed HTML is stored and
   hashed so later code or dataset changes cannot silently rewrite a report.

SQLite transactions serialize mutations. Input and result hashes use canonical
JSON (`sort_keys`, compact separators, no nonfinite values). Source hashes use
original bytes. Run ID is included in a separate exact request hash. Runtime
package versions and the adapter script hash accompany authoritative output.

## Analytical limitations

Baseline/comparison windows are chosen by the authority within the approved
historical interval; no manually certified healthy baseline is fabricated.
No authenticated cross-run behavioral-memory scope is supplied; the resulting
Phase 4 limitations remain in evidence. No configured engineering priors are
invented from free text. System context is supplied metadata, not causal proof.
Detailed canonical evidence remains in the JSON export; reports use bounded
excerpts and explicit evidence paths. A reported correlation window is not an
inferred onset time. Consequence attachment/verification is not implemented.

## Runtime boundary

No MongoDB, websocket, scheduler, external telemetry fetch, demo playback, customer
API key or production deployment is part of the supported workbench. The runtime
stores customer data outside the repository with owner-only directory permissions.
It is not a multi-tenant hosted service; OS access and the internal token define
its local trust boundary. Authority source and interpreter are trusted, externally
provisioned dependencies. Missing authority configuration fails closed.

A server interruption can preserve a nonterminal run. No report can be produced
from it; retry creates a separate run. There is no background recovery queue.
See README for supported formats, limits, setup and focused checks.

## Supplied reference/comparison boundary

Paired evaluations add an independent reference source/validation to the existing
comparison source. Both are snapshotted in each run, alongside a shared mapping and
explicit same-system/identity/meaning/unit attestation. Either upload or validation
invalidates approval. Full projected row arrays stay separate; source bytes are
immutable. No database schema migration is needed for the JSON documents.

The paired adapter calls `app.engine.sii_engine.evaluate_sii` with separate
`reference_rows` and `comparison_rows`, approved signal names and shared units.
The full result is preserved unchanged, including governed analysis, relationships,
temporal onset, persistence, uncertainty, limitations and content-hash provenance.
No local scoring, comparison math, result fusion or timing inference is added.
The authority derives fresh catalogs and operating context; analyst context is
retained in App snapshots rather than injected as an unsupported configuration.
No saved baseline is activated or persistent behavioral memory updated.

Intake allows 10,000 rows per source within the authority's 16–12,000 paired-row
contract. The paired temporal default covers 12,000 rows; the single SII path
continues to override its 5,000-row default with input length. Byte/signal/time
budgets remain unchanged; engine-internal limits remain visible evidence.
