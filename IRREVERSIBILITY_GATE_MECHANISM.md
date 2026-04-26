# Irreversibility Factor as Confirmation Gate

## Problem Solved

The previous multiplicative model I(t) = S(t) × R(t) did not affect detection outcomes because:
- I(t) ≤ S(t) always (since R(t) ≤ 1.0)
- I(t) threshold of 0.6 required both S(t) and R(t) to be high simultaneously
- Rare edge case, didn't meaningfully filter detections

## Solution: Gate Mechanism

Irreversibility factor now acts as a **confirmation gate**, not a multiplier.

### Logic Change

**Old (Ineffective)**
```
confirmed = (persistence OR accumulation)
```

**New (Effective)**
```
confirmed = (persistence OR accumulation) AND irreversibility_gate

where:
  irreversibility_gate = True if legacy mode
  irreversibility_gate = (R(t) >= 0.6) if inevitability mode
```

### Implementation Details

In `_process_unit()` confirmation logic:

```python
# Capture irreversibility at this cycle
if self.use_inevitability_score and cycle_output:
    irreversibility_gate_met = cycle_output.irreversibility_factor >= self.inevitability_threshold
else:
    irreversibility_gate_met = True  # No gate in legacy mode

# Confirmation requires gate + (persistence OR accumulation)
if irreversibility_gate_met:
    if raw_alerts_in_window >= self.confirmation_hits:
        # Confirm as "persistence"
        break
    elif rolling_instability >= self.accumulation_threshold:
        # Confirm as "accumulation"
        break
```

## Why This Works

### Irreversibility Factor Behavior

R(t) is computed from 4 dynamic components:

1. **Persistence Score** - fraction of time with high drift
2. **Drift Acceleration** - magnitude of velocity changes
3. **Covariance Persistence** - stability of structural changes
4. **Failure Alignment** - trajectory alignment with known failures

### Phase-Dependent R(t) Values

**Transient Spike** (brief high drift):
- Raw alerts: YES
- Persistence: FAIL (only 1-2 in window)
- R(t): ~0.1-0.3 (low persistence, no acceleration)
- Gate: FAIL (0.3 < 0.6)
- **Result: NO CONFIRMED ALERT** ✓

**Sustained Degradation** (consistent drift increase):
- Raw alerts: YES
- Persistence: PASS (5+ in window)
- R(t): ~0.7-0.9 (high persistence, sustained acceleration)
- Gate: PASS (0.8 ≥ 0.6)
- **Result: CONFIRMED ALERT** ✓

**Recovery Phase** (drift decreasing):
- Raw alerts: MAYBE (marginal)
- Persistence: MAYBE
- R(t): ~0.3-0.5 (decreasing persistence)
- Gate: FAIL (0.4 < 0.6)
- **Result: NO CONFIRMED ALERT** ✓

## Expected Behavior Differences

When running legacy vs inevitability mode:

### Detection Count
- Legacy mode: Higher count (any persistence/accumulation)
- Inevitability mode: Lower count (requires irreversibility too)
- **Difference**: Intentional filtering of transient events

### Detection Timing
- Legacy mode: Earlier alerts (first persistent pattern)
- Inevitability mode: Later alerts (waiting for R(t) to rise)
- **Difference**: Delayed but more confident

### Lead Time Statistics
- Legacy mode: May include premature alerts
- Inevitability mode: More conservative, later alerts
- **Difference**: Shorter lead times due to later detection

### False Positive Rate
- Legacy mode: Higher (detects transient spikes)
- Inevitability mode: Lower (requires structural commitment)
- **Difference**: More selective detection

## Verification

### CSV Output Changes

Three diagnostic columns log scores at confirmation:

```
drift_score_at_confirmation            # S(t)
inevitability_score_at_confirmation    # Previously: I(t) = S(t)*R(t)
                                       # Now: S(t) (R(t) used for gate only)
irreversibility_factor_at_confirmation # R(t): the gate value
```

### Running Both Modes

```bash
# Legacy mode
python tools/cmapss_unified_runner.py \
  --data-dir /path \
  --datasets FD001 \
  --output legacy_results

# Inevitability mode
python tools/cmapss_unified_runner.py \
  --data-dir /path \
  --datasets FD001 \
  --use-inevitability-score \
  --inevitability-threshold 0.6 \
  --output inevitability_results

# Compare
diff legacy_results/FD001/per_unit_results.csv \
     inevitability_results/FD001/per_unit_results.csv
```

Expected: **Different detection patterns** with non-zero changed alerts.

## Key Properties

✓ **Effective**: R(t) now meaningfully gates confirmation
✓ **Physical**: Requires actual irreversibility for detection
✓ **Selective**: Filters transient false alarms
✓ **Measurable**: Different counts/timing vs legacy
✓ **Interpretable**: Gate threshold directly affects detection

## Irreversibility Threshold Selection

Default: `--inevitability-threshold 0.6`

Lower values (0.4-0.5):
- More detections (weaker filter)
- Earlier alerts (less selective)
- More false positives

Higher values (0.7-0.8):
- Fewer detections (stronger filter)
- Later alerts (more selective)
- Fewer false positives

## Backward Compatibility

Legacy mode unaffected:
- No irreversibility gate
- Same detection logic as before
- Same results as previous version

Inevitability mode gate:
- Only applied when `--use-inevitability-score` enabled
- No gate in legacy default mode

## Test Scenario

To verify the gate works:

1. Run with same dataset in both modes
2. Compare per_unit_results.csv files
3. Look for:
   - Different `confirmed_detected` counts
   - Different `first_confirmed_alert_cycle` values
   - Similar `drift_score_at_confirmation` but different gate status
   - `irreversibility_factor_at_confirmation` shows which cycles met gate

Example:
```
Unit 1, Cycle 50:
  drift_score: 0.58
  irreversibility_factor: 0.35  ← Below 0.6 gate
  
Legacy: CONFIRMED (meets persistence)
Inevitability: NOT CONFIRMED (fails gate)
```

