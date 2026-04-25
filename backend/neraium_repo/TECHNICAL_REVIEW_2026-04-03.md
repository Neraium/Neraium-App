# neraium-core Technical Architecture Review (2026-04-03)

## 1) Architecture analysis

- Ingestion and normalization are split across `pipeline.py`, `ingestion_normalization.py`, `adapters/raw_telemetry_adapter.py`, and parts of `service.py`. This gives broad format coverage, but the boundaries are fuzzy: `pipeline.py` still includes both modern CSV normalization and a legacy `TelemetryPipeline` scoring path in the same file.
- Core runtime inference is centralized in `alignment.py` via `StructuralEngine`, which is very large and imports a wide set of analytics modules directly. This acts as a monolith orchestration + feature + scoring + debug surface.
- Service orchestration (`service.py`) owns request normalization, per-asset engine lifecycle, persistence, canonical output shaping, memory recall, and policy overlays. This concentrates too many cross-cutting concerns into one class.
- Live market ingestion is implemented via connector abstractions (`data_connectors.py`) and CLI orchestration (`run_live_stock_market.py`), then adapted into the same frame contract (`stock_market_adapter.py`). This is good reuse of engine-facing contracts.

## 2) Data flow trace

### Batch / API telemetry path
`raw payload` -> `normalize_external_payload` alias/mapping inference -> `CanonicalIngestionSignalRecord` -> `build_frame` contract (`timestamp/site/asset/customer/sensor_values`) -> `StructuralEngine.process_frame` -> service interpretation/decorators -> `build_canonical_output` -> persisted history + memory records.

### CSV path
`csv_text` -> `parse_csv_rows` -> inferred/validated semantic mapping -> `normalize_csv_rows_to_canonical` -> `canonical_records_to_frames` -> service ingestion loop -> canonical output + persistence.

### Live market path
provider API/mock -> connector-normalized bars -> `build_stock_frame` -> `process_live_frame` -> state/signal mapping + optional CSV append.

## 3) Code quality review

- **Modularity**: `alignment.py` and `service.py` are overloaded and difficult to reason about in isolation.
- **Naming / duplication**: There are duplicate domain loaders (`market_data_loader.py` at root and `markets/data/market_data_loader.py`) plus legacy compatibility modules coexisting with current paths.
- **Error handling consistency**: Mixed strict vs permissive behavior (e.g., pilot hardening toggles strictness) and several broad exception handlers in persistence/util layers risk masking root causes.
- **Technical debt signals**: very large files, mixed legacy/current code in same modules, and debug print paths in the engine.

## 4) Risk analysis

- **Silent failure risk**: multiple decode/serialization and helper paths swallow exceptions and default to empty objects.
- **Data integrity risk**: fallback timestamp auto-fill and optional non-strict coercion can admit partially malformed records; market adapter converts timestamp to float while the generic pipeline uses ISO strings, creating contract ambiguity across ingestion paths.
- **Performance/scaling risk**: per-asset in-memory engine registry in service has no eviction strategy; high-cardinality asset streams will keep growing engine objects.
- **Security/input risk**: external API pulls use `urlopen` without retries/backoff/circuit-breaker policy; no unified validation envelope for external payload schemas before normalization.

## 5) Test coverage gaps

Existing tests cover ingestion alias mapping, connector basics, and CLI argument handling. Missing critical coverage:

- end-to-end assertions that canonical output contract remains stable across raw payload, CSV, and live market paths;
- stress/soak tests for high-cardinality asset churn and service engine-cache growth;
- connector failure matrix tests (timeouts, malformed payload variants, rate-limit retries, partial ticker failures);
- property tests for mapping ambiguity and sensor coercion edge cases under both strict and non-strict hardening modes;
- regression tests around legacy/server paths that currently contain unsafe code patterns.

## 6) Refactor plan (high impact)

1. **Extract `StructuralEngine` orchestration shell from analytics stages**:
   - keep thin coordinator in `alignment.py`;
   - move stage groups into `neraium_core/engine_stages/*` with explicit typed stage I/O contracts.

2. **Split `StructuralMonitoringService` into explicit boundaries**:
   - `ingestion_service.py` (normalization + validation),
   - `engine_registry.py` (engine lifecycle + run config),
   - `result_projection.py` (interpretation/canonical output),
   - `memory_service.py` (recall/dedup/persistence policies).

3. **Unify frame contract typing**:
   - introduce a shared `Frame` dataclass / pydantic model used by telemetry + market adapters;
   - enforce one timestamp representation (ISO UTC string) at engine ingress.

4. **Create explicit error policy layer**:
   - replace broad `except Exception: pass` style branches with typed recoverable errors and structured failure counters.

5. **Separate legacy compatibility code from production path**:
   - move `TelemetryPipeline` and legacy helpers into `neraium_core/legacy/*` to reduce accidental use and improve readability.

## 7) Production readiness

Current state is **not production-ready** for sustained workloads.

What is present:
- reasonable normalization primitives and explicit issue codes in CSV ingestion;
- per-asset engine isolation and persistence primitives;
- basic tests across many modules.

What is still missing for production hardening:
- clear deployment/config story (packaging metadata and dependency lock strategy are incomplete);
- CI/CD policy in-repo (lint/type/test/release gates);
- stronger observability standards (metrics/tracing/error budget counters, not only logs);
- bounded resource controls (engine cache lifecycle, connector retry budgets, backpressure);
- strict contract/version conformance tests across all entrypoints.

## Final verdict

**early-stage system** — impressive breadth and experimentation velocity, but core runtime boundaries, error-policy consistency, and operational hardening are not yet mature enough for reliable production operation at scale.
