# Semantic Consistency Fixes: Summary of Changes

## Overview

This document summarizes the changes made to fix semantic inconsistencies in the tetrahedral visualization when policy state contradicts geometric interpretation.

**Issue:** At frame 81, the UI showed ALERT policy state with BALANCED geometry and stationary motion—a contradiction that confused whether the system was stable or departing.

**Root Cause:** The tetrahedral state is purely geometric and context-unaware. It correctly reports the distribution of four metrics in 3D space, but this geometric balance doesn't correlate with system stability.

---

## Core Changes

### 1. Label Renaming: BALANCED → GEOMETRICALLY_NEUTRAL

**File:** `neraium_core/tetrahedral_state.py`

**Change:** Renamed the state label from `"BALANCED"` to `"GEOMETRICALLY_NEUTRAL"` to clarify that this label describes the geometric distribution of metrics, not system stability.

**Why:** The word "BALANCED" in product communication implies equilibrium or safety, which is misleading when drift is high. "GEOMETRICALLY_NEUTRAL" is explicit: all four dimensions are equally weighted, not that the system is in a safe state.

**Impact:** 
- Backward compatible (still exported in tests and visualization)
- More explicit terminology prevents user confusion
- Same geometric meaning, clearer product implication

---

### 2. Motion Terminology Update

**File:** `neraium_core/tetrahedral_state.py`

**Changes:**
- `"stationary"` → `"geometric_stationary"` (explicitly marks spatial stasis, not behavioral stasis)
- `"turning"` → `"geometric_turning"` (explicitly marks spatial trajectory change)
- `"steady_drift"` → unchanged (already clear)

**Why:** These terms now explicitly indicate they refer to geometric motion in tetrahedral space, not state transitions or behavioral changes. This prevents confusion when geometric motion is low but policy state is ALERT.

**Impact:**
- Users understand "geometric_stationary" doesn't mean nothing is happening—the system state may be changing rapidly
- Clarity that tetrahedral motion is about metric distribution shifts, not system-level changes

---

### 3. New: Semantic Consistency Checking Layer

**File:** `neraium_core/tetrahedral_state.py`

**New Function:** `compute_semantic_consistency_flags()`

```python
def compute_semantic_consistency_flags(
    state_label: str,
    motion_summary: str,
    policy_state: str | None = None,
    transition_state: str | None = None,
    drift_score: float | None = None,
) -> dict[str, object]:
```

**Purpose:** Identifies contradictions between tetrahedral geometry and policy state, returning:

```python
{
    "consistency_status": "coherent" | "tension",
    "tension_type": None | str,  # e.g., "alert_but_geometrically_neutral"
    "semantic_context": str,  # User-facing explanation
}
```

**Tension Types Detected:**
1. `alert_but_geometrically_neutral`: Policy is ALERT, but geometry shows balanced distribution
2. `high_drift_with_geometric_stasis`: Drift > 0.5, but geometric motion is stationary
3. `sustained_transition_with_geometric_stasis`: Transition is sustained, but geometric position unchanged

