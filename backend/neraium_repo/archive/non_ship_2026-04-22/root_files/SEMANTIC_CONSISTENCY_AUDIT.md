# Tetrahedral Semantic Consistency Audit

## Executive Summary

The tetrahedral visualization is **geometrically correct** but **semantically misleading** when policy state contradicts the tetrahedral interpretation. At frame 81, the UI shows:

```
state: ALERT (policy)
transition: SUSTAINED_TRANSITION
drift: 26.8286
display_health: 0%
tetrahedral label: BALANCED (geometric)
motion: stationary (geometric)
```

This is semantically incoherent because "BALANCED" + "stationary" communicates system stability, while ALERT + high drift + sustained transition indicates system departure.

---

## 1. Root Causes

### 1.1 Tetrahedral State is Purely Geometric

**Location:** `neraium_core/tetrahedral_state.py:106-161`

The tetrahedral state computation is based solely on **normalized weights** from four dimensions:
- `structural_drift_score`
- `relational_instability_score`
- `transition_pressure`
- `temporal_consistency_score`

**Key insight:** The position in 3D space is **deterministic** from these weights—it doesn't correlate with "calm" or "active" states.

### 1.2 "BALANCED" Label is Geometrically Correct but Contextually Misleading

**Lines:** `tetrahedral_state.py:138-142`

```python
state_label = "BALANCED"
if weight_peak >= 0.45:
    state_label = f"{_VERTEX_LABELS[nearest_vertex_key]}_DOMINANT"
elif edge_alignment >= 0.35:
    state_label = "EDGE_ALIGNED"
```

**When does "BALANCED" appear?**
- When the highest weight is < 0.45 (no single dimension dominates)
- AND edge_alignment < 0.35 (no two dimensions aligned)

**Why is this misleading?**
- Geometric balance ≠ system stability
- High drift can coexist with balanced weights if all four dimensions are elevated equally
- Product communication should NOT use "BALANCED" when system is in ALERT state

### 1.3 "Motion" Refers to Geometric Motion, Not State Change

**Location:** `tetrahedral_state.py:73-103`

```python
def compute_motion_features(positions: Sequence[Sequence[float]]) -> dict[str, float | str]:
    """Derive simple speed/curvature from recent tetrahedral positions."""
    ...
    if speed < 0.02:
        movement_summary = "stationary"
```

**What is "speed"?**
- `speed = norm(current_position - previous_position)` in 3D tetrahedral space
- This is **geometric velocity**, NOT state velocity

**Why can it be "stationary" during ALERT?**
- The system can be HIGH-DRIFT while dwelling in the same geometric region
- If drift, transition_pressure, etc. remain elevated but don't **change rapidly**, the position stays fixed
- Position changes only when the **distribution of these four metrics shifts**, not when their absolute values change

**Example:** Frame 81 at ALERT with drift=26.8286
- If `transition_pressure=SUSTAINED_TRANSITION` (high but stable)
- And `structural_drift_score` remains elevated but constant
- The tetrahedral position doesn't move (stationary)
- But the system is clearly in active alert state

### 1.4 Policy State Machine is Drift-Based

**Location:** `neraium_core/alignment.py:1500-1507`

The policy state (STABLE/WATCH/ALERT) is determined by:
1. **Drift momentum** (rate of drift change)
2. **Persistence counters** (how long above threshold)
3. **Latching** (hysteresis against false positives)

```python
if self._alert_latched:
    self._current_alert_state = "ALERT"
elif self._alert_counter >= (self.alert_persistence + extra_persistence_boost):
    self._current_alert_state = "ALERT"
elif self._watch_counter >= (self.watch_persistence + 1):
    self._current_alert_state = "WATCH"
else:
    self._current_alert_state = "STABLE"
```

**Key distinction:** Policy state responds to **momentum and sustained elevation**, not geometric distribution.

### 1.5 WATCH State May Be Skipped in Data Streams

**Evidence:** Drift score pattern in demo shows STABLE → ALERT, rarely WATCH.

**Why?**
- WATCH requires: `watch_counter >= (watch_persistence + 1)` with `smooth > watch_thr`
- ALERT requires: `alert_counter >= alert_persistence` with `smooth > alert_thr`
- If drift jumps directly from below watch_thr to above alert_thr in a few frames:
  - alert_counter increments rapidly
  - watch_counter doesn't get chance to reach persistence threshold
  - State transitions STABLE → ALERT, skipping WATCH

**This is correct behavior but needs transparency.**

---

## 2. Tetrahedral Semantic Problems Diagnosed

### Problem 2.1: "BALANCED" Contradicts High Drift/Instability

When `policy_state == "ALERT"` and `tetrahedral_label == "BALANCED"`:
- User sees calm geometry + urgent policy state
- Cognitive dissonance: which should I trust?
- Confusion about whether system is stable or departing

