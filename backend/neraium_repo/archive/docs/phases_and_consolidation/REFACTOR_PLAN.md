# Structural Architecture Refactor Plan

## Current State Assessment

### alignment.py (3416 lines)
**Single monolithic file containing:**
- Frame ingestion & window management
- Core structural detection (drift, relational instability, temporal coherence)
- Regime tracking & transitions
- Rolling baseline management
- Policy state machine (WATCH/ALERT)
- Data quality gates & degraded mode
- **Heavy auxiliary analytics** inline (causal, hierarchy, constraint, horizon, branching, counterfactuals)
- Experimental features (path prototypes, trajectory analysis)
- Packaging & output assembly
- Fast mode logic mixed throughout

**Line count breakdown (estimated):**
- Initialization: ~400 lines
- Core runtime (frame processing + drift/relational/temporal detection): ~1200 lines
- Auxiliary analytics (causal, graph, hierarchy, experimental): ~1100 lines
- Packaging/output assembly: ~400 lines
- Utility methods: ~316 lines

**Complexity issues:**
- Multiple responsibilities deeply coupled
- Auxiliary metrics influence core scoring implicitly
- Fast mode introduces branching inside core logic
- Packaging logic mutates core results
- No clear entry points for each responsibility level

---

## Target Architecture

### Layer 1: Core Runtime (Minimal, production-critical)
**Module:** `neraium_core/engine/core.py`

**Responsibilities:**
- Frame ingestion
- Window slicing & baseline management
- Sensor normalization & NaN handling
- Data quality assessment (gate pass/fail)
- Representation building (temporal features)
- Correlation matrix computation

**Methods to move:**
- `_vector_from_frame()`, `_normalize_sensor_vector()`
- `_extract_windows_from_chronological()`
- `_get_baseline_timestamps()`, `_get_recent_timestamps()`
- Window validation helpers
- Frame caching & incremental window logic
- Data quality computation

**Output:**
- Normalized baseline/recent windows
- Correlation matrices
- Data quality report
- Valid sensor mask

---

### Layer 2: Detection Components (Core critical)

#### A. Windows Manager: `neraium_core/engine/windows.py`

**Move:**
- Window extraction & caching logic
- Baseline matrix cache management
- History ring buffer usage
- Incremental window updates
- `_invalidate_window_caches()`, `_refresh_baseline_matrix_cache()`
- `_materialize_strided_recent()`
- `_extract_windows_from_chronological()`
- `_windows_ready()` validation

---

#### B. Structural Drift: `neraium_core/engine/drift.py`

**Move:**
- Drift score computation from recent vs baseline correlation
- EMA smoothing of drift
- Drift state machine (thresholds, calibration)
- Drift history tracking
- `_update_drift_state_machine()`
- `_drift_alert()`, `_alert_state()`
- Threshold calibration from baselines
- `_system_health()` (derives from drift + stability)

**Pure computation, no side effects.**

---

#### C. Relational Instability: `neraium_core/engine/relational.py`

**Move:**
- Relational stability score (corr frame-to-frame)
- Relational drift (baseline vs recent relationship changes)
- Graph metrics (adjacency, thresholded structure)
- Graph-based instability signals
- Signal structural importance (per-node criticality)
- Subsystem spectral measures

**Pure computation, no side effects.**

---

#### D. Temporal Coherence: `neraium_core/engine/temporal.py`

**Move:**
- Temporal feature extraction from recent window
- Temporal quality signals
- Lag-based correlation features
- Time-to-instability forecasting
- Temporal coherence stage scoring

**Pure computation, no side effects.**

---

#### E. Transitions & Readiness: `neraium_core/engine/transitions.py`

**Move:**
- Transition pressure computation
- Shock detection & activity tracking
- Regime novelty & regime baseline updates
- Dominant mode tracking
- Transition state classification (NONE/EMERGING/SUSTAINED)
- Engine readiness checks
- `_transition_metrics()`
- `_transition_state()`
- Transition history management

**Pure computation, no side effects on core state.**

---

### Layer 3: Auxiliary Analytics (Isolated, optional)

**Module:** `neraium_core/auxiliary/`

**All non-critical enrichment modules go here:**
- `causal_intelligence.py` (causal matrix, hypotheses, actions)
- `graph_analysis.py` (causal graphs, propagation, chains)
- `hierarchy_analysis.py` (cascade direction, localization)
- `counterfactual_guidance.py` (reversibility, futures simulation)
- `path_prototypes.py` (trajectory shape, directional evolution)
- `horizon_analysis.py` (risk horizon estimation)
- `constraint_analysis.py` (lock-in scoring)
- `branching_analysis.py` (branching decisions)

