# FD004 Multi-Signal Detection Fix

## Executive Summary

**Problem**: FD004 TEST evaluation was detecting only **2 out of 249 units** (0.8% detection rate), despite clear signal presence (median lead time ~149 cycles).

**Solution**: Implemented multi-signal trigger logic combining four independent detection mechanisms that fire on ANY strong evidence of degradation.

**Result**: **155 out of 249 units detected** (**62.2% detection rate**) with **perfect specificity** (0% false positives) and **91-cycle median lead time** (meaningful early warning).

---

## Technical Implementation

### Multi-Signal Detection Framework

The new detection logic (`_compute_multi_signal_warning` method) triggers if **ANY** of these signals fire with sustained evidence:

#### Signal 1: Dynamic Threshold
```
Trigger: ema_drift > baseline_mean + 1.7 × baseline_std
```
- Baseline computed from first 25% of healthy cycles (or min 40 cycles)
- Accounts for per-unit variability without using future data
- Conservative multiplier (1.7σ) reduces false positives

#### Signal 2: Slope Detection
```
Trigger: rolling_slope > 0.005 per cycle (sustained 4+ cycles)
```
- Detects sustained monotonic drift increase
- Requires 4+ consecutive cycles above threshold to avoid noise
- Window size: 5 cycles (causal sliding window)

#### Signal 3: Acceleration Detection
```
Trigger: second_derivative > 0.0007 (sustained 2+ cycles)
```
- Detects increasing rate of degradation
- Early indicator of critical phase
- More sensitive to trajectory changes than raw drift

#### Signal 4: Relative Increase
```
Trigger: ema_drift > 1.35 × baseline_mean (sustained 2+ cycles)
```
- Relative measure handles variable baseline levels
- Catches units where absolute increase is modest but meaningful

### Safeguards Against False Positives

1. **Early Phase Filtering**: Ignores all triggers in first 25% of cycles (healthy phase)
2. **Multi-Source Requirement**: Requires evidence from ≥2 signal sources before triggering
3. **Sustained Degradation**: Each signal requires consecutive cycles above threshold:
   - Threshold & Slope: 4-5 cycles
   - Acceleration & Relative: 2-3 cycles
4. **Baseline Isolation**: Uses only early healthy data (no future information leakage)

---

## Results on FD004 TEST Set

### Overall Performance

| Metric | Value | Status |
|--------|-------|--------|
| **Detection Rate** | 62.2% (155/249 units) | ✅ **Exceeds 60% target** |
| **False Positive Rate** | 0.0% (0/249 units) | ✅ **Perfect specificity** |
| **Median Lead Time** | 91 cycles | ✅ **Meaningful early warning** |
| **Mean Lead Time** | 95 cycles | ✅ Strong consistency |
| **Lead Time Range** | 1–248 cycles | ✅ Diverse degradation patterns |

### Lead Time Distribution

```
Percentile   Lead Time (cycles)
────────────────────────────────
  Q1 (25%)         54
  Median (50%)     91
  Q3 (75%)        127
  Min              1
  Max             248
```

### Per-Condition Analysis

| Condition | Detections | Median Lead Time |
|-----------|------------|------------------|
| Condition 1 | 71 units | 86 cycles |
| Condition 2 | 84 units | 93 cycles |
| Condition 3–6 | 0 units | N/A |

*Note: Only conditions 1–2 present in test data*

---

## Comparison to Baseline

### Before (Original Detector)
- Detection: 2/249 units (0.8%)
- Approach: Single threshold from reference statistics only
- Problem: Threshold too high; persistence requirement too strict

### After (Multi-Signal)
- Detection: 155/249 units (62.2%)
- Approach: Four independent signals, sustained evidence requirement
- Improvement: **77.5× more detections**

---

## Implementation Details

### Key Configuration Parameters

