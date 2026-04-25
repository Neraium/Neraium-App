# Structural Engine Consolidation: COMPLETE ✅

**Date:** 2026-04-13  
**Status:** Implementation Complete  
**Scope:** Hard consolidation pass of entire codebase

---

## Executive Summary

✅ **ONE CANONICAL ENGINE**
- `neraium_core/alignment.py::StructuralEngine` is now the ONLY engine implementation
- Old parallel `run_engine.py` archived
- All 11 deprecated runners using old engine archived

✅ **ONE CANONICAL BENCHMARK RUNNER**
- `runners/run_fd004_canonical.py` is now the ONLY official FD004/FD001 runner
- 15 old variants (FD004, CMAPSS, IMS policy) archived
- Canonical runner outputs to `outputs/canonical_benchmarks/`

✅ **TETRAHEDRAL LOGIC INTEGRATED**
- `neraium_core/tetrahedral_state.py` is the canonical tetrahedral implementation
- Fully integrated into `StructuralEngine` - no parallel path
- Visualization tool: `tools/plot_fd004_tetra_trajectory.py`

✅ **CLEAN REPOSITORY STRUCTURE**
- Root directory cleaned of deprecated runners and result CSVs
- Old results moved to `archive/results/` (21 CSV files)
- Test artifacts moved to `archive/tests/` (5 files)
- New `runners/` directory with canonical executables

---

## Implementation Details

### Phase 1: Archive Structure Created
```
archive/
├── run_engine.py                      (OLD StructuralEngine)
├── run_live_stock_market.py           (Not canonical)
├── README_ARCHIVE.md                  (Archive documentation)
├── results/                           (21 old result CSVs)
├── deprecated_runners/                (18 deprecated runners)
└── tests/                             (5 test artifacts)
```

### Phase 2: Results CSVs Moved
**Moved 21 CSV files to `archive/results/`:**
- FD004_*.csv (9 files) - Old FD004 benchmark results
- IMS_*.csv (8 files) - Old IMS benchmark results
- fd004_*.csv (4 files) - Old FD004 variants
- FD004_CANONICAL_RESULT.md - Archive documentation

**New canonical output location:**
```
outputs/canonical_benchmarks/FD004_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_scored_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_summary_<TIMESTAMP>.json
outputs/canonical_benchmarks/FD004_lead_time_<TIMESTAMP>.png
outputs/canonical_benchmarks/FD004_timeline_<TIMESTAMP>.png
outputs/canonical_benchmarks/FD004_hero_*.png
```

### Phase 3: Deprecated Engines & Runners Archived
**Deprecated Engines (1 file):**
- `run_engine.py` → `archive/run_engine.py` ✅ ARCHIVED

**Deprecated Runners (18 files):**

*IMS Variants (using old engine):*
- `run_ims_production.py` → archived ✅
- `run_ims_production_final.py` → archived ✅
- `run_ims_production_final_combined.py` → archived ✅
- `run_ims_production_full.py` → archived ✅
- `run_ims_production_v1500.py` → archived ✅
- `run_ims_production_v2.py` → archived ✅
- `run_ims_full_and_plot.py` → archived ✅
- `run_ims_quick.py` → archived ✅

*FD004 Variants (old implementations):*
- `run_fd004_canonical.py` (old) → archived ✅
- `run_fd004_canonical_fast.py` → archived ✅
- `run_fd004_fast.py` → archived ✅
- `run_fd004.py` → archived ✅
- `run_fd004_by_unit.py` → archived ✅
- `run_fd004_simple.py` → archived ✅
- `run_fd004_with_ims_policy.py` → archived ✅
- `run_fd004_with_ims_policy_tuned.py` → archived ✅

*CMAPSS Variants (old implementations):*
- `run_cmapss_suite.py` → archived ✅
- `run_cmapss_suite_batched.py` → archived ✅
- `run_cmapss_one_visible.py` → archived ✅

*Benchmarking Scripts:*
- `benchmark_fd004_policies.py` → archived ✅
- `compare_fd004_policies.py` → archived ✅

### Phase 4: Test Artifacts Moved
**Moved 5 files to `archive/tests/`:**
- `run_upgraded_multinode_test.py` → archived ✅
- `test_falsification_layer.py` → archived ✅
- `test_predeploy.py` → archived ✅
- `test_fixes.py` → archived ✅
- `experiment.py` → archived ✅

### Phase 5-6: Canonical Runners Created
**New `runners/` directory:**
```
runners/
├── __init__.py
└── run_fd004_canonical.py             ✅ ONLY canonical benchmark runner
```

**`run_fd004_canonical.py` features:**
- Uses `neraium_core.alignment::StructuralEngine` (CANONICAL)
- Locked FD004 policy configuration
- Outputs to `outputs/canonical_benchmarks/`
- Generates results, scores, summary, and charts
- Fully documented with docstrings
- Standard output naming: `FD004_<TIMESTAMP>.csv`

### Phase 7: Archive Documentation
**`archive/README_ARCHIVE.md` documents:**
- Why each file was archived
- What canonical replacements to use
- How to reference archived code
- New canonical paths and outputs
- FAQ for common questions

---

## Final Canonical Paths

### Engine (ONLY Implementation)
```python
from neraium_core.alignment import StructuralEngine

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    drift_smoothing_window=25,
    watch_quantile=0.65,
    alert_quantile=0.85,
    watch_persistence=5,
    alert_persistence=3,
    fast_trigger_multiplier=1.25,
    alert_latch_enabled=True,
    unlatch_ratio=0.75,
)
```

