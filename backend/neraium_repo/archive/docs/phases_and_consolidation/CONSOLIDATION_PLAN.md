# Neraium Structural Engine Consolidation Plan

**Status:** PROPOSAL FOR REVIEW  
**Date:** 2026-04-13  
**Goal:** One canonical engine, one canonical runner path, one canonical benchmark path

---

## CURRENT STATE: INVENTORY & CLASSIFICATION

### ENGINES (2 IMPLEMENTATIONS - CONFLICT!)

#### 1. ✅ CANONICAL: `neraium_core/alignment.py::StructuralEngine`
- **Lines:** ~3,694  
- **Status:** CANONICAL (current implementation)
- **Features:**
  - Latest implementation with full feature set
  - Wraps into ProductionEngine → unified Engine
  - Used by modern FD004/FD001 runs
  - Tetrahedral state integration support
  - Part of production API surface
- **Recent commits:** Multiple improvements (Priority 1&2 engine detection, frame contract fixes, fast-mode optimizations)
- **Used by:**
  - `run_fd004_canonical.py` ✅
  - `run_fd004_fast.py` ✅
  - `run_fd004.py` ✅
  - `run_cmapss_suite_batched.py` ✅
  - `run_cmapss_one_visible.py` ✅
  - `run_demo.py` ✅
  - `live_runner.py` ✅
  - `examples/demo/*` ✅
  - `greenhouse_demo/*` ✅
  - `neraium_core/engine/production.py` ✅
  - `neraium_core/service.py` ✅
  - `evaluation/representation_compare.py` ✅
  - `neraium_core/benchmarks/platform_hotpath.py` ✅

#### 2. ❌ DEPRECATED: `run_engine.py::StructuralEngine`
- **Lines:** 1,376  
- **Status:** DEPRECATED/DUPLICATE (old implementation)
- **Problem:** Exists as a root-level file, confusing due to name collision with modern engine architecture
- **Last meaningful update:** ~3 commits ago (mostly lint fixes)
- **Used by (DEPRECATED RUNNERS):**
  - `run_fd004_by_unit.py` ❌
  - `run_fd004_simple.py` ❌
  - `run_ims_production.py` ❌
  - `run_ims_production_final.py` ❌
  - `run_ims_production_final_combined.py` ❌
  - `run_ims_production_full.py` ❌
  - `run_ims_production_v1500.py` ❌
  - `run_ims_production_v2.py` ❌
  - `run_ims_full_and_plot.py` ❌

---

### RUNNER SCRIPTS (28 root-level runners)

#### Category A: ✅ CANONICAL RUNNERS (using alignment.py)
1. `run_fd004_canonical.py` - FD004 canonical benchmark runner
2. `run_fd004_canonical_fast.py` - FD004 fast mode variant
3. `run_fd004_fast.py` - FD004 with fast-mode optimization
4. `run_fd004.py` - FD004 standard runner
5. `run_cmapss_suite_batched.py` - CMAPSS batched runner
6. `run_cmapss_one_visible.py` - CMAPSS single unit runner
7. `run_cmapss_suite.py` - CMAPSS full suite runner
8. `run_demo.py` - Demo/development runner
9. `run_live.py` - Live production runner
10. `run_pilot.py` - Pilot program runner

#### Category B: ❌ DEPRECATED RUNNERS (using old run_engine.py)
1. `run_fd004_by_unit.py` - OLD: per-unit variant
2. `run_fd004_simple.py` - OLD: simplified runner
3. `run_fd004_with_ims_policy.py` - OLD: policy variant
4. `run_fd004_with_ims_policy_tuned.py` - OLD: tuned policy variant
5. `run_ims_production.py` - OLD: IMS production runner
6. `run_ims_production_final.py` - OLD: IMS final variant
7. `run_ims_production_final_combined.py` - OLD: combined variant
8. `run_ims_production_full.py` - OLD: full IMS runner
9. `run_ims_production_v1500.py` - OLD: v1500 variant
10. `run_ims_production_v2.py` - OLD: v2 variant
11. `run_ims_full_and_plot.py` - OLD: with visualization