### Problem 2.2: "Stationary" Contradicts Active Transition

When `transition_state == "SUSTAINED_TRANSITION"` and `movement_summary == "stationary"`:
- "Sustained transition" indicates active state change
- "Stationary" indicates nothing is moving
- These are contradictory unless explicitly explained

### Problem 2.3: Lack of Context Awareness

The tetrahedral state payload has no awareness of:
- Current policy state (ALERT, WATCH, STABLE)
- Drift momentum direction
- Whether change is geometric or state-based

### Problem 2.4: No Flagging of Contradictions

There is no explicit "model tension" or "semantic inconsistency" field to alert users when:
- Geometric state contradicts policy state
- Tetrahedral indicates stability but policy indicates alert
- Motion is low but drift is high

---

## 3. Policy State Machine Audit: Why WATCH May Be Skipped

### 3.1 State Transition Logic

**Location:** `neraium_core/alignment.py:1476-1507`

```python
# watch_counter increments when smooth > watch_thr
if smooth > watch_thr and not is_potential_spike:
    self._watch_counter += 1
else:
    self._watch_counter = max(0, self._watch_counter - 1)  # Fast decay

# alert_counter increments when smooth > alert_thr
if smooth > alert_thr and not is_potential_spike:
    self._alert_counter += 1
else:
    self._alert_counter = max(0, self._alert_counter - 2)  # Even faster decay
```

### 3.2 WATCH Persistence Requirement

```python
elif self._watch_counter >= (self.watch_persistence + 1):
    self._current_alert_state = "WATCH"
```

**Default watch_persistence:** Check `alignment.py` constructor for exact value
- Typically 2-3 frames above `watch_thr`

### 3.3 How WATCH Gets Skipped

**Scenario:** Drift jumps from 0.3 → 0.6 in 2 frames
- Frame N: drift=0.3, below alert_thr (e.g., 0.5) → watch_counter++, alert_counter--
- Frame N+1: drift=0.6, above alert_thr → alert_counter+=1, alert_counter reaches persistence threshold immediately
- **Result:** STABLE → ALERT, WATCH never triggered

**This is mathematically correct** because:
- Drift exceeded watch threshold
- Drift exceeded alert threshold before watch could accumulate persistence
- System genuinely entered alert-level departure

**But users see binary behavior** (STABLE/ALERT), missing the intermediate intensity level.

### 3.4 Transparency Recommendation

Add explicit state transition logging:
- "Transitioned from STABLE → ALERT (skipped WATCH; drift jumped 0.3→0.6)"
- "Transitioned from STABLE → WATCH (drift elevated)"
- "Maintained WATCH (drift still elevated but below alert)"

---

## 4. Semantic Consistency Requirements

### 4.1 Rule: ALERT + Calm Geometry = Contradiction

When `policy_state == "ALERT"` and tetrahedral shows `"BALANCED"`:
- **Add flag:** `"model_tension": "policy_alert_but_geometry_balanced"`
- **Explanation:** "High instability detected (policy), but structural dimensions are equally involved (geometry). Indicates system-wide departure, not localized stress."

### 4.2 Rule: High Drift + Stationary Geometry = Explain Motion Type

When `drift > high_threshold` and `movement_summary == "stationary"`:
- **Add field:** `"motion_type": "geometric_stasis_with_elevated_regime"`
- **Explanation:** "System is dwelling in elevated stress region; individual metric values are not changing rapidly."

### 4.3 Rule: SUSTAINED_TRANSITION + Stationary = Explain Distinction

When `transition_state == "SUSTAINED_TRANSITION"` and `movement_summary == "stationary"`:
- **Add field:** `"motion_context": "active_state_persistence_not_geometric_movement"`
- **Explanation:** "System is in an active transition that persists over multiple frames; geometric position is stable because transition pressure remains constant."

### 4.4 Rule: WATCH Visibility

When state is WATCH:
- **Ensure** the label is prominently displayed (not hidden)
- **Add explanation:** "Drift is elevated and sustained; requires monitoring. System is above normal thresholds but below critical threshold."

---

## 5. Label Improvements

### Current Issues

| Current Label | Geometric Meaning | Product Implication | Problem |
|---|---|---|---|
| `BALANCED` | All four dimensions roughly equal | System is in equilibrium | Misleading when drift is high |
| `stationary` | Position not changing in 3D | Nothing is happening | Misleading during active transitions |
| Movement: N/A | N/A | N/A | No context on state vs. geometric motion |

### Proposed Changes

