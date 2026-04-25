# Repository Cleanup Inventory

**Date:** 2026-04-13  
**Scope:** Aggressive dead code and duplication reduction  
**Target:** Clean root, unified engine path, single canonical benchmark

## 1. CANONICAL FILES (PRESERVE AT ALL COSTS)

These are the official, production-ready paths:

```
✓ neraium_core/alignment.py          - StructuralEngine (ONLY canonical engine)
✓ runners/run_fd004_canonical.py     - Official FD004 benchmark runner
✓ runners/run_fd004_turbo.py         - Fast validation runner for iteration
```

**Rule:** These three files are the canonical path. Everything else is either supporting these, or dead code.

---

## 2. CORE FRAMEWORK (KEEP)

### Production API Layer
- `apps/api/` - FastAPI application (production)
- `apps/` - All application infrastructure
- `docker/` - Containerization
- `Dockerfile` - Container definition

### Core Engine Support (Must Keep)
- `neraium_core/__init__.py`
- `neraium_core/service.py` - Service layer
- `neraium_core/pipeline.py` - Pipeline orchestration
- `neraium_core/calibration.py` - Engine calibration
- `neraium_core/metrics.py` - Metric calculation
- `neraium_core/windowing.py` - Data windowing
- `neraium_core/decision_layer.py` - Decision interface
- `neraium_core/explanation_layer.py` - Explanation generation
- `neraium_core/output_contract.py` - Output schema

### Feature & Analytics Support
- `neraium_core/causal*.py` - Causal analysis (6 files)
- `neraium_core/geometry.py` - Geometric analysis
- `neraium_core/forecasting.py` - Forecasting models
- `neraium_core/early_warning.py` - Early warning signals
- `neraium_core/data_quality.py` - Data validation
- `neraium_core/regime*.py` - Regime tracking

### Data Integration
- `neraium_core/data_connectors.py` - Data source adapters
- `neraium_core/stock_market_adapter.py` - Market data
- `neraium_core/ingestion_normalization.py` - Data normalization
- `neraium_core/csv_mapping.py` - CSV handling

### Testing & Validation
- `tests/` - Test suite
- `validation/` - Validation framework
- `examples/` - Working examples
- `fixtures/` - Test fixtures

### Configuration
- `config/` - Configuration directory
- `.env.example` - Environment template

### Documentation (Essential)
- `README.md` - Project overview
- `ARCHITECTURE.md` - System architecture
- `API_INTEGRATION.md` - API guide
- `DEMO.md` - Demo instructions
- `QUICK_START_PRODUCTION.md` - Production startup
- `PRODUCTION_INDEX.md` - Production docs
- `PRODUCTION_DEPLOYMENT.md` - Deployment guide
- `SHADOW_MODE_README.md` - Shadow mode docs
- `TURBO_RUNNER.md` - Turbo runner guide

### Supporting Infrastructure
- `.github/workflows/` - CI/CD pipelines
- `.gitignore` - Git ignore rules
- `Makefile` - Build automation
- `build_backend.py` - Backend build

### Research Tools (Keep)
- `tools/` - Diagnostic and evaluation tools (42 files)
- `notebooks/` - Jupyter notebooks

---

## 3. FILES TO ARCHIVE (Historical Value)

These are procedural docs about past work phases. Archive them in `/archive/docs/`:

### Phase/Consolidation Docs (33 items)
```
PHASE_A_B_COMPLETION_SUMMARY.md
PHASE_A_CONTRACT_AND_ISOLATION.md
PHASE_B_UNIFY_SURFACE.md
CONSOLIDATION_PLAN.md
CONSOLIDATION_SUMMARY.md
REFACTOR_PLAN.md
REFACTOR_SUMMARY.md
```

### Analysis/Verification Docs (10 items)
```
CANONICAL_VALIDATION_FINAL.md
CANONICAL_VERIFICATION_PRE_COMPLETION.md
REAL_ACTIVE_PATH_ANALYSIS.md
REAL_PATH_SUMMARY.md
PRODUCTION_READINESS_MEASURED.md
PRODUCTION_READINESS_SUMMARY.md
PRODUCTION_READY_FINAL_SUMMARY.md
PRODUCTION_VALIDATION_EVIDENCE_REPORT.md
upgraded_multinode_quality_report.md
```