#### Category C: ⚠️ EXPERIMENTAL / UNCERTAIN
1. `run_live_stock_market.py` - Custom use case (unclear status)
2. `run_upgraded_multinode_test.py` - Test runner (likely test artifact)
3. `test_falsification_layer.py` - Test file (not a runner)
4. `test_fixes.py` - Test file (not a runner)
5. `experiment.py` - Experiment artifact
6. `test_predeploy.py` - Pre-deploy test
7. `INTEGRATION_GUIDE.py` - Documentation/example (not a runner)

---

### BENCHMARK & VALIDATION SCRIPTS

#### Root Level Benchmarks:
1. `benchmark_fd004_policies.py` - FD004 policy comparison (generates CSVs)
2. `compare_fd004_policies.py` - FD004 policy scoring
3. `generate_post_fix_validation_report.py` - Post-fix validation

#### Validation Module (`validation/`):
1. `fast_validation.py` - Fast validation runner
2. `production_validation.py` - Production validation runner
3. `production_validation_evidence.py` - Evidence generation
4. `production_validation_final.py` - Final validation variant
5. `production_validation_realistic.py` - Realistic scenario validation
6. `release_gates.py` - Release readiness gates
7. `release_policy.py` - Release policies
8. `pipeline.py` - Validation pipeline

#### Tools Benchmarks (`tools/`):
1. `run_fd00x_structural_engine.py` - ✅ CANONICAL: FD001/FD004 structural engine runner
2. `run_evaluation.py` - Evaluation runner
3. `run_validation.py` - Validation runner
4. `run_proof_package.py` - Proof of concept runner
5. `run_canonical_demo.py` - Canonical demo runner
6. `run_release_candidate.py` - Release candidate runner

---

### TETRAHEDRAL/TETRAHEDRON LOGIC PATHS

#### Location: `neraium_core/tetrahedral_state.py`
- **Purpose:** Tetrahedral weight computation and visualization support
- **Functions:**
  - `compute_tetrahedral_weights()` - Normalize 4-dimensional scores into tetrahedral weights
  - `weights_to_position()` - Map weights to 3D tetrahedral position
  - `compute_motion_features()` - Derive speed/curvature from trajectory
- **Status:** ✅ CANONICAL (actively integrated into StructuralEngine)
- **Used by:**
  - `neraium_core/alignment.py` (imports `compute_tetrahedral_state`)
  - `tools/plot_fd004_tetra_trajectory.py` (visualization)
  - Test files for tetrahedral validation

#### Visualization: `tools/plot_fd004_tetra_trajectory.py`
- **Purpose:** Plot tetrahedral trajectory in 3D space
- **Status:** ✅ CANONICAL (supporting tool)
- **Used for:** FD004 trajectory visualization and validation

#### Tests:
- `tests/test_alignment_tetrahedral_fallback.py` - Tetrahedral fallback test

---

### OUTPUT/RESULTS CSV FILES (Root Level)

**Generated by deprecated runners:**
- `FD004_by_unit_results.csv` - OLD
- `FD004_ims_policy_results.csv` - OLD
- `FD004_ims_policy_scored.csv` - OLD
- `FD004_ims_policy_tuned_results.csv` - OLD
- `FD004_ims_policy_tuned_scored.csv` - OLD
- `FD004_leadtime_summary.csv` - OLD
- `IMS_full_results.csv` - OLD
- `IMS_production_results_final.csv` - OLD
- `IMS_production_results_full.csv` - OLD
- `IMS_production_results_v1500.csv` - OLD
- `IMS_production_results_v2.csv` - OLD
- `IMS_quick_results.csv` - OLD
- `IMS_state_segments_final.csv` - OLD

**Benchmark/comparison CSVs:**
- `FD004_policy_benchmark.csv` - Generated by `benchmark_fd004_policies.py`
- `FD004_policy_comparison.csv` - Generated by `compare_fd004_policies.py`

**Canonical:**
- `FD004_scored.csv` - Canonical FD004 results
- `FD004_policy_benchmark.csv` - Canonical policy benchmark
- `FD004_CANONICAL_RESULT.md` - Documentation

---

### CHART GENERATION SCRIPTS

- `tools/plot_fd004_tetra_trajectory.py` - ✅ Tetrahedral trajectory plots
- `tools/plot_geometry_diagnostics.py` - Geometry diagnostics
- `tools/plot_state_graph.py` - State graph visualization
- `tools/plot_state_space.py` - State space plots
- `tools/plot_temporal_diagnostics.py` - Temporal diagnostics
- `tools/plot_signal_degradation.py` - Signal degradation plots

