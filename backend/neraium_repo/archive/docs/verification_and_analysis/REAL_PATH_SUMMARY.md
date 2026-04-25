# Real Active FD004 Path - Executive Summary

## What Actually Drives FD004 Results

The FD004 metrics (alert coverage, lead time, false positives) are **100% determined by**:
- **File:** `run_fd004_with_ims_policy_tuned.py`
- **Lines:** 25-64 (the IMS Policy State Machine)
- **Input:** `structural_drift_score` from engine
- **Output:** `alert_cycle` which determines lead time

## The System

```python
# For each unit:
drift_smooth = rolling_mean(structural_drift_score, 25 cycles)
watch_thr = percentile(drift_smooth, 0.65)
alert_thr = percentile(drift_smooth, 0.85)

# State machine per cycle:
if drift > alert_thr * 1.25:
    alert_latched = True
if drift > alert_thr:
    alert_counter += 1
else:
    alert_counter = max(0, alert_counter - 1)
if alert_counter >= 3:
    alert_latched = True
if alert_latched and drift < watch_thr * 0.75:
    alert_latched = False
state = "ALERT" if alert_latched else "WATCH" if watch_counter >= 5 else "STABLE"
```

## Current Results
- **242/248 units** alert before failure (97.58%)
- **6 units** never alert (zero drift throughout)
- **Mean lead:** 175.49 cycles
- **Median lead:** 164.5 cycles

## Where I Was Wrong

I implemented improvements to:
- `transition_detector.py` - offline replay analysis (not used in FD004)
- `classify_drift_state()` in `engine.py` - unused utility function

These don't affect FD004 at all.

## The Correct Path to Improvement

To improve FD004 metrics, I need to improve the **IMS Policy State Machine** in `run_fd004_with_ims_policy_tuned.py`.

**Specific improvements:**
1. **Stricter counter logic** (line 50: change from `>= 3` to `>= 5`)
2. **Rate-of-change detection** (check drift is rising before alerting)
3. **Window mean validation** (confirm sustained elevation, not just tail high)
4. **Better reset logic** (stricter threshold to un-latch alert)

All changes are localized to lines 25-64 of that single file.

## Next Step

Ready to implement Priority 1 & 2 improvements in the **real** active system?

Would you like me to:
1. Implement stricter counter logic?
2. Add rate-of-change detection?
3. Both of the above?
