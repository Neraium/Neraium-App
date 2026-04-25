# Using the Drift Detection Test Runner with Your Dataset

## Quick Start (Easiest)

The convenience runner automatically finds your test dataset:

```bash
# Auto-detects: C:\Users\Owner\Desktop\CMAPSSData\test_FD004.txt
python -m fd00x.run_fd004_test_set
```

That's it! It will:
1. ✓ Find your test_FD004.txt file
2. ✓ Run advanced drift detection (all 249 units)
3. ✓ Save results to `fd004_test_set_results/`

## With Options

```bash
# Run on first 50 units (faster for testing)
python -m fd00x.run_fd004_test_set --max-units 50

# Use basic runner instead of advanced
python -m fd00x.run_fd004_test_set --basic

# Custom output directory
python -m fd00x.run_fd004_test_set --output-dir ./my_results

# Override dataset path
python -m fd00x.run_fd004_test_set --path "path/to/test_FD004.txt"

# Combine options
python -m fd00x.run_fd004_test_set --max-units 100 --output-dir ./results
```

## Direct Runner Usage (More Control)

### Advanced Runner (Recommended for FD004)

```bash
# With explicit path
python -m fd00x.run_advanced_fd004_demo --path "C:\Users\Owner\Desktop\CMAPSSData\test_FD004.txt"

# Or with convenience runner
python -m fd00x.run_fd004_test_set
```

**Output:**
- `fd004_advanced_results/fd004_advanced_drift_results.csv` - Per-unit metrics
- `fd004_advanced_results/fd004_advanced_summary.json` - Summary stats
- `fd004_advanced_results/ADVANCED_RESULTS.txt` - Report

### Basic Runner (Simpler, Faster)

```bash
python -m fd00x.run_drift_detection_demo --path "C:\Users\Owner\Desktop\CMAPSSData\test_FD004.txt"
```

**Output:**
- `drift_test_results/fd004_drift_detection_results.csv`
- `drift_test_results/fd004_drift_detection_summary.json`
- `drift_test_results/RESULTS.txt`
- Unit signal visualizations (PNG files)

## Expected Behavior

### When You Run It

```
✓ Found FD004 test set: C:\Users\Owner\Desktop\CMAPSSData\test_FD004.txt

ADVANCED DRIFT DETECTION - NASA CMAPSS FD004
================================================================================

FD004 Complexity:
  • 249 units in test set (hardest CMAPSS dataset)
  • 6 operating conditions (non-linear interactions)
  • 2 fault modes: HPC degradation + Fan degradation
  • Highly variable degradation rates

[1/3] Initializing advanced detector...
[2/3] Running drift detection on FD004 (249 units)...
  [1/249] Unit 1... conditions=3, fault_mode=HPC_like
  [2/249] Unit 2... conditions=4, fault_mode=Fan_like
  ...
```

### Progress Indicator

Each unit shows:
- Unit ID
- Number of operating conditions detected
- Inferred fault mode (HPC_like, Fan_like, or mixed)

### Sample Output Summary

```
────────────────────────────────────────────────────────
RESULTS SUMMARY
────────────────────────────────────────────────────────

Overall Detection Performance:
  Units tested:           249/249
  Detection rate:         82.3% (205 units)
  False positive rate:    3.2% (8 units)

Lead Time Statistics:
  Median:                 145 cycles
  Mean:                   158 cycles
  Range:                  12 - 389 cycles
  Quartiles (Q1-Q3):      95 - 210 cycles

Inferred Fault Modes (249 units, 2 modes):
  HPC_like     : 145 units (58.2%)
  Fan_like     : 104 units (41.8%)

Performance by Operating Condition (6 conditions):
  Condition 1 : 42 detections, median lead_time=180 cycles
  Condition 2 : 38 detections, median lead_time=155 cycles
  Condition 3 : 39 detections, median lead_time=130 cycles
  Condition 4 : 41 detections, median lead_time=175 cycles
  Condition 5 : 39 detections, median lead_time=145 cycles
  Condition 6 : 45 detections, median lead_time=105 cycles

Signal Characteristics:
  Mean raw drift:         0.1234
  Mean EMA drift:         0.0856

Performance:
  Total elapsed time:     62.50 seconds
  Throughput:             3.98 units/second
────────────────────────────────────────────────────────
```

## Troubleshooting

### "Could not find FD004 test set"

The runner looks in these locations (in order):
1. `C:\Users\Owner\Desktop\CMAPSSData\test_FD004.txt`
2. `./data/test_FD004.txt`
3. `./test_FD004.txt`

