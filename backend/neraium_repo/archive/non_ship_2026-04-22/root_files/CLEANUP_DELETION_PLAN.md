# Repository Cleanup: Proposed Deletions & Archives

## DELETION LIST

These files have no references in the canonical path and should be **permanently deleted**:

### Category 1: Superseded Engine Implementation

```
DELETE: neraium_core/engine.py

Reason:
  - Fully replaced by StructuralEngine in neraium_core/alignment.py
  - Old DetectorConfig/DetectionResult approach superseded
  - Engine registry (engine_registry.py) imports from alignment.py
  - References in codebase all point to alignment.StructuralEngine
  - Deletion will clean up confusion between two engine impls

Size: ~1.2 KB
Risk: LOW - canonical path uses alignment.py only
```

### Category 2: Old FD004 Experimental Variants

```
DELETE: neraium_core/fd004_real.py
DELETE: neraium_core/fd004_synthetic.py
DELETE: neraium_core/fd004_canonical_evaluation.py
DELETE: neraium_core/fd004_plotting.py
DELETE: neraium_core/fd004_transition.py

Reason:
  - All FD004 functionality consolidated into canonical runner
  - run_fd004_canonical.py handles real data via StructuralEngine
  - run_fd004_turbo.py handles validation/turbo runs
  - These old modules are NOT imported by canonical runners
  - Old evaluation/plotting code duplicates canonical runner output
  - Transition analysis superseded by tetrahedral_state.py integration

Size: ~45 KB total
Risk: LOW - canonical runners don't import these
Verification:
  grep -r "from neraium_core.fd004_real" .
  grep -r "from neraium_core.fd004_synthetic" .
  grep -r "from neraium_core.fd004_canonical_evaluation" .
  grep -r "from neraium_core.fd004_plotting" .
  grep -r "from neraium_core.fd004_transition" .
  # All should return empty in active code
```

### Category 3: Superseded/Deprecated Scripts

```
DELETE: scripts/run_full_validation.py
Reason: Superseded by runners/run_fd004_turbo.py (faster, cleaner)
Size: ~2.5 KB

DELETE: scripts/run_cmapss_structural_batch.py
Reason: Superseded by runners/run_fd004_canonical.py (better interface)
Size: ~3.2 KB

DELETE: scripts/download_three_vendor.py
Reason: One-time setup script, not part of canonical path
Size: ~1.1 KB

DELETE: scripts/evaluate_transition_awareness.py
Reason: Old evaluation script, functionality in tools/
Size: ~2.8 KB

DELETE: scripts/build_intelligence_monolith.py
Reason: Old build process, superseded by modular approach
Size: ~1.4 KB

DELETE: scripts/run_shadow_mode_example.py
Reason: Example code, should live in examples/ not scripts/
Size: ~0.9 KB

DELETE: scripts/verify_ingest_batch_cors.sh
Reason: Old shell test, not part of canonical testing
Size: ~0.3 KB

Verification:
  grep -r "scripts.run_full_validation" .
  grep -r "scripts.run_cmapss_structural_batch" .
  # Check for any imports from these files
```

### Category 4: Junk/Artifacts

```
DELETE: +

Reason: Empty marker file with no purpose
Size: 0 bytes
Risk: NONE
```

**Total Deletions: 14 files, ~58 KB**

---

## ARCHIVE LIST

Files with historical value should be moved to `archive/`:

### Category 1: Procedural/Phase Documentation (19 items)

