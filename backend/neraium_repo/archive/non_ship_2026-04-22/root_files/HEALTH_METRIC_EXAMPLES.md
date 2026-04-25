# Display Health Metric Examples

## Overview

The new `display_health` metric replaces the misleading legacy `system_health` calculation. It is:
- **Policy-aligned**: Reflects the state machine state (STABLE, WATCH, ALERT)
- **Continuous**: Interpolates smoothly based on drift relative to thresholds
- **Safe during warmup**: Returns 95 when thresholds are not yet calibrated
- **Preserved raw value**: Original engine health is stored in `raw_system_health`

## Field Mapping

In the backend output, you will now see:
- `raw_system_health`: Engine-native health (legacy formula, preserved for debugging)
- `display_health`: Policy-aligned UI metric (new, primary field for UI)
- `system_health`: Backward-compatibility alias (set to `display_health`)

**For the UI**: Use `display_health` (or `system_health` for backward-compat).

## Health Band Mapping

| State | Range | Description |
|-------|-------|-------------|
| STABLE | 70-100 | System operating nominally |
| WATCH | 35-70 | Drift detected, needs attention |
| ALERT | 0-35 | High drift, requires immediate action |
| WARMUP | ~95 | Thresholds not calibrated yet |

## Example Scenarios

### Example 1: Warmup Phase (Thresholds Not Calibrated)

**Conditions:**
- Policy state: STABLE (default during warmup)
- Watch threshold: None
- Alert threshold: None
- Smoothed drift: 0.3

**Calculation:**
```
Since thresholds are None → return 95
```

**Result:**
```json
{
  "policy_state": "STABLE",
  "raw_system_health": 78,
  "display_health": 95,
  "system_health": 95,
  "structural_drift_score_smoothed": 0.3
}
```

**Interpretation:** During initial calibration, health stays high (95) to avoid false alarms while the system learns nominal behavior.

---

### Example 2: STABLE State - Normal Operation

**Conditions:**
- Policy state: STABLE
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 0.2

**Calculation:**
```
State = STABLE (drift 0.2 < watch_thr 0.5)
Progress towards watch threshold = 0.2 / 0.5 = 0.4 (40%)
health = 100.0 - (0.4 * 30.0) = 100.0 - 12.0 = 88.0
return max(70.0, 88) = 88
```