**Solution:** 
- Move your file to one of these locations, OR
- Use `--path` argument: `python -m fd00x.run_fd004_test_set --path "your/path/test_FD004.txt"`

### "FileNotFoundError: Cannot find training data for FD004"

Make sure you're using the correct filename:
- ✓ `test_FD004.txt` (test set)
- ✓ `train_FD004.txt` (training set - also works)
- ✗ `FD004.txt` (won't work)
- ✗ `fd004.txt` (won't work)

Use `--path` to specify explicitly if needed.

### Very slow or out of memory

Run with `--max-units` to test on a subset first:

```bash
# Test on first 10 units
python -m fd00x.run_fd004_test_set --max-units 10

# Then gradually increase
python -m fd00x.run_fd004_test_set --max-units 50
python -m fd00x.run_fd004_test_set --max-units 100
```

### Different results each run?

Results should be **deterministic** (same each run) because:
- No random initialization in detector
- Walk-forward validation uses only past data
- Threshold computed from healthy reference window

If results vary, it may indicate:
- Different `--max-units` selected different units
- Dataset loading issue (verify file content)
- Different `--path` pointing to different file

## Understanding Output Files

### CSV Results (fd004_advanced_drift_results.csv)

Per-unit metrics with 29 columns:

| Column | Meaning |
|--------|---------|
| unit_id | Engine identifier (1-249) |
| n_cycles | Total operational cycles |
| warning_cycle | Cycle where alert fired (or None) |
| lead_time_cycles | Cycles before degradation onset |
| false_positive | Whether alert was in healthy zone |
| quantum_peak, information_peak, ... | Max component score |
| quantum_mean, information_mean, ... | Mean component score |
| inferred_fault_mode | HPC_like, Fan_like, mixed, or unknown |
| degradation_trajectory | smooth, stepped, or variable |

### JSON Summary (fd004_advanced_summary.json)

Aggregated statistics:

```json
{
  "n_units_tested": 249,
  "detection_rate": 0.823,
  "false_positive_rate": 0.032,
  "median_lead_time": 145.0,
  "mean_lead_time": 158.3,
  "condition_analysis": {
    "1": {"detection_count": 42, "median_lead_time": 180.0},
    "2": {"detection_count": 38, "median_lead_time": 155.0},
    ...
  },
  "fault_mode_distribution": {
    "HPC_like": 145,
    "Fan_like": 104
  }
}
```

## Analysis Workflow

### 1. Quick Test (5 minutes)

```bash
python -m fd00x.run_fd004_test_set --max-units 10
```

Check:
- Any errors?
- Output directory created?
- CSV has 10 rows?

### 2. Medium Analysis (10 minutes)

```bash
python -m fd00x.run_fd004_test_set --max-units 50
```

Check results for:
- Detection rate (should be 70-85%)
- False positive rate (should be <5%)
- Median lead time (should be 100-200 cycles)

### 3. Full Analysis (2 minutes)

```bash
python -m fd00x.run_fd004_test_set
```

Get complete statistics across all 249 units.

## Next Steps

After running the test runner:

1. **Review CSV** - Open `fd004_advanced_drift_results.csv` in Excel
   - Sort by `lead_time_cycles` to see best detections
   - Filter by `false_positive=True` to see missed cases

2. **Check Summary** - Read `fd004_advanced_summary.json`
   - Compare detection rates per condition
   - Review fault mode distribution

3. **Read Report** - Open `ADVANCED_RESULTS.txt`
   - Per-unit summary table
   - Detailed statistics breakdown

4. **Understand Results** - Reference `FD004_ADVANCED_ANALYSIS_GUIDE.md`
   - Interpret condition-specific lead times
   - Understand fault mode signatures
   - Troubleshoot low detection rates

## Performance Expectations

On a modern CPU (Intel i7 or better):

| Dataset | Time | Throughput |
|---------|------|-----------|
| 10 units | ~3 seconds | 3-4 units/sec |
| 50 units | ~15 seconds | 3-4 units/sec |
| 100 units | ~30 seconds | 3-4 units/sec |
| 249 units (all) | ~60 seconds | 3-4 units/sec |

Memory usage: ~2-3 MB per unit (max 500 MB total)

## Getting Help

- **Installation issue:** Check DRIFT_TEST_RUNNER_QUICKSTART.md
- **Understanding results:** See FD004_ADVANCED_ANALYSIS_GUIDE.md
- **Component details:** Read DRIFT_DETECTION_TEST_RUNNER.md
- **Code reference:** Check docstrings in runner files

---

**Ready?**

```bash
python -m fd00x.run_fd004_test_set
```

Results will be in `fd004_test_set_results/` 🚀