**Archive to: archive/docs/phases_and_consolidation/**

```
PHASE_A_B_COMPLETION_SUMMARY.md
PHASE_A_CONTRACT_AND_ISOLATION.md
PHASE_B_UNIFY_SURFACE.md
CONSOLIDATION_PLAN.md
CONSOLIDATION_SUMMARY.md
REFACTOR_PLAN.md
REFACTOR_SUMMARY.md
```

Reason:
  - Document past development phases
  - Have historical value for understanding evolution
  - Not needed for current development
  - Can be referenced if we need to understand past decisions

### Category 2: Verification/Analysis Documentation (9 items)

**Archive to: archive/docs/verification_and_analysis/**

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

Reason:
  - Evidence of past validation work
  - No longer actively used
  - May have regulatory/audit value
  - Can reference if validation history needed

### Category 3: Feature/Process Documentation (8 items)

**Archive to: archive/docs/features_and_processes/**

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

Reason:
  - Describe experimental/exploratory features
  - Legacy design documentation
  - Useful for reference but not active
  - Keeps root clean while preserving knowledge

### Category 4: Old Scripts & Tools (5 items)

**Archive to: archive/old_scripts/**

```
lead_time_engine.py
diagnostic_asset_groups.py
plot_fd004_results.py
generate_fd004_median_plot.py
INTEGRATION_GUIDE.py
```

Reason:
  - Legacy implementations
  - Replaced by newer approaches
  - Useful reference for understanding evolution
  - Not imported by canonical path

Size: ~20 KB

### Category 5: Test Data Files (3 items)

**Archive to: archive/test_data/**

```
train_FD004.txt (9.9 MB)
baseline_coupling_instability.json
benchmark_calibration.json
```

Reason:
  - CMAPSS training data (public)
  - Calibration baselines
  - Large file improves clone speed when archived
  - Can be re-downloaded from source
  - Still needed for canonical/turbo runners

Action:
  - Move to archive/ but create symlink from root: `ln -s archive/test_data/train_FD004.txt ./`
  - Update runner scripts to check both root and archive/ locations
  - Add note in README about data location

**Total Archives: 44 files, ~12 MB**

---

## FILES THAT SHOULD MOVE (Not Delete/Archive)

These files should move to more appropriate locations:

### 1. Root-level Python files

**app.py** → `apps/standalone.py` or keep at root if it's the entry point  
**build_backend.py** → `build/backend.py` or keep at root if needed by build system

**Action:** Review and clarify purpose. If entry point, document. If utility, move to appropriate module.

### 2. Diagnostic Python files

**diagnostic_asset_groups.py** → `archive/old_scripts/`  
**Reason:** Legacy diagnostic, no active usage

**Action:** ARCHIVE (already listed above)

---

## FILES NEEDING CLARIFICATION

These files should be reviewed for business necessity:

### Priority 1: Potentially Remove

```
greenhouse_demo/          (98 MB)
  - Large demo project
  - May be proof-of-concept
  - Could move to archive or delete if not needed
  - Action: Clarify if still referenced

ui/                       (200+ KB)
  - UI components/themes
  - Should probably be in apps/ or separate repo
  - Action: Clarify if still active

apprunner.yaml
  - AWS AppRunner configuration
  - Action: Keep if AWS deployment active, else archive
```

### Priority 2: May Be Useful

```
notebooks/                (small)
  - Jupyter notebooks
  - Keep if active research
  
tools/                    (167 KB)
  - Diagnostic and evaluation tools
  - Keep - valuable for development

examples/                 (300+ KB)
  - Example projects
  - Keep - used for demos and testing
```

---

## PROPOSED EXECUTION ORDER

### Phase 1: Prepare Archive Structure
```bash
# Create archive subdirectories
mkdir -p archive/docs/{phases_and_consolidation,verification_and_analysis,features_and_processes}
mkdir -p archive/old_scripts
mkdir -p archive/test_data
```

### Phase 2: Move Files to Archive
```bash
# Phase docs
mv PHASE_A_*.md archive/docs/phases_and_consolidation/
mv CONSOLIDATION_*.md archive/docs/phases_and_consolidation/
mv REFACTOR_*.md archive/docs/phases_and_consolidation/

# Verification docs
mv CANONICAL_*.md archive/docs/verification_and_analysis/
mv PRODUCTION_READINESS_*.md archive/docs/verification_and_analysis/
mv REAL_*.md archive/docs/verification_and_analysis/
mv upgraded_multinode_quality_report.md archive/docs/verification_and_analysis/

# Feature docs
mv REPLAY_*.md archive/docs/features_and_processes/
mv VALIDATION_*.md archive/docs/features_and_processes/
mv GREENHOUSE_*.md archive/docs/features_and_processes/
mv POLISH_SUMMARY.md archive/docs/features_and_processes/
mv PREMIUM_DESIGN_NOTES.md archive/docs/features_and_processes/

# Old scripts
mv lead_time_engine.py archive/old_scripts/
mv diagnostic_asset_groups.py archive/old_scripts/
mv plot_fd004_results.py archive/old_scripts/
mv generate_fd004_median_plot.py archive/old_scripts/
mv INTEGRATION_GUIDE.py archive/old_scripts/

# Test data
mv train_FD004.txt archive/test_data/
mv baseline_coupling_instability.json archive/test_data/
mv benchmark_calibration.json archive/test_data/

# Create symlink for backward compatibility
ln -s archive/test_data/train_FD004.txt ./train_FD004.txt
```

### Phase 3: Update Imports
```bash
# Find any imports of archived files
grep -r "from lead_time_engine" --include="*.py"
grep -r "from diagnostic_asset_groups" --include="*.py"
# Update any that exist
```

### Phase 4: Delete Dead Code
```bash
# Old engine
rm neraium_core/engine.py

# Old FD004 variants
rm neraium_core/fd004_real.py
rm neraium_core/fd004_synthetic.py
rm neraium_core/fd004_canonical_evaluation.py
rm neraium_core/fd004_plotting.py
rm neraium_core/fd004_transition.py

# Superseded scripts
rm scripts/run_full_validation.py
rm scripts/run_cmapss_structural_batch.py
rm scripts/download_three_vendor.py
rm scripts/evaluate_transition_awareness.py
rm scripts/build_intelligence_monolith.py
rm scripts/run_shadow_mode_example.py
rm scripts/verify_ingest_batch_cors.sh

# Junk
rm +
```

### Phase 5: Verify
```bash
# Run tests
python -m pytest tests/ -v

# Try canonical runner
python -m runners.run_fd004_canonical --help

# Try turbo runner  
python -m runners.run_fd004_turbo --help

# Check for import errors
python -c "from neraium_core.alignment import StructuralEngine; print('OK')"
```

### Phase 6: Update .gitignore

Add/verify these patterns:
```
# Output directories (already present, verify)
outputs/
reports/
logs/

# Add if missing
debug_outputs/
fd00x/
backup_claude_ui/
greenhouse_demo/
validation_results_post_fix/
artifacts/
```

### Phase 7: Create Archive README

Create `archive/README.md`:
```markdown
# Archive Directory

This directory contains:

1. **docs/** - Historical documentation about past development phases, verification, and features
2. **deprecated_runners/** - Old runner scripts (before canonical consolidation)
3. **old_scripts/** - Legacy helper scripts
4. **test_data/** - CMAPSS dataset and calibration baselines
5. **tests/** - Old test implementations

All files here are preserved for reference but not part of the active canonical path.

See CLEANUP_INVENTORY.md in the repository root for detailed classification.
```

### Phase 8: Commit Changes

```bash
git add -A
git commit -m "Clean up dead code and consolidate documentation

- Move 44 historical docs to archive/ (phases, verification, features, old scripts)
- Delete 14 dead/superseded files (old engine variant, FD004 duplicates, deprecated scripts)
- Keep canonical path: StructuralEngine + run_fd004_canonical + run_fd004_turbo
- Archive test data with backward-compatible symlink
- Update .gitignore for output directories
- Reduce root clutter: ~168 → ~30 files
- Reduce source files: ~5671 → ~2600 active Python files

Deliverables:
- CLEANUP_INVENTORY.md: Full classification and strategy
- CLEANUP_DELETION_PLAN.md: This detailed plan with reasons
- archive/ structure: Organized historical preservation
- Cleaner root directory for better DX

No breaking changes. All canonical runners and API still functional.
See CLEANUP_INVENTORY.md for full details.

https://claude.ai/code/session_01B8ngG9XjWaik9RqTgvisKA
```

---

## RISK ASSESSMENT

| Risk | Probability | Severity | Mitigation |
|------|-------------|----------|-----------|
| Import breakage from deleted files | LOW | MEDIUM | grep -r before deletion, run tests |
| Needed file accidentally deleted | LOW | HIGH | All files in git history, archive backups |
| Data loss (test data) | LOW | LOW | Create symlink, archive has copy |
| Workflow disruption | LOW | MEDIUM | Test canonical/turbo after changes |
| CI/CD breakage | LOW | MEDIUM | Run full test suite |

**Overall Risk: LOW**

---

## VERIFICATION CHECKLIST

Before committing:

- [ ] All files to archive exist and are moved
- [ ] All files to delete are identified in git (can be recovered)
- [ ] No imports broken (grep -r for old module names)
- [ ] Canonical runner works: `python -m runners.run_fd004_canonical --help`
- [ ] Turbo runner works: `python -m runners.run_fd004_turbo --help`
- [ ] Tests pass: `python -m pytest tests/ -x`
- [ ] Archive directory structure is clear and documented
- [ ] README.md in archive/
- [ ] .gitignore updated
- [ ] Root directory is clean (~30 files instead of ~168)
- [ ] Commit message is clear and references this plan