| New Label | When | Meaning |
|---|---|---|
| `GEOMETRICALLY_NEUTRAL` | weight_peak < 0.45 | All four dimensions equally activated; doesn't imply stability |
| `GEOMETRICALLY_STABLE` | No recent position change | Position fixed in tetrahedral space (geometric motion = 0) |
| `GEOMETRICALLY_ACTIVE` | Significant position changes | Dimensions shifting relative to each other |
| `METRIC_REGIME_ELEVATION` (new) | All metrics high but stable | System is at elevated operating point, not moving geometrically |

### Terminology Recommendations

**For motion_summary (rename to motion_class):**
- `geometric_stationary`: Position hasn't changed in tetrahedral space
- `geometric_drift`: Position drifting within constraints
- `geometric_turning`: Position direction changing significantly
- Add context: When displaying during ALERT, add: "Geometric motion: stationary. State motion: ALERT (active departure from baseline)."

---

## 6. Implementation Plan

### Phase 1: Add Semantic Consistency Flags

**File:** `neraium_core/tetrahedral_state.py`

Add a new function `compute_tetrahedral_semantic_flags()` that takes:
- tetrahedral_state (dict)
- policy_state (str, one of ALERT/WATCH/STABLE)
- transition_state (str)
- drift_score (float)

Returns:
```python
{
    "consistency_status": "coherent" | "tension",
    "tension_type": None | "alert_geometry_mismatch" | "high_drift_stationary" | ...,
    "semantic_context": str,  # Explanation
}
```

### Phase 2: Rename Labels

**tetrahedral_state.py:**
- `BALANCED` → `GEOMETRICALLY_NEUTRAL`
- `movement_summary` → `geometric_motion_class`
- Update test expectations

### Phase 3: Add Policy Context to Payload

**tetrahedral_state.py: compute_tetrahedral_state()**

Add optional parameters:
- `policy_state`: Current ALERT/WATCH/STABLE state
- `transition_state`: WARMUP/STABLE/EMERGING_TRANSITION/SUSTAINED_TRANSITION
- `drift_score`: Current drift value

Include in payload:
- `policy_state` (pass-through for context)
- `semantic_flags` (from semantic consistency check)
- `motion_explanation` (contextual interpretation)

### Phase 4: Update Visualization

**ui/components/tetrahedral_viz.py:**
- Display `semantic_flags` if tension exists
- Show `motion_explanation` alongside `movement_summary`
- Color-code based on consistency status

### Phase 5: Test and Document

Create test cases for:
- ALERT + GEOMETRICALLY_NEUTRAL (should flag tension)
- STABLE + GEOMETRICALLY_NEUTRAL (no tension)
- High drift + geometric_stationary (should explain)
- SUSTAINED_TRANSITION + geometric_stationary (should explain)

---

## 7. Why WATCH Appears Binary in Demo Data

**Analysis of state transitions:**
```
Frame 1-35: STABLE (drift rising gradually)
Frame 36-54: STABLE (drift crosses watch threshold but bounces back)
Frame 55: ALERT (drift exceeds alert threshold, latches)
Frame 56-120: ALERT (drift remains elevated)
```

**Why WATCH is rare:**
1. Drift often jumps directly from STABLE range to ALERT range
2. Once alert latches, it requires drift to drop below (watch_thr × unlatch_ratio) to unlatch
3. Demo data has sharp transitions, not gradual climbs

**This is correct behavior**, but the UI should make it visible that WATCH can exist (e.g., "No WATCH observations in this playback; system mostly STABLE or ALERT").

---

## 8. Recommended UI Changes

### 8.1 HeaderBar Enhancement

```
Current:  Phase: [current_phase]  Confidence: [%]  Frame: [N]/[Total]
Proposed: Phase: [current_phase]  Policy State: [STABLE|WATCH|ALERT]  Confidence: [%]
          Geometric State: [GEOMETRICALLY_NEUTRAL|_DOMINANT|_ALIGNED]
```

### 8.2 TetrahedronPanel Enhancement

```
Add below the 3D plot:
- Motion class: [geometric_stationary|geometric_drift|geometric_turning]
- Semantic consistency: [coherent | tension: alert_but_balanced_geometry]
- Context: [Short explanation of any contradictions]
```

### 8.3 Insight Panels Enhancement

```
Expand "Reasoning" to include:
- Tetrahedral state label (with explanation of what it means)
- Policy state label (with drift/momentum context)
- Any semantic tensions (explicit flagging)
- State transition reason (if changed from previous frame)
```

---

## 9. Conclusion

The tetrahedral state is **technically sound** but **requires semantic context** to be product-appropriate. The three key issues are:

1. **BALANCED label is misleading** when system is in ALERT (should rename to GEOMETRICALLY_NEUTRAL)
2. **Motion/movement lack context** about whether it's geometric or state-based (need explicit distinction)
3. **No flagging of contradictions** when geometry and policy disagree (need explicit tension field)

The WATCH state is correctly skipped when drift jumps directly from STABLE to ALERT thresholds; this should be documented transparently to users.

