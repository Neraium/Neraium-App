# Archive: Deprecated and Experimental Code

This directory contains deprecated code that has been archived during the **Structural Engine Consolidation** (April 2026).

**IMPORTANT:** Nothing in this archive is part of the canonical codebase. All production/benchmark work should use the canonical paths in the root `runners/` directory.

---

## What Was Archived and Why

### Engines (Consolidation)

**Old Implementation:**
- `run_engine.py` - Original StructuralEngine implementation (1,376 lines)
  - **Status:** DEPRECATED - superseded by `neraium_core/alignment.py::StructuralEngine`
  - **Reason:** Two parallel engine implementations created confusion about which was authoritative
  - **Canonical Replacement:** Use `neraium_core.alignment::StructuralEngine` in all new code

**Why Only One Engine Now:**
- `neraium_core/alignment.py::StructuralEngine` is the ONLY canonical engine implementation
- All 11 deprecated runners that imported from `run_engine.py` have been archived
- Tetrahedral logic is fully integrated into the canonical engine
- No parallel or "shadow" engine paths remain

---

### Result CSVs (Cleanup)

**Moved to `archive/results/`:**
- `FD004_by_unit_results.csv`
- `FD004_ims_policy_*.csv` (multiple variants)
- `FD004_leadtime_summary.csv`
- `FD004_scored.csv` (canonical benchmark result)
- `FD004_policy_*.csv` (policy variants)
- `IMS_*.csv` (all IMS variants)
- `fd004_*.csv` (all FD004 variants)

**Reason:** Keep root directory clean. All new results go to `outputs/canonical_benchmarks/`

**New Output Format:**
```
outputs/canonical_benchmarks/FD004_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_scored_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_summary_<TIMESTAMP>.json
```

---

### Deprecated Runners (15 files)

**Moved to `archive/deprecated_runners/`:**

#### Old IMS Variants (Using `run_engine.py`)
- `run_ims_production.py` - OLD IMS runner
- `run_ims_production_final.py` - OLD IMS final variant
- `run_ims_production_final_combined.py` - OLD IMS combined
- `run_ims_production_full.py` - OLD IMS full
- `run_ims_production_v1500.py` - OLD IMS v1500 variant
- `run_ims_production_v2.py` - OLD IMS v2 variant
- `run_ims_full_and_plot.py` - OLD IMS with plots
- `run_ims_quick.py` - OLD IMS quick run

#### Old FD004 Variants (Using `run_engine.py` or alternate implementations)
- `run_fd004_by_unit.py` - OLD per-unit runner
- `run_fd004_simple.py` - OLD simplified runner
- `run_fd004_canonical.py` - OLD canonical runner (replaced by `runners/run_fd004_canonical.py`)
- `run_fd004_canonical_fast.py` - OLD fast variant
- `run_fd004_fast.py` - OLD fast mode
- `run_fd004.py` - OLD standard runner
- `run_fd004_with_ims_policy.py` - OLD IMS policy variant
- `run_fd004_with_ims_policy_tuned.py` - OLD tuned policy variant

#### Old CMAPSS Variants
- `run_cmapss_suite.py` - OLD full suite
- `run_cmapss_suite_batched.py` - OLD batched version
- `run_cmapss_one_visible.py` - OLD single unit variant

#### Benchmarking Scripts
- `benchmark_fd004_policies.py` - OLD policy benchmark (archive/deprecated_runners/)
- `compare_fd004_policies.py` - OLD policy comparison script

**Reason:** These runners either:
1. Used the OLD `run_engine.py` implementation (deprecated)
2. Were variants of the FD004/IMS pipeline that are now consolidated into one canonical runner
3. Used IMS-specific or legacy policy paths that are not part of canonical flow

**Canonical Replacement:**
```bash
python runners/run_fd004_canonical.py  # NEW: Only canonical FD004/FD001 runner
```

---

### Other Deprecated/Experimental Code

**Moved to `archive/`:**
- `run_live_stock_market.py` - Custom use case (not part of canonical engine path)

**Moved to `archive/tests/`:**
- `run_upgraded_multinode_test.py` - Test artifact
- `test_falsification_layer.py` - Test file
- `test_predeploy.py` - Pre-deploy test
- `test_fixes.py` - Fix validation test
- `experiment.py` - Experimental code

---

## How to Reference Archived Code

If you need to understand old implementations:

```bash
# View old engine implementation
cat archive/run_engine.py

# View old FD004 runner
cat archive/deprecated_runners/run_fd004_canonical.py

# View old IMS results
ls archive/results/IMS_*.csv
```

---

## Canonical Paths (Use These)

### Engine
```python
from neraium_core.alignment import StructuralEngine
```

### Benchmark Runner
```bash
# Run FD004/FD001 canonical benchmark
python runners/run_fd004_canonical.py
```

### Output Location
```
outputs/canonical_benchmarks/FD004_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_scored_<TIMESTAMP>.csv
outputs/canonical_benchmarks/FD004_summary_<TIMESTAMP>.json
```

### Other Canonical Runners (Not Benchmarks)
```bash
python run_demo.py          # Demo (FastAPI + Next.js)
python run_live.py          # Production live runner
python run_pilot.py         # Pilot program
python run_ui.py            # UI runner
```

---

## Key Changes Made

1. **One Engine:** `neraium_core/alignment.py::StructuralEngine` is now THE only engine
2. **One FD004 Benchmark Runner:** `runners/run_fd004_canonical.py` is the only benchmark runner
3. **No Parallel Paths:** Tetrahedral logic is integrated into main engine, not separate
4. **Clean Root Directory:** No old result CSVs, deprecated runners, or test artifacts at root level
5. **Standard Output Format:** All results go to `outputs/canonical_benchmarks/` with timestamps

---

## What To Do If You Need Old Code

### If you need to recover old results:
```bash
# Check archive/results/ for historical CSVs
ls archive/results/
```

### If you need to understand old implementation:
```bash
# Read old engine
cat archive/run_engine.py

# Read any old runner variant
cat archive/deprecated_runners/run_fd004_by_unit.py
```

### If you want to reference old IMS work:
```bash
# All IMS runners are archived
# Use canonical StructuralEngine instead
from neraium_core.alignment import StructuralEngine
```

---

## Questions

**Q: Can I use the old `run_engine.py`?**  
A: No. It's archived for reference only. Use `neraium_core.alignment::StructuralEngine` instead.

**Q: Where do I run benchmarks now?**  
A: Use `python runners/run_fd004_canonical.py`. This is the only canonical benchmark runner.

**Q: What happened to IMS-specific policies?**  
A: All IMS-specific and policy variant runners have been archived. They are not part of the canonical engine path.

**Q: Why was tetrahedral logic consolidated?**  
A: Tetrahedral state computation is now integrated directly into `neraium_core/tetrahedral_state.py` and used by `StructuralEngine`. There is no separate "tetrahedral engine" path.

**Q: Can I still access old results?**  
A: Yes. See `archive/results/` for all historical CSVs. New results are in `outputs/canonical_benchmarks/`.

---

**Last Updated:** 2026-04-13  
**Consolidation Version:** 1.0  
**Status:** Complete