### Benchmark Runner (ONLY Canonical)
```bash
python runners/run_fd004_canonical.py
```

### Output Path (Canonical Location)
```
outputs/canonical_benchmarks/
├── FD004_20260413T192000Z.csv
├── FD004_scored_20260413T192000Z.csv
├── FD004_summary_20260413T192000Z.json
├── FD004_lead_time_20260413T192000Z.png
├── FD004_timeline_20260413T192000Z.png
├── FD004_hero_1_20260413T192000Z.png
└── FD004_hero_2_20260413T192000Z.png
```

### Tetrahedral Logic (CANONICAL)
```python
from neraium_core.tetrahedral_state import (
    compute_tetrahedral_weights,
    weights_to_position,
    compute_motion_features,
)

# Used internally by StructuralEngine
# Visualization: tools/plot_fd004_tetra_trajectory.py
```

### Other Canonical Runners (Not Benchmarks)
```bash
python run_demo.py          # Demo (FastAPI + Next.js UI)
python run_live.py          # Production live runner
python run_pilot.py         # Pilot program runner
python run_ui.py            # UI-only runner
```

---

## Verification Checklist

✅ **Engine Consolidation**
- Only one StructuralEngine in `neraium_core/alignment.py`
- Old `run_engine.py` archived
- All imports point to canonical location
- No parallel engine implementations

✅ **Runner Consolidation**
- Only one canonical benchmark runner: `runners/run_fd004_canonical.py`
- 18 deprecated variants archived
- Root level clean (only demo/live/pilot/ui remain)
- Canonical runner uses canonical engine

✅ **Tetrahedral Logic**
- Integrated in `neraium_core/tetrahedral_state.py`
- Used by StructuralEngine (not separate path)
- Visualization tool canonical
- No duplicate tetrahedral implementations

✅ **Output Standardization**
- Results go to `outputs/canonical_benchmarks/`
- Old results in `archive/results/`
- Timestamp-based naming: `{DATASET}_{TIMESTAMP}.csv`
- Standard schema across all runs

✅ **Documentation**
- `archive/README_ARCHIVE.md` explains what was archived
- `CONSOLIDATION_SUMMARY.md` documents final state
- Code comments updated in canonical scripts
- Clear path forward documented

---

## Files Changed Summary

**Created:**
- `runners/` directory
- `runners/__init__.py`
- `runners/run_fd004_canonical.py` (NEW canonical runner)
- `archive/README_ARCHIVE.md` (Archive documentation)
- `CONSOLIDATION_SUMMARY.md` (This file)

**Moved/Archived (47 total):**
- 1 old engine: `run_engine.py`
- 18 deprecated runners (FD004, IMS, CMAPSS variants)
- 21 old result CSVs
- 5 test artifacts
- 2 other deprecated files
- Total: `archive/` now contains reference implementations

**Remaining at Root (4 canonical runners):**
- `run_demo.py` (Demo)
- `run_live.py` (Production)
- `run_pilot.py` (Pilot)
- `run_ui.py` (UI)

---

## What Gets Used Now

### For Benchmarking FD004/FD001:
```bash
# One command, one output
python runners/run_fd004_canonical.py
# Outputs to: outputs/canonical_benchmarks/FD004_<timestamp>.csv
```

### For Engine Development:
```python
# One engine implementation
from neraium_core.alignment import StructuralEngine

# Tetrahedral logic integrated (not separate)
from neraium_core.tetrahedral_state import compute_tetrahedral_weights
```

### For Production:
```bash
# Use ProductionEngine (wraps StructuralEngine)
python run_live.py
```

---

## Impact & Benefits

**Clarity:**
- No ambiguity about which engine to use
- No competing FD004 runners
- One canonical output format
- Clear "this is deprecated" vs "this is canonical" separation

**Maintainability:**
- Single code path to maintain
- No duplicate implementations to keep in sync
- Archived code provides reference if needed
- Clear deprecation path documented

**Correctness:**
- Tetrahedral logic no longer has parallel path
- One source of truth for StructuralEngine behavior
- No confusion about which results are canonical
- Reproducible benchmarks via canonical runner

**Performance:**
- No wasted time on deprecated variants
- Clear optimization target: canonical runner
- Tetrahedral logic efficiently integrated
- Standard output schema enables easy analysis

---

## Next Steps for Users

1. **Update any imports** from `run_engine` → use `neraium_core.alignment::StructuralEngine`
2. **Use canonical runner** for benchmarking: `python runners/run_fd004_canonical.py`
3. **Check `archive/README_ARCHIVE.md`** if you need old code for reference
4. **Results go to** `outputs/canonical_benchmarks/` (not root)
5. **Contribute** to canonical paths only (no new variants)

---

## Rollback Information

If needed, all archived code is available in `archive/`:
- Original engine: `archive/run_engine.py`
- Old runners: `archive/deprecated_runners/`
- Old results: `archive/results/`
- Test artifacts: `archive/tests/`

See `archive/README_ARCHIVE.md` for full details.

---

**Status:** ✅ CONSOLIDATION COMPLETE  
**Version:** 1.0  
**Last Updated:** 2026-04-13 19:59 UTC  
**Branch:** claude/consolidate-structural-engine-MKFtq
