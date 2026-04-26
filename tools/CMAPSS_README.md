# Neraium CMAPSS Unified Validation Runner

Comprehensive validation framework for NASA CMAPSS (Commercial Modular Aero-Propulsion System Simulation) datasets using the **Neraium SII Engine** (System Instability Intelligence).

This tool measures **early instability detection** — how effectively the engine identifies system degradation before failure occurs.

## Purpose

Instead of Remaining Useful Life (RUL) prediction, this runner focuses on **detection lead time**:
- When does the engine first detect instability?
- How many cycles before actual failure?
- What's the aggregate detection coverage across units?

## Quick Start

```bash
# Setup
source .venv/bin/activate
pip install -e .

# Run validation
python tools/cmapss_unified_runner.py \
  --data-dir /path/to/CMAPSSData \
  --datasets FD001 FD002 FD003 FD004 \
  --output validation_out \
  --progress
```

## Data Format

Expected directory structure:
```
/path/to/CMAPSSData/
  test_FD001.txt      (test data)
  RUL_FD001.txt       (remaining useful life values)
  test_FD002.txt
  RUL_FD002.txt
  test_FD003.txt
  RUL_FD003.txt
  test_FD004.txt
  RUL_FD004.txt
```

### Test Data Format
Each row in `test_FD00X.txt`:
```
unit_id cycle setting_1 setting_2 setting_3 s1 s2 ... s21
```

- **unit_id**: Integer 1-248 (varies by dataset)
- **cycle**: Integer cycle number (1, 2, 3, ...)
- **operating settings**: 3 columns (setting_1, setting_2, setting_3)
- **sensors**: 21 columns (s1 through s21)

### RUL File Format
`RUL_FD00X.txt` contains one integer per line (one per test unit):
```
RUL_unit_1
RUL_unit_2
...
```

Where **RUL** is the remaining cycles before failure (observed in test set + RUL = total lifespan).

## Alert Detection Logic

The runner uses **strict priority** for identifying instability alerts:

1. **Regime classification** (primary)
   - TRANSITION: Early degradation detected
   - UNSTABLE: Active degradation
   - LOCK_IN: Critical/imminent failure
   - (STABLE is normal operation)

2. **Urgency levels** (secondary)
   - ALERT: Elevated risk
   - CRITICAL: Imminent danger

3. **Structural drift** (fallback)
   - Configurable threshold (default: 0.5)
   - Measures change in sensor correlation structure

## Core Metrics

Per unit:
- **first_alert_cycle**: Cycle when alert first triggered
- **failure_cycle**: last_observed_cycle + RUL
- **lead_time_cycles**: failure_cycle - first_alert_cycle
- **detected**: Boolean (alert before failure)
- **max_instability**: Peak instability score during lifespan

Aggregate:
- **detection_coverage**: % of units with alerts before failure
- **mean/median lead_time**: Average/median detection advance
- **missed_units**: Units with no alert before failure

## Output Structure

```
validation_out/
  FD001/
    per_unit_results.csv    (1 row per unit)
    summary.json            (aggregate metrics)
  FD002/
    per_unit_results.csv
    summary.json
  FD003/
    per_unit_results.csv
    summary.json
  FD004/
    per_unit_results.csv
    summary.json
  
  all_datasets_summary.csv  (consolidated across FD001-004)
  all_datasets_summary.json
```

### Per-Unit CSV Columns
```
unit_id,total_cycles,failure_cycle,first_alert_cycle,alert_type,
  alert_regime,lead_time_cycles,detected,max_instability,instability_at_alert
```

**alert_type**: `regime` | `urgency` | `structural_drift`

### Summary JSON
```json
{
  "dataset": "FD001",
  "units_total": 100,
  "units_detected": 85,
  "detection_coverage_pct": 85.0,
  "median_lead_time_cycles": 20.0,
  "mean_lead_time_cycles": 21.5,
  "min_lead_time_cycles": 5,
  "max_lead_time_cycles": 45,
  "missed_units": 15,
  "false_positive_count": 0,
  "engine_version": "SIIEngine Unified"
}
```

## CLI Options

```bash
python tools/cmapss_unified_runner.py \
  --data-dir <path>           # Required: CMAPSS data directory
  --datasets FD001 FD002 ...  # Datasets to process (default: all)
  --output <path>             # Output directory (default: validation_out)
  --progress                  # Show progress bar (requires tqdm)
  --drift-threshold <float>   # Structural drift alert threshold (default: 0.5)
  --unit <int>                # Process single unit (debug mode)
  --plot                      # Generate plots (optional, not yet implemented)
```

## Engine Configuration

The runner uses `SIIEngine` with:
- **baseline_window**: 50 cycles (adaptive for short sequences)
- **recent_window**: 12 cycles (rolling window for covariance)
- **drift_weight**: 0.40
- **velocity_weight**: 0.35
- **pressure_weight**: 0.25

## Usage Examples

### Run all datasets with progress
```bash
python tools/cmapss_unified_runner.py \
  --data-dir ~/CMAPSSData \
  --output ~/results \
  --progress
```

### Run single dataset with custom threshold
```bash
python tools/cmapss_unified_runner.py \
  --data-dir ~/CMAPSSData \
  --datasets FD004 \
  --drift-threshold 0.6 \
  --output ~/results/fd004
```

### Debug single unit
```bash
python tools/cmapss_unified_runner.py \
  --data-dir ~/CMAPSSData \
  --datasets FD001 \
  --unit 42 \
  --output ~/debug
```

## Testing

Run the test suite:
```bash
pytest tests/test_cmapss_runner.py -v
```

Tests cover:
- CMAPSS row parsing (21 sensors)
- Failure cycle calculations
- Alert detection logic (regime, urgency, drift threshold)
- Summary metric aggregation
- File I/O (CSV, JSON)
- End-to-end integration

All 23 tests passing ✓

## Interpretation Guide

### High Detection Coverage (>90%)
✓ Engine reliably identifies degradation
✓ Few missed failures
⚠️ May have false positives (check alert_type distribution)

### Long Lead Time (>30 cycles)
✓ Early warning capability
✓ Operators have time to respond
⚠️ May indicate overly sensitive thresholds

### Short Lead Time (<10 cycles)
✓ Accurate degradation detection
⚠️ Limited response time for operators
🔍 Consider threshold tuning

### Missed Units
🔍 Investigate failure modes (sudden vs gradual)
🔍 Check if those units differ in sensor patterns
⚠️ May indicate dataset-specific issues

## Performance Notes

- Processing speed: ~1-10 ms per unit (depends on cycle count)
- Memory: ~100 MB for full FD004 dataset (248 units, ~128k cycles total)
- Parallelization: Can be added for multiple datasets

## Troubleshooting

### "Need at least N samples" error
**Cause**: Unit has fewer baseline cycles than configured baseline_window
**Solution**: Engine automatically adapts for units with <50 cycles

### No alerts detected
- Check `--drift-threshold`: try lowering to 0.4
- Check sensor data quality (NaN values, constant readings)
- Inspect first few cycles of `instability_history` output

### High false positive count
- Check threshold: try raising to 0.6+
- Review `alert_regime` distribution
- Ensure RUL values are accurate

## References

**NASA CMAPSS Dataset**: https://www.nasa.gov/intelligent-systems-division/datasets
**Neraium SII Engine**: `neraium_core/sii_engine_unified.py`
**Adapter Interface**: `neraium_core/sii_engine_adapter.py`

## Citation

If using this validation runner in research, cite:
```
Neraium CMAPSS Unified Validation Runner v1.0
System Instability Intelligence (SII) Engine
https://github.com/neraium/Neraium-App
```