---

### OUTPUT DIRECTORIES

- `outputs/` - Runtime outputs from validator runs
- `debug_outputs/` - Debug visualization outputs
- `reports/` - Report artifacts
- `fd004_canonical_fast_outputs/` - Canonical fast-mode outputs
- `fd004_outputs_subset/` - Subset validation outputs

---

## PROPOSED CANONICAL STRUCTURE

```
neraium-core/
├── neraium_core/                          # CORE ENGINE
│   ├── alignment.py                       # ✅ StructuralEngine (CANONICAL)
│   ├── engine/                            # Engine wrapper layers
│   │   ├── unified.py                     # ✅ Unified engine (CANONICAL)
│   │   ├── production.py                  # ✅ Production engine (CANONICAL)
│   │   └── ... other engine modules
│   ├── tetrahedral_state.py               # ✅ Tetrahedral logic (CANONICAL)
│   └── ... other core modules
│
├── runners/                               # NEW: OFFICIAL RUNNER SCRIPTS
│   ├── benchmark_fd004.py                 # ✅ FD004 canonical runner
│   ├── benchmark_fd001.py                 # ✅ FD001 canonical runner
│   ├── benchmark_cmapss.py                # ✅ CMAPSS runner
│   ├── demo.py                            # ✅ Demo runner
│   └── __init__.py
│
├── validation/                            # VALIDATION & BENCHMARKING
│   ├── fast_validation.py
│   ├── production_validation.py
│   ├── pipeline.py
│   └── ... other validation modules
│
├── tools/                                 # DEVELOPMENT TOOLS
│   ├── run_fd00x_structural_engine.py     # ✅ FD001/FD004 tetrahedral runner
│   ├── plot_fd004_tetra_trajectory.py     # ✅ Tetrahedral visualization
│   └── ... other development tools
│
├── outputs/                               # LOCAL OUTPUT (gitignore)
│   ├── canonical_run_<timestamp>/
│   └── validation_run_<timestamp>/
│
├── archive/                               # DEPRECATED FILES (for reference)
│   ├── deprecated_runners/
│   │   ├── run_fd004_by_unit.py
│   │   ├── run_fd004_simple.py
│   │   ├── run_ims_production.py
│   │   └── ... other deprecated runners
│   ├── run_engine.py                      # OLD StructuralEngine (for reference only)
│   └── README_ARCHIVE.md                  # What was archived and why
│
└── ... other existing structure (apps/, tests/, docs/, etc.)
```

---

## CONSOLIDATION ACTIONS

### Phase 1: Archive Deprecated Code

**Move to `archive/` for future reference (NOT DELETED):**

1. Root-level engine implementation:
   - `run_engine.py` → `archive/run_engine.py`

2. Deprecated runner scripts (11 files):
   - `run_fd004_by_unit.py` → `archive/deprecated_runners/`
   - `run_fd004_simple.py` → `archive/deprecated_runners/`
   - `run_fd004_with_ims_policy.py` → `archive/deprecated_runners/`
   - `run_fd004_with_ims_policy_tuned.py` → `archive/deprecated_runners/`
   - `run_ims_production.py` → `archive/deprecated_runners/`
   - `run_ims_production_final.py` → `archive/deprecated_runners/`
   - `run_ims_production_final_combined.py` → `archive/deprecated_runners/`
   - `run_ims_production_full.py` → `archive/deprecated_runners/`
   - `run_ims_production_v1500.py` → `archive/deprecated_runners/`
   - `run_ims_production_v2.py` → `archive/deprecated_runners/`
   - `run_ims_full_and_plot.py` → `archive/deprecated_runners/`

3. Create `archive/README_ARCHIVE.md` documenting:
   - Which files were archived
   - Why they were archived
   - What canonical replacements to use
   - How to reference old results

### Phase 2: Create Canonical Runners Directory

**Create `runners/` directory with canonical entry points:**

1. `runners/__init__.py` - Package marker
2. `runners/benchmark_fd004.py` - Consolidate FD004 canonical variants
3. `runners/benchmark_fd001.py` - FD001 canonical runner
4. `runners/benchmark_cmapss.py` - CMAPSS canonical runner
5. `runners/demo.py` - Canonical demo runner