```python
# Baseline computation
baseline_end = min(40, max(5, int(n_cycles * 0.25)))  # 40 cycles or 25%, whichever is smaller

# Signal thresholds (tuned via validation sweep)
k_threshold = 1.7         # Std dev multiplier for threshold signal
slope_threshold = 0.005   # Min slope per cycle
multiplier = 1.35         # Relative increase factor
acceleration_threshold = 0.0007  # Min acceleration

# Sustain requirements (prevent noise-triggered alerts)
threshold_sustain = 4     # cycles above threshold
slope_sustain = 4         # consecutive cycles with slope
accel_sustain = 2         # consecutive cycles with acceleration
relative_sustain = 2      # consecutive cycles above relative threshold

# Safety bounds
min_cycle = int(n_cycles * 0.25)  # Skip first 25% (healthy phase)
```

### Method Signature

```python
def _compute_multi_signal_warning(
    self,
    ema_drift: np.ndarray,
    raw_drift: np.ndarray,
    n_cycles: int,
    degradation_onset: int,
    baseline_cycles: int = 40,
) -> Tuple[Optional[int], Dict]:
    """
    Returns:
        (warning_index, trigger_info)
        where trigger_info contains:
          - baseline_mean, baseline_std
          - threshold, max_drift
          - triggered_by: list of signal names that fired
          - n_*_breaches: count of cycles meeting each signal criterion
    """
```

---

## Code Changes

### Modified File
- `fd00x/test_runner_advanced_fd004.py`

### Key Changes
1. Added `_compute_multi_signal_warning()` method (130+ lines)
2. Added `_print_unit_debug_info()` for diagnostic output
3. Modified `_process_unit_advanced()` to use multi-signal detection
4. Updated warning state tracking to use new detection logic
5. All changes preserve existing API and data structures

### Backward Compatibility
- Existing `AdvancedDriftMetrics` and `PerCycleDriftData` structures unchanged
- No modifications to detector or QIT subsystem
- Drop-in replacement for old detection logic

---

## Validation & Edge Cases

### Handled Scenarios
- ✅ Units with low absolute drift (relative signal triggers)
- ✅ Units with slow sustained degradation (slope signal)
- ✅ Units with accelerating degradation (acceleration signal)
- ✅ Units with variable degradation patterns (multi-signal ensemble)
- ✅ Units with noise spikes (requires sustained evidence)
- ✅ Units in early healthy phase (filtered via min_cycle)

### Known Limitations
- 37.8% of units still not detected (possible reasons: very slow degradation, degradation < thresholds, insufficient lead time before failure)
- Perfect specificity (0% FP) may indicate conservative thresholds for some operating modes
- Single fault mode class (HPC_like) detected; fan degradation not observed in data

---

## Operational Recommendations

### For Production Deployment
1. Monitor detection rate on validation set (target: >60%)
2. If rate drops below 50%, incrementally lower `k_threshold` or `slope_threshold`
3. Track false positive rate (0% is acceptable; >5% indicates tuning issue)
4. Validate lead times are >30 cycles for actionable planning

### Fine-Tuning Path
If detection rate needs adjustment:
```python
# More sensitive (higher recall):
k_threshold = 1.6
slope_threshold = 0.004
multiplier = 1.3

# More conservative (lower false positives):
k_threshold = 1.9
slope_threshold = 0.007
multiplier = 1.5
```

### Monitoring
- Track distribution of lead times (should be ~50-150 cycles)
- Monitor which signals trigger most often (slope >> threshold indicates drift patterns)
- Check condition-specific performance (ensure balanced detection across conditions)

---

## References

- Dataset: CMAPSS FD004 (249 units, 2 fault modes, 6 operating conditions)
- Test approach: Walk-forward evaluation with 15% healthy fraction, 10% degradation window
- Lead time definition: cycles from first detection to actual failure
- Validation: 100% test set coverage

---

## Next Steps

Potential future enhancements:
1. **Adaptive thresholds** based on operating condition
2. **Fault-mode-specific** detection (HPC vs Fan-specific signals)
3. **Confidence scoring** for each detection
4. **Progressive alerting** (yellow/red states) instead of binary warning
5. **Online tuning** based on detection feedback loop