**Result:**
```json
{
  "policy_state": "STABLE",
  "raw_system_health": 92,
  "display_health": 88,
  "system_health": 88,
  "structural_drift_score_smoothed": 0.2,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System is stable with good health (88/100). As drift was at 40% of the distance to watch threshold, health drops proportionally from the STABLE max of 100 toward 70.

---

### Example 3: STABLE State - Approaching Watch

**Conditions:**
- Policy state: STABLE
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 0.45

**Calculation:**
```
State = STABLE (drift 0.45 < watch_thr 0.5)
Progress towards watch threshold = 0.45 / 0.5 = 0.9 (90%)
health = 100.0 - (0.9 * 30.0) = 100.0 - 27.0 = 73.0
return max(70.0, 73.0) = 73
```

**Result:**
```json
{
  "policy_state": "STABLE",
  "raw_system_health": 64,
  "display_health": 73,
  "system_health": 73,
  "structural_drift_score_smoothed": 0.45,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System is still technically STABLE but drift is approaching watch threshold. Health drops to 73, near the STABLE/WATCH boundary (70).

---

### Example 4: WATCH State - Moderate Concern

**Conditions:**
- Policy state: WATCH
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 0.7

**Calculation:**
```
State = WATCH (watch_thr 0.5 <= drift 0.7 < alert_thr 1.0)
Drift range = 1.0 - 0.5 = 0.5
Progress towards alert = (0.7 - 0.5) / 0.5 = 0.4 (40%)
health = 70.0 - (0.4 * 35.0) = 70.0 - 14.0 = 56.0
return 56
```

**Result:**
```json
{
  "policy_state": "WATCH",
  "raw_system_health": 52,
  "display_health": 56,
  "system_health": 56,
  "structural_drift_score_smoothed": 0.7,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System has transitioned to WATCH state with moderate health degradation (56/100). Drift is 40% of the way from watch to alert threshold.

---

### Example 5: WATCH State - Approaching Alert

**Conditions:**
- Policy state: WATCH
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 0.95

**Calculation:**
```
State = WATCH (watch_thr 0.5 <= drift 0.95 < alert_thr 1.0)
Drift range = 1.0 - 0.5 = 0.5
Progress towards alert = (0.95 - 0.5) / 0.5 = 0.9 (90%)
health = 70.0 - (0.9 * 35.0) = 70.0 - 31.5 = 38.5
return 38
```

**Result:**
```json
{
  "policy_state": "WATCH",
  "raw_system_health": 34,
  "display_health": 38,
  "system_health": 38,
  "structural_drift_score_smoothed": 0.95,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System is still in WATCH but very close to ALERT threshold. Health approaches the WATCH/ALERT boundary (35).

---

### Example 6: ALERT State - Active Alert

**Conditions:**
- Policy state: ALERT
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 1.2

**Calculation:**
```
State = ALERT (drift 1.2 >= alert_thr 1.0)
Excess drift = 1.2 - 1.0 = 0.2
health = max(0, 35.0 - (0.2 * 35.0)) = 35.0 - 7.0 = 28.0
return 28
```

**Result:**
```json
{
  "policy_state": "ALERT",
  "raw_system_health": 18,
  "display_health": 28,
  "system_health": 28,
  "structural_drift_score_smoothed": 1.2,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System has triggered ALERT with degraded health (28/100). Drift is 20% above the alert threshold, causing further health reduction from the ALERT max of 35.

---

### Example 7: ALERT State - Severe Degradation

**Conditions:**
- Policy state: ALERT
- Watch threshold: 0.5
- Alert threshold: 1.0
- Smoothed drift: 2.0

**Calculation:**
```
State = ALERT (drift 2.0 >= alert_thr 1.0)
Excess drift = 2.0 - 1.0 = 1.0
health = max(0, 35.0 - (1.0 * 35.0)) = max(0, 0) = 0
return 0
```

**Result:**
```json
{
  "policy_state": "ALERT",
  "raw_system_health": 2,
  "display_health": 0,
  "system_health": 0,
  "structural_drift_score_smoothed": 2.0,
  "watch_threshold": 0.5,
  "alert_threshold": 1.0
}
```

**Interpretation:** System has severe degradation with critical health (0/100). Drift is 1.0 unit above alert threshold, indicating substantial structural deviation.

---

## Summary Table

| State | Drift | Watch | Alert | raw_health | display_health | Meaning |
|-------|-------|-------|-------|-----------|-----------------|---------|
| WARMUP | 0.3 | None | None | 78 | **95** | Safe initial state |
| STABLE | 0.2 | 0.5 | 1.0 | 92 | **88** | Normal operation |
| STABLE | 0.45 | 0.5 | 1.0 | 64 | **73** | Approaching WATCH |
| WATCH | 0.7 | 0.5 | 1.0 | 52 | **56** | Attention needed |
| WATCH | 0.95 | 0.5 | 1.0 | 34 | **38** | Near ALERT |
| ALERT | 1.2 | 0.5 | 1.0 | 18 | **28** | Active alert |
| ALERT | 2.0 | 0.5 | 1.0 | 2 | **0** | Critical |

---

## Key Properties

1. **Monotonic within states**: As drift increases within a state, health decreases continuously.
2. **State boundaries respected**: Transitions between states show clear health band changes.
3. **Warmup safety**: Health stays at 95 during initial calibration to avoid false alarms.
4. **Raw field preserved**: `raw_system_health` remains available for internal debugging and tracing legacy behavior.
5. **UI-ready**: `display_health` is optimized for UI display with meaningful ranges per state.

---

## Migration Guide

### Frontend Changes

If your frontend is currently reading from the API:

```javascript
// OLD (still works for backward-compatibility)
const health = data.system_health;  // Was misleading legacy value

// NEW (recommended)
const health = data.display_health;  // Policy-aligned, meaningful value

// OPTIONAL: Debug/trace legacy value
const rawHealth = data.raw_system_health;  // Engine-native metric
```

### Backend Extract/Normalization Path

The computation happens in the backend wrapper at:
- **File**: `neraium_core/alignment.py`
- **Method**: `_compute_display_health(policy_state, smoothed_drift, watch_threshold, alert_threshold)`
- **Location**: Lines ~1343-1408

The output is set at:
- **File**: `neraium_core/alignment.py`
- **Location**: Lines ~2503-2545 (in the result dictionary update)

The API exposes both fields via:
- **File**: `apps/api/main.py`
- **Function**: `_compact_result_view()`
- **Location**: Lines ~155-171