Each canonical runner should:
- Use `neraium_core.alignment::StructuralEngine` (NOT run_engine.py)
- Use standard output path: `outputs/<dataset>_<timestamp>/`
- Output results in canonical CSV format
- Have clear docstrings explaining usage

### Phase 3: Standardize Benchmark & Output Paths

**Define canonical paths:**

```
OUTPUT_DIR = Path("outputs")  # All runs go here
CANONICAL_RESULTS_DIR = OUTPUT_DIR / "canonical_benchmarks"
VALIDATION_RESULTS_DIR = OUTPUT_DIR / "validation_runs"
```

**Canonical result file naming:**
```
{DATASET}_{RUN_TYPE}_{TIMESTAMP}.csv

Examples:
- FD004_canonical_20260413T192000Z.csv
- FD001_canonical_20260413T192000Z.csv
- CMAPSS_canonical_20260413T192000Z.csv
- FD004_validation_20260413T192000Z.csv
```

**Canonical schema (all results files):**
```csv
unit,cycle,timestamp,structural_drift_score,relational_instability_score,
transition_pressure,temporal_inconsistency,tetrahedral_position_x,
tetrahedral_position_y,tetrahedral_position_z,state,alert,lead_time
```

### Phase 4: Consolidate Tetrahedral Logic

**Status:** Already canonical, no consolidation needed

- Keep `neraium_core/tetrahedral_state.py` as-is
- Ensure `tools/plot_fd004_tetra_trajectory.py` is the canonical visualization
- Document tetrahedral support in main `neraium_core/alignment.py`

### Phase 5: Clean Up Ambiguous Runners

**Action on uncertain/experimental runners:**

1. `run_live_stock_market.py`:
   - ⚠️ Unknown status - need user input
   - Options: Archive or clarify as custom/experimental

2. `run_upgraded_multinode_test.py`:
   - ⚠️ Appears to be test artifact
   - Action: Move to `tests/` or `archive/`

3. Test files at root:
   - `test_*.py` files should be in `tests/` (already mostly there)
   - Action: Move any root-level test files

---

## SUMMARY: WHAT BECOMES WHAT

### CANONICAL ✅
- **Engine:** `neraium_core/alignment.py::StructuralEngine`
- **Wrapper:** `neraium_core/engine/production.py::ProductionEngine`
- **Unified:** `neraium_core/engine/unified.py::Engine`
- **Benchmark runners:** `runners/benchmark_*.py` (new canonical location)
- **Tetrahedral logic:** `neraium_core/tetrahedral_state.py`
- **Visualization:** `tools/plot_fd004_tetra_trajectory.py`
- **Output directory:** `outputs/`
- **Output format:** `{DATASET}_{RUN_TYPE}_{TIMESTAMP}.csv`

### ARCHIVED ⏪
- **Old engine:** `archive/run_engine.py`
- **Deprecated runners:** `archive/deprecated_runners/*.py` (11 files)
- **Old IMS/policy variants:** All in archive
- **Old result CSVs:** Remain in root (can be moved to `archive/results/` if desired)

### REMOVED ❌
- None - all deprecated code is archived for reference, not deleted

---

## RISK ASSESSMENT

### Low Risk ✅
- Moving deprecated runners to archive
- Creating `runners/` directory
- Documenting archive contents
- Standardizing output paths

### Medium Risk ⚠️
- Renaming/consolidating canonical runner variants
- Changing output file naming scheme (may break existing automation)
- Moving result CSVs (depends on external references)

### Mitigation
- All deprecated code is archived, not deleted
- Can provide shims/symlinks if needed
- Document all changes in CONSOLIDATION_SUMMARY.md

---

## NEXT STEPS

1. **Review this plan** - confirm alignment with strategic intent
2. **Clarify uncertain items** - decide on `run_live_stock_market.py`, test artifacts
3. **Approve structure** - confirm `runners/` location and naming
4. **Implement** - execute the consolidation in phases
5. **Validate** - test canonical runners still work correctly
6. **Document** - create CONSOLIDATION_SUMMARY.md with final state

---

## Questions for User

1. Should we archive old result CSVs, or keep them in root?
2. Should `run_live_stock_market.py` be archived or documented as active?
3. Is the proposed `runners/` directory location acceptable?
4. Should canonical runners be named `benchmark_FD004.py` or `run_FD004_canonical.py`?
5. Any other runner variants that should be canonical vs. archived?
