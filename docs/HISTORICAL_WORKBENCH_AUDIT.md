# Historical evaluation workbench audit

Date: 2026-09-08. Scope: inspection and recommendations; no runtime changes.

Neraium-App should own the internal workflow from customer/prospect historical
telemetry through validation, signal/context mapping, authoritative analysis,
evidence review, and a customer evaluation report.

## Inspection boundary

- Neraium-App was absent locally and cloned from its default branch, `main`, at
  `6b154f0108a9d3411b4526a64d5631d5c1784ea9`.
- No `AGENTS.md` or additional named instruction/rules files were found in this
  checkout; no ancestor `AGENTS.md` was present. User constraints govern the audit.
- Neraium-1.0 comparison: local HEAD
  `e665018993b128d0dbd280879727be8a7181d6fb`, with substantial existing modified and
  untracked work. Committed historical-ingestion and result-contract sources were
  also inspected with `git show`. Local telemetry services are identified below
  as uncommitted, not assumed to be a released integration.
- This is static inspection. No dependencies installed, application started,
  datasets processed, tests run, or deployment attempted. Reuse candidates are
  not claims of verified runtime correctness.
- The request ended at “what is”; the missing final criterion is unknown.

## Finding

The repository has useful parts, but no connected historical evaluation workflow.
Its active FastAPI/React application is a live and synthetic-playback dashboard.
A separate file-oriented application exists inside `neraium_core/sii`, alongside
multiple local analysis implementations. Renaming the dashboard would leave
conflicting analytical authority and unsuitable data handling in place.

### Actual execution paths

1. `backend/server.py` mounts systems, playback, audit, customers, ingest, demo,
   and WebSocket routers. Ingestion calls `backend/services/sii_state.py`, then
   `neraium_core/sii_engine_adapter.py`, then `sii_engine_unified.py`.
2. `neraium_core/sii_cli.py` calls `sii/SIIApplication`, which loads CSV/JSON,
   processes records through `sii/engine.py`, and writes CSV/JSON reports. This
   uses a different engine from the mounted web API.
3. `backend/services/neraium_engine_impl.py` wraps state/decision services with
   additional hazard, trajectory, and bearing-specific rules. The resolver calls
   this “canonical”; `backend/routers/neraium.py` exists but is not mounted by
   `server.py`. Neither is a Neraium-1.0 integration.

## Reuse inventory

| Area | Existing source | Disposition |
|---|---|---|
| CSV/JSON parsing and validation | `neraium_core/sii/ingestion.py`, `types.py`, `errors.py` | Reuse selected helpers after comparing with 1.0 ingestion. Existing code handles numeric validity, missingness, source metadata, identity fields, and analysis tables. CSV requires timestamp/site/asset columns; it is not a general mapping UI. |
| Batch/file orchestration | `neraium_core/sii/app.py`, `sii_cli.py` | Retain the file-in/result-out pattern; replace the local engine dependency and separate live-provider configuration. |
| Report serialization | `neraium_core/sii/reporting.py` | Reuse file-writing/serialization utilities. Current field projections target local engine outputs and need authoritative result/evidence fields. |
| UI shell and charts | `frontend/src/index.css`, `components/TechnicalCharts.js`, `InstabilityChart.js`, `SignalLayerPanel.js` | Candidate presentation reuse with historical time ranges and immutable run results. Keep only components that fit the new workflow; do not carry forward computed verdicts. |
| Reviewer notes | `backend/routers/audit.py`, `components/AuditView.js` | Reuse selected note/display patterns. Current transition log is not an evaluation review ledger; it needs evaluation/run identity and durable review history. |
| Explanation presentation | `components/OperatorExplanationReport.js`, `services/operator_explanation_context.py` | Useful layout and separation of known-event validation context from engine input. Existing report is PRONOSTIA-specific and imports a `Pronostia` API export absent from `api.js`; not a working generic report screen. |
| Tests and fixtures | `tests/`, `backend/tests/`, `fixtures/` | Preserve small relevant examples where useful. Existing tests mostly concern legacy engines/demos; their expectations are not the new analysis contract. |

## Obsolete for this workbench

- **Live dashboard workflow:** `frontend/src/App.js` subscribes to 500 ms WebSocket
  snapshots, polls playback status every second, and prioritizes current regime.
  Replace navigation with evaluation stages; retire live banners, playback speed,
  monitoring controls, and live narration from the workbench path.
- **Synthetic playback:** `backend/services/playback.py` generates synthetic
  systems and calls `ss.reset_all()` when starting. This must not share state with
  customer evaluation runs. Retire its routes/UI from the workbench runtime.
- **Customer integration setup:** `routers/customers.py`, `routers/ingest.py`,
  and `SettingsView.js` implement customer API-key/frame-ingest workflows.
  Replace with internal evaluation metadata and bounded historical intake.
- **Product positioning and deployment guidance:** README describes real-time
  Neraium Grow; Grow/customer deployment, launch, and live ingestion documents
  reflect the old product. Rewrite only the retained workbench entrypoints after
  the runtime boundary is established.
- **Stale instructions:** `docs/PIPELINE_MAP.md` claims a single path through
  absent `alignment.py`/`service.py`; `RAW_INGESTION.md` invokes missing
  `tools/run_raw_data.py`; `PROOF_PACKAGE_WORKFLOW.md` invokes missing
  `tools/run_proof_package.py`. These are not evidence of implemented capability.
- **Stale CI:** `ci.yml` reads an absent `requirements.txt`;
  `multinode-benchmark-gate.yml` calls an absent runner; `fd004-hero-plot.yml`
  references absent `fd004_real`/`fd004_plotting` modules. Retire obsolete jobs and
  repair focused CI when implementation begins; do not run them to audit this repo.

