# Phase B: Unify Product Surface

**Status**: Planning phase  
**Date**: 2026-04-13  
**Objective**: Create one coherent, unified product surface after Phase A contract stabilization

---

## Overview

Phase A stabilized the *internal* contract (canonical frame format, ingestion adapters, etc.).

Phase B unifies the *external* product experience:
1. **One canonical entrypoint** – clear, documented way to use the system
2. **One runtime path** – replay, live ingestion, and evidence flow through the same interface
3. **One validation command** – produces all benchmarks and investor artifacts
4. **One production narrative** – documentation matches measured reality

---

## Phase B Deliverables

### 1. Canonical Entrypoint (`neraium_core/engine/__init__.py`)

**Goal**: Users import and use one clear interface, not three overlapping ones.

Currently (fragmented):
- `from neraium_core.alignment import StructuralEngine` (internal, low-level)
- `from neraium_core.engine.production import ProductionEngine` (production wrapper)
- `from validation.shadow_mode import run_replay` (validation, scattered)
- Various validation scripts in `/scripts/`

**Target**: One unified entrypoint

```python
from neraium_core import Engine

# Users should be able to do:
engine = Engine(baseline_window=12, recent_window=6)
result = engine.ingest_frame(timestamp=..., asset_id=..., sensors={...})

# Or for batch/validation:
engine.replay(dataset_path="FD004.csv", dataset_type="fd004")
evidence = engine.get_evidence_report()
```

**Implementation**:
1. Create unified `Engine` class that wraps StructuralEngine + ProductionEngine behavior
2. Expose three use cases: `ingest_frame()`, `replay()`, `get_evidence()`
3. Update `__init__.py` to export `Engine` as the primary interface
4. Mark `StructuralEngine` and `ProductionEngine` as internal (underscore prefix)

---

### 2. Unified Runtime Path

**Goal**: All three modes (replay, live, evidence) flow through the same engine with consistent output.

Currently (parallel paths):
- **Replay path**: Load CSV → validation scripts → shadow mode runner → diff reports
- **Live path**: ProductionEngine.process_frame() → EngineResult
- **Evidence path**: Shadow mode runs replay separately, generates evidence

**Target**: Single runtime that produces consistent artifacts

```
Dataset/Stream
    ↓
Engine.ingest_frame() [normalized by adapters]
    ↓
StructuralEngine.process_frame() [core processing]
    ↓
Unified Output Format
    ├── state, drift, health metrics
    ├── evidence (if shadow mode enabled)
    └── causal attribution (if analytics enabled)
```

**Implementation**:
1. `Engine.ingest_frame()` always returns same schema (EngineResult)
2. `Engine.replay()` iterates through frames, collects results
3. `Engine.get_evidence_report()` aggregates shadow mode data
4. Remove duplicate logic in validation scripts

---

### 3. One Official Validation Command

**Goal**: `neraium-core validate` produces all benchmarks and investor artifacts in one pass.

Currently (scattered):
- `scripts/run_full_validation.py` – metrics, plots, lead time summary
- `validation/shadow_mode/` – replay diff, evidence logs
- Various manual plotting/reporting scripts
- Multiple output formats and structures

**Target**: Single canonical validation command

```bash
neraium-core validate \
  --fd004 ./FD004.csv \
  --ims ./IMS.csv \
  --output ./results

# Produces single output structure:
./results/
├── FD004/
│   ├── metrics.json          # All benchmark metrics
│   ├── hero_plot.png         # Investor-safe visualization
│   ├── validation_report.md  # Measured performance
│   └── evidence_log.json     # Shadow mode evidence
├── IMS/
│   └── [same structure]
└── VALIDATION_REPORT.md      # Overall summary
```

**Implementation**:
1. Create `neraium_core/cli.py` with `validate` command
2. Consolidate metric computation (one `compute_metrics()`)
3. Consolidate plot generation (one `generate_plots()`)
4. Consolidate reporting (one `generate_report()`)
5. Wire up shadow mode evidence as option flag
6. Create machine-readable JSON output alongside markdown

---

### 4. Authoritative Production Documentation

**Goal**: One doc that says "use this" with only measured claims.

Currently (inconsistent):
- Multiple `README.md` files with different audiences
- Claims about latency/throughput that may not match measured validation
- Theoretical "targets" mixed with observed results
- No clear "is this production-ready?" answer

**Target**: One `PRODUCTION_READINESS.md` that is authoritative

```markdown
# Production Readiness

## Measured Performance (FD004 validation)
- Latency per frame: [measured value] ms
- Throughput: [measured value] frames/sec
- Memory per unit: [measured value] MB
- Baseline window accuracy: [measured value]%

## Known Limitations
- Evolving sensor schemas (handled with dynamic registration)
- Cold start (requires baseline window of [N] frames)
- [List actual operational constraints]

## Deployment Checklist
- [ ] Baseline window filled with clean data
- [ ] All sensors reporting numeric values
- [ ] Site ID configured
- [ ] Shadow mode enabled for first 7 days (optional)

## Support / Troubleshooting
[Actual operational guidance, not theoretical]
```

**Implementation**:
1. Create `PRODUCTION_READINESS.md`
2. Extract measured values from latest validation report
3. Remove theoretical claims from existing docs
4. Demote old READMEs to `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`
5. Update main README to point to both entry point guide + production readiness

---

## Phase B Implementation Sequence

### Week 1: Core Entrypoint
- [ ] Create unified `Engine` class
- [ ] Implement `ingest_frame()`, `replay()`, `get_evidence()`
- [ ] Update `__init__.py` to export `Engine`
- [ ] Write usage examples in docstring

### Week 2: Runtime Unification
- [ ] Consolidate metric computation
- [ ] Unify output schema (EngineResult for all paths)
- [ ] Wire shadow mode into unified runtime
- [ ] Verify all three paths produce consistent results

### Week 3: Validation Command
- [ ] Create CLI interface (`neraium_core/cli.py`)
- [ ] Implement `validate` command with all options
- [ ] Consolidate plotting/reporting logic
- [ ] Generate both markdown and JSON outputs

### Week 4: Documentation
- [ ] Extract measured metrics from validation
- [ ] Write `PRODUCTION_READINESS.md`
- [ ] Update main README with clear entry point
- [ ] Create deployment checklist

---

## Phase B Success Criteria

✓ Users can `from neraium_core import Engine` and know that's the right way  
✓ All three modes (replay, live, evidence) produce consistent output schema  
✓ One `neraium-core validate` command produces all benchmark artifacts  
✓ One `PRODUCTION_READINESS.md` is authoritative and matches measured data  
✓ No contradictions between documentation and measured performance  
✓ Old documentation clearly marked as historical/reference  

---

## Architectural Outcome

After Phase B, the repo narrative becomes:

> **Neraium** is a structural drift detection engine for industrial equipment.
>
> **Use it**: `from neraium_core import Engine`
>
> **Validate it**: `neraium-core validate --fd004 ./data.csv`
>
> **Deploy it**: See [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md)
>
> **Learn it**: See [ARCHITECTURE.md](./docs/ARCHITECTURE.md)

No more fragmentation. One product, one interface, one story.

