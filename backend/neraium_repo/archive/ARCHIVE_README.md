# Archive Directory

This directory contains files that have been archived during repository cleanup (April 2026).

All archived files are preserved for historical reference but are NOT part of the active canonical development path.

## Directory Structure

```
archive/
├── ARCHIVE_README.md              # This file
├── README_ARCHIVE.md              # Original archive documentation
├── deprecated_runners/             # Old runner implementations (pre-consolidation)
├── tests/                          # Old test implementations
│
├── docs/                           # Historical documentation
│   ├── phases_and_consolidation/   # Past development phases (A, B, consolidation)
│   ├── verification_and_analysis/  # Validation reports and analysis
│   └── features_and_processes/     # Experimental features and process docs
│
├── old_scripts/                    # Legacy utility scripts
│   ├── lead_time_engine.py
│   ├── diagnostic_asset_groups.py
│   ├── plot_fd004_results.py
│   ├── generate_fd004_median_plot.py
│   └── INTEGRATION_GUIDE.py
│
├── old_tests/                      # Test files for deleted modules
│   ├── test_fd004_real.py
│   ├── test_fd004_synthetic.py
│   ├── test_fd004_canonical_evaluation.py
│   └── test_fd004_plotting.py
│
├── test_data/                      # CMAPSS datasets and calibration baselines
│   ├── train_FD004.txt (9.9 MB)
│   ├── baseline_coupling_instability.json
│   └── benchmark_calibration.json
│
└── results/                        # Old result outputs
```

## What Was Archived and Why

### Phases & Consolidation (7 files)
- **PHASE_A_B_COMPLETION_SUMMARY.md** - Phase A & B work completion documentation
- **PHASE_A_CONTRACT_AND_ISOLATION.md** - Phase A contract design
- **PHASE_B_UNIFY_SURFACE.md** - Phase B surface unification
- **CONSOLIDATION_*.md** - Engine consolidation work (plan & summary)
- **REFACTOR_*.md** - Code refactoring documentation

**Value:** Historical record of development methodology and architectural decisions

### Verification & Analysis (9 files)
- **CANONICAL_VALIDATION_FINAL.md** - Final validation evidence
- **CANONICAL_VERIFICATION_PRE_COMPLETION.md** - Pre-completion verification
- **PRODUCTION_READINESS_*.md** - Production readiness assessments
- **REAL_ACTIVE_PATH_ANALYSIS.md** - Path analysis from previous iterations
- **upgraded_multinode_quality_report.md** - Quality metrics from past tests

**Value:** Audit trail of validation work and evidence of system correctness

### Features & Processes (8 files)
- **REPLAY_*.md** - Replay feature documentation
- **VALIDATION_*.md** - Validation pipeline documentation
- **GREENHOUSE_UI_REDESIGN_SUMMARY.md** - UI redesign notes
- **POLISH_SUMMARY.md** - UI polish work
- **PREMIUM_DESIGN_NOTES.md** - Premium feature design

**Value:** Reference for experimental features and design evolution

### Old Scripts (5 files)
- **lead_time_engine.py** - Superseded by StructuralEngine in alignment.py
- **diagnostic_asset_groups.py** - Legacy diagnostic utility
- **plot_*.py** - Old plotting utilities (replaced by canonical runner output)
- **INTEGRATION_GUIDE.py** - Old integration guide

**Value:** Reference implementation of past approaches; recovered from git if needed

### Old Tests (4 files)
Tests for deleted FD004 variant modules. Archived because the modules they test no longer exist.

**Value:** Reference for how FD004 variants worked; used to belong in tests/

### Test Data (3 files)
CMAPSS training data and calibration baselines (11 MB total). Archived to reduce clone size.

**Note:** Data can be re-downloaded from NASA CMAPSS dataset source. Symlink at repository root for backward compatibility.

### Deprecated Runners
Pre-consolidation runner implementations (in subdirectory). Kept for reference only.

## Canonical Path (Current)

The active canonical path as of cleanup is:

```
✓ neraium_core/alignment.py              - StructuralEngine (ONLY canonical engine)
✓ runners/run_fd004_canonical.py         - Official FD004 benchmark runner
✓ runners/run_fd004_turbo.py             - Fast validation runner
✓ neraium_core/engine/                   - Unified Engine wrapper around StructuralEngine
```

## Recovering Archived Files

All files are in git history and can be recovered:

```bash
# View archived file from git
git show main:archive/docs/phases_and_consolidation/PHASE_A_CONTRACT_AND_ISOLATION.md

# Or restore to current branch
git checkout main -- archive/docs/phases_and_consolidation/PHASE_A_CONTRACT_AND_ISOLATION.md

# Or view when file was deleted
git log --oneline -- PHASE_A_CONTRACT_AND_ISOLATION.md
```

## Storage Impact

Archiving these files during the cleanup reduced root-level clutter from ~168 files to ~30 files.

```
Before cleanup:
  - 33 markdown files in root
  - 7 old runner scripts in scripts/
  - 14 dead Python files in neraium_core/

After cleanup:
  - 8 markdown files in root (essential only)
  - 0 redundant scripts
  - 0 dead Python files
  - 44 archived files (organized by type)
```

## References

See parent repository `CLEANUP_INVENTORY.md` and `CLEANUP_DELETION_PLAN.md` for:
- Full classification criteria
- Detailed reasons for each file's status
- Implementation checklist