“Retire” means remove from the intended application path, with historical code
preserved in version control. This audit deletes nothing.

## Duplication with Neraium-1.0

| Responsibility duplicated in App | Neraium-1.0 reference | Recommendation |
|---|---|---|
| Parsing, data quality, identity and mapping | `backend/app/services/historical_ingestion.py`, `upload_parser.py`, `upload_validator.py`, historical-ingestion router | Prefer established contracts/helpers. Inspect applicability before extracting; historical upload interfaces are being changed locally. |
| SII scoring and state interpretation | `backend/app/engine/sii_engine.py`, `engine/analysis.py`, `services/sii_runner.py` | Integrate a pinned authoritative analysis boundary. Do not maintain App's unified/advanced/local SII engines as an independent customer-result authority. |
| Result normalization and evidence | `backend/app/services/analysis_result_contract.py`, `engine_identity.py` | Preserve canonical results, limitations, and provenance instead of re-scoring in App's adapters or UI. |
| Evidence persistence and historical comparisons | `shared/neraium-intelligence` | Reuse compatible versioned contracts. This package does **not** contain the full analysis engine. |
| Customer-facing explanation/report concepts | `backend/app/services/operator_report.py` | Compare output contracts and presentation helpers before creating another report interpretation layer. |
| Canonical telemetry mapping and run orchestration | Local untracked `canonical_signal_catalog.py`, `signal_registry.py`, `telemetry_analysis_service.py` and related services | Relevant emerging ownership boundary, not a released dependency. Do not copy or silently depend on unfinished local work. |

A SHA-256 comparison found no identical tracked Python/JS/TS source files larger
than 200 bytes against Neraium-1.0's local working files. The duplication above is
functional responsibility, not a claim of identical source or proven shared
history. The comparison excludes smaller, non-source, and untracked files.

## Old demo and research material

- `backend/services/pronostia_demo.py`, `pronostia_decision_layer.py`,
  `live_pronostia_ingestion.py`, `synthetic_systems.py`, and demo/playback/live
  routers; frontend PRONOSTIA components, lead-time helpers, demo controls,
  future-path presentation, and narration.
- `tools/` includes IMS/PRONOSTIA/CMAPSS/WUR runners, threshold tuning, sweeps,
  benchmarks, and demo launchers. Keep useful tiny fixtures separately; do not
  include benchmark execution in normal evaluation workflow or routine checks.
- `sii_engine_advanced.py`, validation/sensitivity/comparison modules, and the
  bearing-specific hazard/failure/intervention code need archival classification
  before removal. They are not the authoritative Neraium-1.0 implementation.
- `results/` contains 93 tracked artifacts. Treat these as legacy outputs pending
  individual provenance review, not customer evidence. Inventory counts alone do
  not establish their validity or authorize deletion.

## Blocking behaviors and missing workflow

1. **Missing data becomes evidence:** `sii_state.ingest_frame` substitutes `0.0`
   for absent configured signals. Preserve missingness and validation outcomes.
2. **Unknown becomes stable:** `_smoothed_regime` maps warmup/unknown to STABLE;
   `App.js` does likewise for the title. Preserve insufficient-evidence states.
3. **History is temporary:** process-global systems retain only 600 frames under
   run ID `live`; playback resets them. Introduce durable evaluation, dataset,
   mapping-revision, run, and artifact identity before handling customer history.
4. **Errors can become invented analysis:** `neraium_engine_impl.update` catches
   every engine exception and substitutes `_simple_drift`; it also substitutes
   cycle for timestamp and carries bearing-specific minimum actionable cycles.
   Authoritative analysis failures must produce explicit failed/limited outcomes.
5. **No connected evaluation lifecycle:** no mounted historical file intake,
   validation review, mapping approval, explicit baseline/analysis-window setup,
   durable run execution, or customer report approval/export workflow was found.
   The separate CLI covers only part of this chain.
6. **Audit is not reliable run provenance:** the background scanner repeatedly
   traverses retained histories and suppresses write exceptions. Store run-linked
   evidence and reviewer decisions explicitly rather than inferring them from
   live transitions.

## Minimal implementation sequence

1. Establish the workbench purpose in retained documentation and navigation;
   remove demo/live entrypoints from the active workflow without rewriting
   reusable charts or parsers.
2. Define evaluation/dataset/run records and immutable source artifacts, including
   customer/prospect identity, source hashes, timestamp/unit policy, mapping
   revision, context, and selected baseline/analysis intervals.
3. Connect bounded file intake, validation preview, and reviewed signal/system
   mapping. Persist exclusions, unresolved signals, transformations, and quality
   limitations before analysis eligibility is determined.
4. Add one adapter to a pinned Neraium-1.0 analysis interface. Record engine and
   configuration versions and input provenance; propagate failures explicitly.
   Whether this is a package or service requires dependency-boundary inspection;
   the shared evidence package alone cannot execute analysis.
5. Render stored authoritative results and supporting evidence, collect reviewer
   interpretation, and export a report with scope, quality, mapping/context,
   methods/version, findings or insufficient evidence, limitations, and review
   status. Keep reviewer prose distinct from engine evidence.
6. Remove obsolete active dependencies and repair focused checks only after
   references are disconnected. Test changed parsing, run isolation, authority
   handoff/failure propagation, and report provenance with tiny inputs.

No production-app fork, live scheduler, benchmark run, or full rewrite is needed
to establish this boundary. The immediate deliverable is a small connected
historical evaluation path using existing authoritative analysis.
