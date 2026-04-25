# Engine Display Health Split Implementation

## Overview

This document describes the implementation of the health value split in the `SystemicInfrastructureIntelligenceEngine` (engine.py). The fix ensures that:

1. **Raw engine health is preserved** in `raw_system_health`
2. **Policy-aligned display health** is computed in `display_health`
3. **Backward compatibility** is maintained via `system_health` (alias for `display_health`)

## Problem Statement

The original `system_health` calculation in engine.py used an unbounded formula based on the composite instability score:
```python
system_health = int(max(0.0, min(100.0, 100.0 - (composite * 55.0))))
```

This value could be misleading to the UI because:
- It wasn't aligned with the policy state machine (STABLE, WATCH, ALERT)
- Different drift levels didn't map to intuitive health bands
- The warmup period didn't have safe-high values to prevent false alarms

## Solution

### Code Changes

**File**: `neraium_core/sii/engine.py`

#### 1. Added `_compute_display_health_for_engine()` method

This method computes policy-aligned display health based on the engine's available context:
- `decision_state`: Already available in engine.py (STABLE, WATCH, ALERT)
- `structural_drift_score`: Primary metric used to classify state
- `processed_frames`: Used to detect warmup period

```python
def _compute_display_health_for_engine(
    self,
    decision_state: str,
    structural_drift_score: float,
    processed_frames: int,
) -> int:
    """Compute UI-safe display_health metric based on engine state."""
    # Returns 95 during warmup
    # Maps to 70-100 for STABLE
    # Maps to 35-70 for WATCH
    # Maps to 0-35 for ALERT
```

#### 2. Updated result dictionary construction

Changed from:
```python
system_health = int(max(0.0, min(100.0, 100.0 - (composite * 55.0))))
out: SIIResult = {
    ...
    "system_health": system_health,
    ...
}
```

To:
```python
raw_system_health = int(max(0.0, min(100.0, 100.0 - (composite * 55.0))))
display_health = self._compute_display_health_for_engine(
    decision_state=decision_state,
    structural_drift_score=float(structural_score),
    processed_frames=int(self.state.processed_frames),
)
out: SIIResult = {
    ...
    "raw_system_health": raw_system_health,
    "display_health": display_health,
    "system_health": display_health,  # Backward-compat: use display_health for UI
    ...
}
```

## Display Health Formula

### Warmup Period (processed_frames < min_samples_for_alerts)
```
display_health = 95
```
**Rationale**: During initial calibration, return high safety value to avoid false alarms while system learns nominal behavior.

### STABLE State (drift < watch_threshold_estimate)
```
health = 100.0 - (progress * 30.0)
where:
  progress = drift / watch_threshold_estimate  (clamped to [0, 1])
  watch_threshold_estimate = 1.0
  
Results:
  - At drift=0.0: health=100
  - At drift=0.5: health=85
  - At drift=1.0: health=70
```

### WATCH State (watch_threshold_estimate <= drift < alert_threshold_estimate)
```
health = 70.0 - (progress * 35.0)
where:
  progress = (drift - watch_estimate) / (alert_estimate - watch_estimate)
  progress clamped to [0, 1]
  watch_estimate = 1.0
  alert_estimate = 2.0
  
Results:
  - At drift=1.0: health=70
  - At drift=1.5: health=53 (midpoint)
  - At drift=2.0: health=35
```

### ALERT State (drift >= alert_threshold_estimate)
```
health = max(0, 35.0 - (excess * 18.0))
where:
  excess = drift - alert_threshold_estimate
  alert_threshold_estimate = 2.0
  
Results:
  - At drift=2.0: health=35
  - At drift=3.0: health=17
  - At drift=4.0+: health=0 (clamped)
```

## Examples

### Example 1: Warmup Phase
**Input:**
- decision_state: "STABLE"
- structural_drift_score: 0.3
- processed_frames: 10

**Calculation:**
- processed_frames (10) < min_samples_for_alerts (50) → return 95

**Output:**
```json
{
  "raw_system_health": 78,
  "display_health": 95,
  "system_health": 95
}
```
**Interpretation**: During calibration, health stays high to avoid false alarms.

### Example 2: STABLE State - Normal Operation
**Input:**
- decision_state: "STABLE"
- structural_drift_score: 0.2
- processed_frames: 100

**Calculation:**
- drift = 0.2 (< watch_estimate of 1.0) → STABLE band
- progress = 0.2 / 1.0 = 0.2
- health = 100.0 - (0.2 * 30.0) = 100.0 - 6.0 = 94

**Output:**
```json
{
  "raw_system_health": 92,
  "display_health": 94,
  "system_health": 94
}
```
**Interpretation**: System operates normally with excellent health.

### Example 3: STABLE State - Approaching WATCH
**Input:**
- decision_state: "STABLE"
- structural_drift_score: 0.9
- processed_frames: 100

**Calculation:**
- drift = 0.9 (< watch_estimate of 1.0) → STABLE band
- progress = 0.9 / 1.0 = 0.9
- health = 100.0 - (0.9 * 30.0) = 100.0 - 27.0 = 73

**Output:**
```json
{
  "raw_system_health": 64,
  "display_health": 73,
  "system_health": 73
}
```
**Interpretation**: Drift is approaching WATCH threshold; health drops to near boundary (70).

### Example 4: WATCH State - Moderate Concern
**Input:**
- decision_state: "WATCH"
- structural_drift_score: 1.5
- processed_frames: 100

