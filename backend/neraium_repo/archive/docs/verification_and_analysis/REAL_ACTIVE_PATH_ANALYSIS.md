# FD004 Real Active Path - Detailed Analysis

## End-to-End Flow

```
test_FD004.txt (raw sensor data)
    ↓
run_fd004_by_unit.py
  → StructuralEngine.process_frame() for each frame
  → Outputs: structural_drift_score (huge values: 700k-950k)
    ↓
FD004_by_unit_results.csv
    ↓
run_fd004_with_ims_policy_tuned.py ← THIS IS THE ACTIVE SYSTEM
  → IMS POLICY STATE MACHINE (lines 25-64)
    ↓
FD004_ims_policy_tuned_scored.csv
    ↓
run_fd004_canonical_fast.py
  → Metrics reporting
```

## The Real IMS Policy State Machine (ACTIVE SYSTEM)

**File:** `run_fd004_with_ims_policy_tuned.py` lines 25-64

**Input:** structural_drift_score from engine
**Processing:**
1. Smooth with 25-cycle rolling mean
2. Calculate thresholds:
   - watch_threshold = 65th percentile of smoothed drift
   - alert_threshold = 85th percentile of smoothed drift
3. State machine for each cycle:
   - **Fast-trigger:** if drift > alert_threshold × 1.25 → alert_latched = True
   - **Alert counter:** increments if drift > alert_threshold, decrements otherwise
   - **Watch counter:** increments if drift > watch_threshold, decrements otherwise
   - **State logic:**
     - ALERT if alert_latched = True
     - WATCH if watch_counter ≥ 5 (5 frames of elevation)
     - STABLE otherwise
   - **Reset:** if alert_latched and drift < watch_threshold × 0.75 → clear alert

**Output:** First cycle where state = ALERT

## Current Behavior Analysis

From FD004_by_unit_results.csv (248 units):

**Drift Score Range:**
- Median: 812,670
- Mean: 773,094
- 95th percentile: 923,244
- 6 units: zero drift throughout (automatic misses)

**Policy Threshold Ranges (varies per unit):**
- Watch (65th %ile): typically 800k-850k
- Alert (85th %ile): typically 850k-920k

**Current Results (baseline):**
- Alert Coverage: 97.58% (242 of 248 units)
- Mean Lead Time: 175.49 cycles
- Median Lead Time: 164.5 cycles
- Misses: 6 (units with zero drift)
- Quality: 134 good, 75 very_early, 33 usable, 6 miss

## Problems in Current System

1. **No Rate-of-Change Detection**
   - Counter-based logic treats stable elevation same as rapidly increasing
   - Cannot distinguish between "holding high" vs "accelerating up"

2. **Loose Counter Logic**
   - Alert counter decrements by only 1 per frame (line 43)
   - Can recover from brief dips too easily
   - Fast-trigger (×1.25) can fire once and lock in alert for long time

3. **No Baseline Awareness**
   - Quantile-based thresholds can be misleading if unit has consistently high drift
   - No distinction between units that start high vs units that rise sharply

4. **No Persistent Elevation Validation**
   - Watch counter just needs 5 frames above threshold (line 59)
   - Doesn't check if elevation is sustained (window mean low but tail high)

5. **Reset Threshold Too Loose**
   - Resets only if drift < watch_threshold × 0.75 (line 53)
   - For units with high watch_threshold, this is a big drop
   - Alert can snap back immediately on next spike

## Opportunities for Improvement (in this system)

**Goal:** Reduce false positives while maintaining or improving coverage

**Approach 1: Stricter Counter Logic**
- Require alert_counter ≥ 5 instead of 3 (more persistent confirmation)
- Or increase decrement rate (e.g., decrement by 2 instead of 1)

**Approach 2: Rate-of-Change Detection**
- Calculate rolling derivative of smoothed drift
- Only trigger alert if both:
  - Counter condition met (alert_counter ≥ 3)
  - AND drift is rising (derivative > min_threshold)
- Prevents alerts from flat or declining signals

**Approach 3: Window Mean Validation**
- Before transitioning to ALERT, check that window mean is also elevated
- Prevents "tail high, mean low" scenario

**Approach 4: Baseline-Relative Thresholds**
- Instead of fixed percentiles, compute baseline mean/std early
- Use baseline-relative thresholds: threshold = baseline_mean + K×baseline_std
- Better handles units with different "normal" drift levels

## Constraints for Implementation

✅ Must work within the IMS policy state machine
✅ Must produce FD004_by_unit_results.csv with correct structural_drift_score
✅ Must improve alerts in run_fd004_with_ims_policy_tuned.py
✅ Cannot modify engine process_frame (that would require full FD004 re-run)
✅ Can only modify the policy logic itself

## Recommendation

**Focus on approaches that can be implemented in the IMS policy:**
- Stricter counter logic (approach 1): Easy, low risk, clear impact
- Rate-of-change detection (approach 2): Medium effort, high impact
- Window mean validation (approach 3): Medium effort, catches false positives

These three can all be implemented by modifying `run_fd004_with_ims_policy_tuned.py` lines 35-64 only.