**Key rule:** Core runtime must NOT depend on any auxiliary module.

**Import protection:** Use feature flags (env vars) to gate expensive auxiliary computations.

---

### Layer 4: Orchestration: `neraium_core/engine/orchestration.py`

**New responsibility:**
- StructuralEngine no longer implements all logic inline
- Instead: coordinates calls between core + auxiliary
- Explicitly calls:
  1. Core window & data quality layer
  2. Detection components (drift, relational, temporal, transitions)
  3. Optional auxiliary analytics (if enabled)
  4. Final packaging
- Clear data flow: frame → windows → detections → [optional aux] → packaged result

**Pseudo-structure:**
```python
class StructuralEngineOrchestrator:
    def process_frame(self, frame: Dict) -> Dict:
        # 1. Core: ingest & normalize
        vector = core.ingest(frame)
        baseline, recent = windows.extract()
        dq_report = core.assess_quality(baseline, recent)
        
        # 2. Core: compute detections
        drift_result = drift_detector.compute(corr_baseline, corr_recent)
        relational_result = relational_detector.compute(...)
        temporal_result = temporal_detector.compute(...)
        transition_result = transition_detector.compute(...)
        
        # 3. Optional: auxiliary
        if should_run_auxiliary():
            causal = auxiliary.causal_intelligence(...)
            hierarchy = auxiliary.hierarchy_analysis(...)
            ...
        
        # 4. Package
        return packaging.assemble(drift_result, relational_result, ..., auxiliary_results)
```

---

### Layer 5: Packaging & Output: `neraium_core/engine/packaging.py`

**Move:**
- Result template creation (`_default_result_payload()`)
- Schema assembly
- Output field formatting
- Backward-compatible field mapping
- Safe defaults for warmup/degraded modes
- `_safe_default_tetrahedral_payload()`
- `_analytics_unavailable_payload()`

**Key rule:** Pure assembly, no computation.

---

### Layer 6: Baseline & State Management: `neraium_core/engine/state.py`

**Move:**
- Rolling baseline correlation tracking
- Baseline lock/unlock logic
- Regime library persistence
- Regime baseline updates
- Episode memory
- State snapshots for restore
- `reset_baseline()`, `lock_baseline()`
- `snapshot_state()`, `restore_state()`
- `_persist_regime_state()`

**This layer is stateful and singleton-like; separate from pure detection.**

---

## File Structure After Refactor

```
neraium_core/
├── alignment.py                 # ENTRY POINT ONLY (thin facade)
│
├── engine/
│   ├── __init__.py
│   ├── core.py                 # Frame ingest, normalization, QA
│   ├── windows.py              # Window extraction & caching
│   ├── drift.py                # Structural drift detection
│   ├── relational.py           # Relational instability
│   ├── temporal.py             # Temporal coherence
│   ├── transitions.py          # Transition pressure & state
│   ├── orchestration.py        # Coordinate core + aux
│   ├── packaging.py            # Output assembly
│   ├── state.py                # Baseline, regime, episodes
│   └── config.py               # Constants & thresholds
│
├── auxiliary/
│   ├── __init__.py
│   ├── causal_intelligence.py  # Causal metrics, hypotheses
│   ├── graph_analysis.py       # Causal graphs, chains
│   ├── hierarchy_analysis.py   # Cascade direction (moved)
│   ├── counterfactual_guidance.py  # Reversibility (moved)
│   ├── path_prototypes.py      # Trajectory shapes (moved)
│   ├── horizon_analysis.py     # Risk horizon (moved)
│   ├── constraint_analysis.py  # Lock-in scoring (moved)
│   └── branching_analysis.py   # Branching paths (moved)
│
└── ... (existing modules unchanged)
```

---

## Migration Sequence

### Phase 1: Infrastructure (Day 1)
1. Create `engine/` directory with `__init__.py`
2. Create `auxiliary/` directory with `__init__.py`
3. Create `engine/config.py` with all constants
4. Create empty `engine/*.py` modules (stubs only)
5. **Branch commit:** Infrastructure scaffolding

### Phase 2: Extract Core (Day 2-3)
1. **windows.py**: Move window extraction + caching logic
2. **core.py**: Frame ingest, normalization, QA
3. Update imports in alignment.py
4. **Branch commit:** Core window & ingest logic extracted