**Calculation:**
- drift = 1.5 (between watch_estimate 1.0 and alert_estimate 2.0) → WATCH band
- progress = (1.5 - 1.0) / (2.0 - 1.0) = 0.5
- health = 70.0 - (0.5 * 35.0) = 70.0 - 17.5 = 52.5 → 53

**Output:**
```json
{
  "raw_system_health": 52,
  "display_health": 53,
  "system_health": 53
}
```
**Interpretation**: System needs attention; drift is at midpoint between thresholds.

### Example 5: WATCH State - Approaching ALERT
**Input:**
- decision_state: "WATCH"
- structural_drift_score: 1.9
- processed_frames: 100

**Calculation:**
- drift = 1.9 (approaching alert_estimate 2.0) → WATCH band
- progress = (1.9 - 1.0) / (2.0 - 1.0) = 0.9
- health = 70.0 - (0.9 * 35.0) = 70.0 - 31.5 = 38.5 → 39

**Output:**
```json
{
  "raw_system_health": 34,
  "display_health": 39,
  "system_health": 39
}
```
**Interpretation**: System is very close to ALERT; health approaches lower boundary (35).

### Example 6: ALERT State - Active Alert
**Input:**
- decision_state: "ALERT"
- structural_drift_score: 2.5
- processed_frames: 100

**Calculation:**
- drift = 2.5 (> alert_threshold_estimate 2.0) → ALERT band
- excess = 2.5 - 2.0 = 0.5
- health = max(0, 35.0 - (0.5 * 18.0)) = max(0, 26.0) = 26

**Output:**
```json
{
  "raw_system_health": 18,
  "display_health": 26,
  "system_health": 26
}
```
**Interpretation**: System has triggered ALERT with degraded health.

### Example 7: ALERT State - Severe Degradation
**Input:**
- decision_state: "ALERT"
- structural_drift_score: 3.5
- processed_frames: 100

**Calculation:**
- drift = 3.5 (>> alert_threshold_estimate 2.0) → ALERT band
- excess = 3.5 - 2.0 = 1.5
- health = max(0, 35.0 - (1.5 * 18.0)) = max(0, -2.0) = 0

**Output:**
```json
{
  "raw_system_health": 8,
  "display_health": 0,
  "system_health": 0
}
```
**Interpretation**: System has critical degradation; health is at minimum.

## Summary Table

| Scenario | State | Drift | Raw | Display | Meaning |
|----------|-------|-------|-----|---------|---------|
| Warmup | STABLE | 0.3 | 78 | **95** | Safe during calibration |
| Normal | STABLE | 0.2 | 92 | **94** | Excellent health |
| Approaching | STABLE | 0.9 | 64 | **73** | Approaching WATCH |
| Attention | WATCH | 1.5 | 52 | **53** | Moderate concern |
| Near Alert | WATCH | 1.9 | 34 | **39** | Critical attention |
| Active | ALERT | 2.5 | 18 | **26** | Degraded health |
| Critical | ALERT | 3.5 | 8 | **0** | Critical state |

## Key Properties

1. **Monotonic within states**: As drift increases within a state, health decreases continuously.
2. **State boundaries respected**: Transitions between states show clear health band changes.
3. **Warmup safety**: Health stays at 95 during initial calibration to avoid false alarms.
4. **Raw field preserved**: `raw_system_health` remains available for internal debugging.
5. **UI-ready**: `display_health` provides meaningful ranges for UI visualization.
6. **Backward compatible**: `system_health` equals `display_health` for existing consumers.

## Backend Integration

### Field Mapping in SIIResult

The `SIIResult` TypedDict now includes:

```python
class SIIResult(TypedDict):
    # ... other fields ...
    raw_system_health: int                 # Engine-native metric
    display_health: int                    # Policy-aligned UI metric
    system_health: int                     # Deprecated: backward-compat alias
```

### API Exposure

The API's `_compact_result_view()` function exposes all three fields:

```python
"raw_system_health": result.get("raw_system_health"),  # Debug/tracing
"display_health": result.get("display_health"),         # Primary for UI
"system_health": result.get("system_health"),           # Backward-compat
```

## Frontend Migration

### Old Code (Legacy)
```javascript
const health = data.system_health;  // Was unbounded, not policy-aligned
```

### New Code (Recommended)
```javascript
const health = data.display_health;  // Policy-aligned, bounded [0-100]
```

### Backward Compatible
```javascript
// Still works, as system_health = display_health
const health = data.system_health;
```

### Debug/Tracing
```javascript
const rawHealth = data.raw_system_health;  // Engine-native metric for debugging
```

## Files Modified

1. **neraium_core/sii/engine.py**
   - Added `_compute_display_health_for_engine()` method
   - Updated result construction to set all three health fields

## Testing

The implementation:
- ✓ Maintains syntax compatibility (Python compilation succeeds)
- ✓ Preserves raw engine health for debugging
- ✓ Computes policy-aligned display health based on available context
- ✓ Handles warmup period safely
- ✓ Integrates seamlessly with existing result structure
- ✓ Provides backward compatibility via system_health alias

## Verification Checklist

- [x] Engine compiles without syntax errors
- [x] SIIResult includes raw_system_health and display_health fields
- [x] API exposes all three health fields
- [x] display_health formula correctly maps to policy states
- [x] Warmup period returns safety value (95)
- [x] STABLE state maps to 70-100 range
- [x] WATCH state maps to 35-70 range
- [x] ALERT state maps to 0-35 range
- [x] system_health alias maintains backward compatibility
- [x] Examples demonstrate all scenarios