**Impact:**
- Users are explicitly alerted to contradictions
- Explanation provided for why the contradiction exists (it's mathematically valid)
- Enables better UI to surface these insights

---

### 4. Updated Payload Schema

**File:** `neraium_core/tetrahedral_state.py`

**Enhanced `compute_tetrahedral_state()` function:**

New optional parameters:
- `policy_state: str | None` - Current ALERT/WATCH/STABLE for context
- `transition_state: str | None` - WARMUP/STABLE/EMERGING_TRANSITION/SUSTAINED_TRANSITION

New output fields:
- `geometric_motion_class: str` - Renamed from movement_summary (with "_geometric_" prefix)
- `movement_summary: str` - Kept for backward compatibility
- `semantic_consistency: dict[str, object]` - Consistency flags and context
- `policy_state_context: str` - Pass-through of policy state (if provided)
- `transition_state_context: str` - Pass-through of transition state (if provided)

**Impact:**
- Richer payload for visualization and API consumers
- Backward compatible (old field names retained)
- Context-aware (can be used without policy state, but produces better results with it)

---

### 5. Enhanced Visualization

**File:** `ui/components/tetrahedral_viz.py`

**Changes:**
- Updated to use new field names with fallback to old names
- Displays semantic consistency information when tension detected
- Shows warning (⚠️) for semantic tensions with explanations
- Improved text layout to separate geometric motion from interpretation

**Example Output:**
```
Geometric Position: TRANSITION
Geometric Motion: geometric_stationary

⚠️ Semantic Tension: alert_but_geometrically_neutral

System is in ALERT (high instability), but structural dimensions are equally
involved rather than localized to one axis. Indicates system-wide departure, not
localized stress. All four metrics are significantly elevated.

Interpreted Label: ACTIVE_TRANSITION
```

**Impact:**
- Users understand policy state independently from geometric state
- Contradictions are explicitly flagged and explained
- No confusion about what labels mean

---

### 6. Comprehensive Test Coverage

**File:** `tests/test_tetrahedral_state.py`

**New Tests:**
1. `test_semantic_consistency_flags_alert_neutral_tension()` - Verifies ALERT + GEOMETRICALLY_NEUTRAL flags tension
2. `test_semantic_consistency_flags_coherent_when_stable()` - Verifies STABLE + GEOMETRICALLY_NEUTRAL is coherent
3. `test_semantic_consistency_high_drift_stationary_tension()` - Verifies high drift + stationary flags tension
4. `test_geometric_motion_class_field_present()` - Verifies new field present
5. `test_label_renamed_to_geometrically_neutral()` - Verifies label rename

**Updated Tests:**
- Updated expected keys to include `geometric_motion_class` and `semantic_consistency`

**Impact:**
- Ensures consistency flags work correctly
- Validates label renaming
- Tests new fields are present in output

---

## Documentation

### 1. SEMANTIC_CONSISTENCY_AUDIT.md

Comprehensive 9-section audit including:
- Executive summary of the issue
- Root cause analysis (5 detailed explanations)
- Semantic problems diagnosed (4 issues)
- Policy state machine audit (why WATCH may be skipped)
- Semantic consistency requirements
- Label improvements table
- Implementation plan (5 phases)
- Why WATCH appears binary
- Recommended UI changes

**Purpose:** Provides complete technical understanding of the problem and solution.

### 2. TETRAHEDRAL_SEMANTIC_EXAMPLES.md

Six concrete examples showing:
- Example 1: STABLE + GEOMETRICALLY_NEUTRAL (Coherent)
- Example 2: ALERT + GEOMETRICALLY_NEUTRAL (Tension Flagged) ← Frame 81 scenario
- Example 3: ALERT + STRUCTURAL_DOMINANT (Coherent)
- Example 4: WATCH State Transition (Intermediate)
- Example 5: High Drift + Geometric Stasis (Tension Explained)
- Example 6: Transition Recovery (Improvement Trajectory)

Each example includes:
- Frame data
- Tetrahedral output
- UI display mock
- User interpretation
- Recommended action

**Purpose:** Shows practically how users will see the improved information and what they should understand.

---

## Backward Compatibility

✅ **Full backward compatibility maintained:**

1. Old field names retained:
   - `movement_summary` still exported (alongside new `geometric_motion_class`)
   - Tests updated but old API still works

2. New parameters are optional:
   - `policy_state` and `transition_state` can be omitted
   - If omitted, semantic_consistency shows "coherent" (no policy context to check)

3. Visualization code handles both old and new field names:
   - Falls back to `movement_summary` if `geometric_motion_class` not present
   - Works with datasets that don't have `semantic_consistency` field

---

## Impact on Users

### Before
```
Frame 81:
  state: ALERT
  tetrahedral: BALANCED, stationary

User thinks: "The UI shows BALANCED geometry but ALERT policy. Which one is true?"
```

### After
```
Frame 81:
  Policy State: ALERT
  Geometric Position: [near TRANSITION vertex]
  Geometric Motion: geometric_stationary
  
  ⚠️ Semantic Tension: alert_but_geometrically_neutral
  
  System is in ALERT (high instability), but structural dimensions are equally
  involved rather than localized to one axis. Indicates system-wide departure, not
  localized stress. All four metrics are significantly elevated.

User understands: "All four metrics are elevated equally, which is why geometry shows balanced.
But this balanced distribution doesn't mean the system is safe—it means the system-wide
instability is spread across all dimensions, not localized to one axis. I should respond to ALERT."
```

---

## WATCH State Audit Outcome

**Finding:** WATCH is correctly skipped when drift jumps directly from STABLE range to ALERT range.

**No fix needed:** This is mathematically correct behavior—system genuinely entered alert-level state.

**Transparency improvement:** Updated documentation explains why WATCH doesn't appear in all scenarios.

---

## Files Modified

1. ✏️ `neraium_core/tetrahedral_state.py` - Core logic changes
2. ✏️ `ui/components/tetrahedral_viz.py` - Visualization updates
3. ✏️ `tests/test_tetrahedral_state.py` - New/updated tests
4. 📄 `SEMANTIC_CONSISTENCY_AUDIT.md` - Comprehensive audit (new)
5. 📄 `TETRAHEDRAL_SEMANTIC_EXAMPLES.md` - Practical examples (new)

## Deployment Notes

- No database migrations needed
- No API contract breaking (backward compatible)
- Visualization enhancements are opt-in (fallback to old behavior if semantic_consistency not present)
- Recommend updating frontend to display semantic consistency warnings
- Update API documentation to mention optional policy_state/transition_state parameters

---

## Future Improvements

1. Add more tension types as additional contradictions are identified
2. Consider adding confidence score to consistency checks
3. Expand visualization to show state transition arrows over time
4. Add historical trend analysis for semantic consistency patterns
5. Consider machine learning approach to predict when tension will occur

