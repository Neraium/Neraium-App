# FD004 Turbo Runner

## Overview

`runners/run_fd004_turbo.py` is a **fast validation runner** for quick iteration during development.

**⚠️ Not the official benchmark.** Results are **directional only**. Use `run_fd004_canonical.py` for final benchmark results.

## Key Differences from Canonical Runner

| Aspect | Canonical | Turbo |
|--------|-----------|-------|
| **Purpose** | Official benchmark | Fast validation/smoke test |
| **Default units** | All units | 5 units |
| **Cycle limit** | None | Optional per-unit limit |
| **Runtime** | ~26 hours | Minutes (5 units) |
| **Output dir** | `outputs/canonical_benchmarks/` | `outputs/turbo_benchmarks/` |
| **File naming** | `FD004_*.csv` | `FD004_turbo_*.csv` |
| **Engine** | StructuralEngine | **Same StructuralEngine** |
| **Schema** | — | **Identical to canonical** |
| **Charts** | Always | Optional (--no-charts) |

## Schema Compatibility

Both runners output **identical columns**:
- `unit`, `cycle`, `policy_state`, `policy_watch`, `policy_alert`
- `state`, `structural_drift_score`, `drift_smooth`
- `watch_threshold`, `alert_threshold`

Scored CSV columns are also identical, enabling direct row-by-row comparison when using the same data subset.

## Example Commands

### 5-unit smoke test (default, fastest)
```bash
python -m runners.run_fd004_turbo
```
**Expected runtime:** 1-3 minutes  
**Use case:** Verify runner works, check schema, smoke test after code changes

### 10-unit validation
```bash
python -m runners.run_fd004_turbo --max-units 10
```
**Expected runtime:** 5-10 minutes  
**Use case:** Validate engine behavior across more units, quick iteration

### 5-unit turbo with cycle limit (smallest dataset)
```bash
python -m runners.run_fd004_turbo --max-units 5 --max-cycles 150
```
**Expected runtime:** <1 minute  
**Use case:** Ultra-fast turbo mode, verify integration works

### With explicit data paths
```bash
python -m runners.run_fd004_turbo \
  --test /path/to/test_FD004.txt \
  --rul /path/to/RUL_FD004.txt \
  --max-units 8
```

### Skip charts for faster runs
```bash
python -m runners.run_fd004_turbo --max-units 10 --no-charts
```
**Expected runtime:** 30% faster (saves chart generation overhead)

### Custom output directory
```bash
python -m runners.run_fd004_turbo \
  --max-units 8 \
  --output-dir outputs/my_turbo_runs
```

## Understanding the Output

All outputs use the same structure as the canonical runner:

```
outputs/turbo_benchmarks/
├── FD004_turbo_20260413T214530Z.csv          # All frames, per-unit details
├── FD004_turbo_scored_20260413T214530Z.csv   # Summary per unit with RUL scoring
├── FD004_turbo_summary_20260413T214530Z.json # Metrics: coverage, lead times, etc.
├── FD004_turbo_lead_time_...png              # (optional) Distribution chart
├── FD004_turbo_timeline_...png               # (optional) Failure timeline
├── FD004_turbo_hero_1_...png                 # (optional) Example unit trajectory
└── FD004_turbo_hero_2_...png                 # (optional) Example unit trajectory
```

## When to Use Each Runner

| Scenario | Runner |
|----------|--------|
| "Does my code change break the engine?" | **Turbo** (5 units) |
| "Did I fix that logic?" | **Turbo** (5-10 units) |
| "Is the schema still valid?" | **Turbo** (5 units) |
| "Rough directional signal?" | **Turbo** (10 units) |
| "Final benchmark number for publication" | **Canonical** (all units) |
| "Compare results to baseline" | **Canonical** (all units) |
| "Acceptance test for production" | **Canonical** (all units) |

## Implementation Notes

### Same Core Engine Path
- Uses `StructuralEngine` from `neraium_core/alignment.py`
- Identical `ENGINE_CONFIG` as canonical
- No alternate engine logic or shortcuts
- Real frame processing, not fake data

### Runtime Reduction Strategy
- Reduces unit count via `--max-units N`
- Optional cycle limit via `--max-cycles N` (keeps first N cycles per unit)
- Charts optional via `--no-charts` (saves ~1-2 minutes on 10 units)

### Code Sharing Opportunity
The helper functions are duplicated from the canonical runner:
- `resolve_data_paths()`
- `classify_alert_quality()`
- `load_fd004()`, `load_rul()`

**Future refactor:** Extract to `runners/shared_fd004.py` to reduce duplication and maintenance burden.

## Data Path Resolution (Same as Canonical)

Priority order:
1. Command-line arguments (`--test`, `--rul`)
2. Environment variable `CMAPSS_DATA_DIR`
3. `./data/` directory in repo

Example with environment:
```bash
export CMAPSS_DATA_DIR=/home/user/cmapss_data
python -m runners.run_fd004_turbo --max-units 10
```

## FAQ

**Q: Can I compare turbo results to canonical results?**  
A: Yes, if you run both on the same unit subset (e.g., units 1-5). The schema and engine are identical. You can do:
```bash
python -m runners.run_fd004_canonical --test ... --rul ...
# Extract units 1-5 from output CSV
python -m runners.run_fd004_turbo --max-units 5
# Compare CSV columns - should be identical
```

**Q: What if my changes break on the 5-unit turbo?**  
A: You've caught the issue early. Turbo is designed for this. Fix and re-run (minutes, not hours).

**Q: Will turbo results differ from canonical?**  
A: Yes, because it's a subset. Individual unit lead times may differ. The engine behavior is identical, but statistics on 5 units vs 100 units will differ. That's expected.

**Q: Should I use turbo for final reporting?**  
A: No. Always run canonical for publication/final numbers.

**Q: Can I reduce it further?**  
A: Yes, try `--max-units 3 --max-cycles 100 --no-charts` for <30 seconds.