### Phase 3: Extract Detection Components (Day 3-4)
1. **drift.py**: Structural drift detection
2. **relational.py**: Relational instability
3. **temporal.py**: Temporal coherence
4. **transitions.py**: Transition metrics & state
5. Wire detectors into alignment.py
6. **Branch commit:** Detection components extracted

### Phase 4: Orchestration & Packaging (Day 4-5)
1. **orchestration.py**: Coordinate all detections
2. **packaging.py**: Output assembly
3. **state.py**: Baseline & regime management
4. Refactor alignment.py to delegate to orchestrator
5. **Branch commit:** Orchestration & packaging extracted

### Phase 5: Auxiliary Isolation (Day 5)
1. Move experimental_analytics + causal modules to auxiliary/
2. Add feature gates (env vars) to skip expensive computations
3. Update orchestration.py to optionally call auxiliary
4. **Branch commit:** Auxiliary modules isolated

### Phase 6: Testing & Validation (Day 6)
1. Run existing tests (FD001, FD004)
2. Verify output contract unchanged
3. Add unit tests for each detection component
4. Add integration tests for orchestration
5. **Branch commit:** Tests & validation

### Phase 7: Documentation & Cleanup (Day 6-7)
1. Document public APIs
2. Add module-level docstrings
3. Create ARCHITECTURE.md guide
4. Remove old code, cleanup
5. **Final commit:** Cleanup & documentation

---

## Complexity Reduction Metrics

### Before
- alignment.py: 3416 lines
- Single class with 50+ methods
- 18 imports from auxiliary modules in core path

### Target
- alignment.py: ~200 lines (only entry point)
- orchestration.py: ~400 lines (coordination)
- drift.py, relational.py, temporal.py, transitions.py: ~250 lines each
- Total production-critical path: ~1500 lines (56% reduction)
- Core responsibility separation clear

### Code Quality
- Each module has **one reason to change**
- No implicit coupling via shared state
- Clear data flow: input → detect → package → output
- Fast mode/degraded mode handled as policy, not branching

---

## Determinism & Validation

### No-Change Contract
- Given identical frame inputs, outputs must be identical pre/post refactor
- Numeric precision preserved (same rounding)
- Random/experimental components isolated in auxiliary
- State mutations only in state.py

### Testing Strategy
1. **Regression tests:** FD001/FD004 lead time unchanged
2. **Component tests:** Each detector produces same results
3. **Integration tests:** Orchestrator + packaging preserves schema
4. **Degraded mode:** Gate failure handling unchanged
5. **Fast mode:** Output contract same, computation deferred

### Validation Harness
```python
# Light script-friendly validator
class RegressionValidator:
    def run_fd001(self, engine: StructuralEngine) -> Dict[str, float]:
        # Lead time per unit
        # Decision state counts (ADMIT/SUPPRESS/VOID)
        # Runtime per frame
        pass
    
    def run_fd004(self, engine: StructuralEngine) -> Dict[str, float]:
        # Similar metrics
        pass
```

---

## Fast Mode Cleanup

### Current: Branching inside core
```python
# BAD: Fast mode logic mixed in
if self.fast_mode:
    geometry_payload = self._fast_mode_geometry_payload(...)
else:
    geometry_payload = self.geometry_layer.update(...)
```

### Target: Policy wrapper
```python
# GOOD: Deferred as policy
geometry_result = orchestration.compute_geometry(
    z_recent_valid, 
    policy=PolicyMode.FAST if self.fast_mode else PolicyMode.FULL
)

# Inside compute_geometry:
if policy == PolicyMode.FAST:
    return CACHED_PAYLOAD
else:
    return geometry_layer.update(...)
```

**Result:** Core code never branches on fast_mode; it's a pure configuration policy.

---

## Non-Goals (What's NOT changing)

- Algorithm logic is unchanged
- Numeric behavior is preserved
- Output schema is compatible
- Warmup behavior unchanged
- Degraded mode logic unchanged
- Regime library mechanics unchanged
- State machine thresholds unchanged

---

## Success Criteria

✅ alignment.py reduced from 3416 to <300 lines  
✅ Core runtime path (frame→detection) is readable top-to-bottom  
✅ Auxiliary modules can be disabled without breaking core  
✅ Fast mode is policy, not branching  
✅ No numeric changes to outputs (regression tests pass)  
✅ Each module has clear, single responsibility  
✅ All existing tests pass  
✅ New architecture documented