### Feature/Process Docs (8 items)
```
REPLAY_TEST_GUIDE.md
REPLAY_REFINEMENTS.md
VALIDATION_PLAN.md
VALIDATION_PIPELINE_README.md
VALIDATION_REPORT.md
GREENHOUSE_UI_REDESIGN_SUMMARY.md
POLISH_SUMMARY.md
PREMIUM_DESIGN_NOTES.md
```

### Old Scripts (5 items)
```
lead_time_engine.py              - Legacy engine variant
INTEGRATION_GUIDE.py             - Old integration guide
diagnostic_asset_groups.py       - Old diagnostics
plot_fd004_results.py            - Old plotting script
generate_fd004_median_plot.py    - Old plotting script
```

### Test Data (3 items)
```
train_FD004.txt                  - CMAPSS training data (9.9MB)
baseline_coupling_instability.json
benchmark_calibration.json
```

---

## 4. FILES TO DELETE (Dead Code)

These are obsolete implementations, duplicates, and superseded runners:

### Old Engine Implementations (1 item)
```
❌ neraium_core/engine.py          - SUPERSEDED by alignment.py (StructuralEngine)
   Reason: Fully replaced by canonical StructuralEngine in alignment.py
```

### Old FD004 Variants (5 items)
```
❌ neraium_core/fd004_real.py               - Old FD004 real data handler
❌ neraium_core/fd004_synthetic.py          - Old FD004 synthetic handler
❌ neraium_core/fd004_canonical_evaluation.py - Old evaluation script
❌ neraium_core/fd004_plotting.py           - Old plotting (use canonical runner)
❌ neraium_core/fd004_transition.py         - Old transition analysis
   Reason: All functionality rolled into canonical runners
```

### Duplicate Scripts (7 items)
```
❌ scripts/run_full_validation.py           - Superseded by turbo runner
❌ scripts/run_cmapss_structural_batch.py   - Superseded by canonical runner
❌ scripts/download_three_vendor.py         - One-time setup script
❌ scripts/evaluate_transition_awareness.py - Old evaluation
❌ scripts/build_intelligence_monolith.py   - Old build script
❌ scripts/run_shadow_mode_example.py       - Example (see examples/)
❌ scripts/verify_ingest_batch_cors.sh      - Old test script
   Reason: All duplicated by more recent canonical paths or testing
```

### Junk
```
❌ +                                        - Empty marker file
   Reason: Artifact with no purpose
```

**Total to delete: 14 items**

---

## 5. GENERATED/RUNTIME OUTPUT (Already Ignored)

These directories are already in `.gitignore` and can be cleaned from working directory:

```
outputs/                          - Run outputs (gitignored)
reports/                          - Report artifacts (gitignored)
logs/                            - Log files (gitignored)
debug_outputs/                   - Debug artifacts
fd004_canonical_fast_outputs/    - Turbo test outputs (gitignored)
fd004_outputs_subset/            - Subset test outputs
fd00x/                          - Old FD00x outputs
artifacts/                       - Build/test artifacts
backup_claude_ui/               - UI backups
data/                          - Sample data
greenhouse_demo/               - Demo data (98MB)
validation_results_post_fix/   - Old validation runs
```

**These are safe to clean.** They regenerate on demand.

---

## 6. EDGE CASES TO VERIFY

### Python Files in neraium_core (66 total)

Most are experimental/supporting. Need human judgment on:
- Subsystems (auxiliary, experimental_analytics, operator, sii, etc.)
- Math engines (symbolic, verification, probabilistic)
- System intelligence engines (multiple)
- Diagnostics files

**Strategy:** Keep all unless explicitly shown to be unused. Move to archive if stale but potentially valuable.

### Root-Level Clutter (Various Files)

```
app.py                          - ?
apprunner.yaml                  - AWS AppRunner config (keep if deployed)
build_backend.py               - ?
diagnostic_asset_groups.py     - ? (move to archive)
```

**Strategy:** Review for production necessity. If not used in active deployment, archive.

---

## 7. ROOT-LEVEL STRUCTURE (AFTER CLEANUP)

Target clean root:

```
/
├── .github/                  # CI/CD workflows
├── .env.example             # Example environment
├── .gitignore               # Git ignore
├── .dockerignore            # Docker ignore
├── README.md                # Project documentation
├── ARCHITECTURE.md          # Architecture docs
├── QUICK_START_PRODUCTION.md # Production guide
├── API_INTEGRATION.md       # API docs
├── PRODUCTION_INDEX.md      # Production docs
├── TURBO_RUNNER.md          # Turbo guide
├── Dockerfile               # Container definition
├── Makefile                 # Build automation
├── apps/                    # FastAPI application
├── docker/                  # Docker files
├── config/                  # Configuration
├── neraium_core/            # Core framework (canonical)
│   ├── alignment.py         # StructuralEngine
│   └── [supporting files]
├── runners/                 # Official runners
│   ├── run_fd004_canonical.py
│   └── run_fd004_turbo.py
├── examples/                # Working examples
├── tests/                   # Test suite
├── validation/              # Validation framework
├── fixtures/                # Test fixtures
├── tools/                   # Diagnostic/eval tools
├── notebooks/               # Jupyter notebooks
├── archive/                 # Archived docs & old code
│   ├── README_ARCHIVE.md
│   ├── docs/               # Historical docs
│   └── deprecated_runners/ # Already exists
└── .claude/                 # Claude Code config
```

**Eliminated:**
- Root-level scripts/ (merge to tools/ or archive)
- Root-level *.py files (merge or delete)
- Root-level procedural docs (move to archive/docs/)
- Root-level output directories
- Root-level test data files

---

## 8. CLEANUP EXECUTION PLAN

### Phase 1: Archive & Move
1. Create `/archive/docs/` directory
2. Move 33 markdown doc files to `archive/docs/`
3. Move 5 old scripts to `archive/old_scripts/`
4. Move test data to `archive/test_data/`
5. Update any imports if needed

### Phase 2: Delete Dead Code
1. Delete 7 old script files from `scripts/`
2. Delete 5 old FD004 variant files from `neraium_core/`
3. Delete old engine.py
4. Delete empty marker file `+`
5. Verify no imports are broken

### Phase 3: Tighten .gitignore
- Add patterns for output directories
- Verify regime_library*.json files are ignored
- Add fd00x/ to gitignore

### Phase 4: Verify & Test
1. Run tests: `python -m pytest tests/`
2. Run canonical: `python -m runners.run_fd004_canonical --help`
3. Run turbo: `python -m runners.run_fd004_turbo --help`
4. Verify imports work
5. Commit changes

---

## 9. SAFETY CHECKLIST

Before deletion, verify:

- [ ] StructuralEngine in alignment.py is the canonical engine
- [ ] No imports from `engine.py` to `alignment.py`
- [ ] No imports from deleted FD004 variants in canonical runners
- [ ] No imports from deleted script files
- [ ] Tests still pass
- [ ] Canonical and turbo runners still work
- [ ] No broken relative imports
- [ ] Archive directory structure is clear

---

## 10. EXPECTED OUTCOME

```
Repository metrics AFTER cleanup:

Root-level files:          ~15 (from ~168)  ✓ -90%
Markdown docs in root:     ~8  (from ~33)   ✓ -76%
Dead Python files:         ~0  (from ~14)
Duplicate runners:         ~0  (from ~7)
Output directories:        cleaned
Total files (source only): ~2000 (from ~5671) ✓ -65%

Canonical path clarity:    HIGH
  - One engine (StructuralEngine)
  - One benchmark runner (canonical)
  - One validation runner (turbo)
  - Clear supporting structure

Maintainability:          IMPROVED
  - No duplicate implementations
  - Clear canonical vs. archived distinction
  - Smaller surface area to reason about
```

---

## 11. ROLLBACK PLAN

All deleted files are either:
1. Already in git history (can be recovered)
2. Backed up in archive/deprecated_runners/
3. Documented in this inventory

If issues arise:
```bash
git log --oneline | head  # Find last good state
git show <commit>:path/to/file  # Recover from git
```

---

## Questions for Review

1. **apprunner.yaml** - Is this used for AWS deployment? Keep or archive?
2. **greenhouse_demo/** (98MB) - Is this still needed? Currently output, should archive or delete?
3. **ui/** directory - Should this be in apps/ instead?
4. **neraium_core/experimental_analytics/** - Is this active or experimental-only?
5. **neraium_core/system_intelligence/** - Is this actively used or exploration?

