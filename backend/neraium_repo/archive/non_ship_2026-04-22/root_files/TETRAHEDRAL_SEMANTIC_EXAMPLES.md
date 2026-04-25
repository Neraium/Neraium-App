# Tetrahedral Semantic Consistency Examples

This document provides concrete examples showing how the updated tetrahedral state visualization handles semantic consistency between policy state, drift, and geometric representation.

---

## Example 1: STABLE System with Balanced Geometry (Coherent)

**Scenario:** Early in monitoring, system is operating normally.

### Frame Data
```python
{
    "policy_state": "STABLE",
    "transition_state": "STABLE",
    "structural_drift_score": 0.15,
    "relational_instability_score": 0.12,
    "transition_pressure": 0.10,
    "temporal_consistency_score": 0.95,
    "drift": 0.10,
    "display_health": 95,
}
```

### Tetrahedral Output
```python
{
    "state_label": "GEOMETRICALLY_NEUTRAL",
    "nearest_vertex": "RELATIONAL",
    "geometric_motion_class": "geometric_stationary",
    "speed": 0.005,
    "semantic_consistency": {
        "consistency_status": "coherent",
        "tension_type": None,
        "semantic_context": "",
    },
}
```

### User Interpretation
✅ **Coherent and Clear**
- Policy state STABLE matches geometric state GEOMETRICALLY_NEUTRAL
- Low drift (0.10) matches low geometric motion
- System appears healthy and stable
- No contradictions to resolve

---

## Example 2: ALERT System with Geometrically Neutral State (Tension Flagged)

**Scenario:** Frame 81 from the issue—system is departing, all dimensions elevated equally.

### Frame Data
```python
{
    "policy_state": "ALERT",
    "transition_state": "SUSTAINED_TRANSITION",
    "structural_drift_score": 0.65,
    "relational_instability_score": 0.68,
    "transition_pressure": 0.62,
    "temporal_consistency_score": 0.35,
    "drift": 26.8286,
    "display_health": 0,
}
```

### Tetrahedral Output
```python
{
    "state_label": "GEOMETRICALLY_NEUTRAL",  # All four metrics high and balanced
    "nearest_vertex": "TRANSITION",
    "geometric_motion_class": "geometric_stationary",  # Position not changing
    "speed": 0.018,  # Very low velocity in tetrahedral space
    "semantic_consistency": {
        "consistency_status": "tension",
        "tension_type": "alert_but_geometrically_neutral",
        "semantic_context": (
            "System is in ALERT (high instability), but structural dimensions are equally "
            "involved rather than localized to one axis. Indicates system-wide departure, not "
            "localized stress. All four metrics are significantly elevated."
        ),
    },
}
```

### UI Display (Updated)
```
Geometric Position: TRANSITION (nearest vertex)
Geometric Motion: geometric_stationary
⚠️ Semantic Tension: alert_but_geometrically_neutral

System is in ALERT (high instability), but structural dimensions are equally
involved rather than localized to one axis. Indicates system-wide departure, not
localized stress. All four metrics are significantly elevated.

Interpreted Label: ACTIVE_TRANSITION
```

### User Interpretation
⚠️ **Tension Explained**
- Policy state ALERT is justified (high drift + sustained transition)
- GEOMETRICALLY_NEUTRAL means all four metrics are equally elevated
- This is **NOT** a sign of stability—it's a sign of **system-wide departure**
- Geometric motion is stationary because the metric distribution isn't **shifting**; rather, all metrics are **sustained at high levels**
- Recommended action: Monitor for escalation or recovery; investigate root cause across all dimensions

---

## Example 3: ALERT System with Structural Dominance (Coherent)

**Scenario:** System failure localized to structural component.

### Frame Data
```python
{
    "policy_state": "ALERT",
    "transition_state": "SUSTAINED_TRANSITION",
    "structural_drift_score": 0.90,
    "relational_instability_score": 0.15,
    "transition_pressure": 0.20,
    "temporal_consistency_score": 0.70,
    "drift": 25.0,
    "display_health": 5,
}
```

### Tetrahedral Output
```python
{
    "state_label": "STRUCTURAL_DOMINANT",  # One dimension dominates
    "nearest_vertex": "STRUCTURAL",
    "geometric_motion_class": "steady_drift",  # Position drifting
    "speed": 0.15,  # Significant motion
    "semantic_consistency": {
        "consistency_status": "coherent",
        "tension_type": None,
        "semantic_context": "",
    },
}
```

### UI Display
```
Geometric Position: STRUCTURAL (nearest vertex)
Geometric Motion: steady_drift
Interpreted Label: STRUCTURAL_STRESS_BUILDING
```

### User Interpretation
✅ **Clear and Coherent**
- Policy state ALERT is justified (high structural drift)
- STRUCTURAL_DOMINANT geometry correctly identifies the problem axis
- Geometric motion shows active drift toward the STRUCTURAL vertex
- Recommendation: Focus investigation on structural components; relational and temporal aspects appear stable

---

## Example 4: WATCH State Transition (Intermediate Monitoring)

**Scenario:** System trending toward alert but not yet critical.

### Frame Data (before WATCH transition)
```python
{
    "policy_state": "WATCH",
    "transition_state": "EMERGING_TRANSITION",
    "structural_drift_score": 0.42,
    "relational_instability_score": 0.38,
    "transition_pressure": 0.40,
    "temporal_consistency_score": 0.60,
    "drift": 12.5,
    "display_health": 25,
}
```

### Tetrahedral Output
```python
{
    "state_label": "GEOMETRICALLY_NEUTRAL",  # No single axis dominates yet
    "nearest_vertex": "STRUCTURAL",  # But closest to structural
    "geometric_motion_class": "steady_drift",  # Moving in tetrahedral space
    "speed": 0.08,
    "semantic_consistency": {
        "consistency_status": "coherent",
        "tension_type": None,
        "semantic_context": "",
    },
}
```

### UI Display
```
Geometric Position: STRUCTURAL (nearest vertex)
Geometric Motion: steady_drift
Policy State: WATCH ← Important: System is trending toward alert
Interpreted Label: STRUCTURAL_STRESS_BUILDING
```

### User Interpretation
⚠️ **Intermediate State—Active Monitoring**
- Policy state WATCH indicates drift is elevated but below ALERT threshold
- Geometric motion is active (steady_drift), indicating the problem is growing
- Trend suggests movement toward STRUCTURAL vertex (and toward ALERT)
- Recommendation: Increase monitoring frequency; prepare response plans; watch for acceleration

---

## Example 5: High Drift with Geometric Stasis and Sustained Transition (Tension Explained)

**Scenario:** System at elevated stress plateau, neither improving nor worsening.

### Frame Data
```python
{
    "policy_state": "ALERT",
    "transition_state": "SUSTAINED_TRANSITION",
    "structural_drift_score": 0.80,
    "relational_instability_score": 0.75,
    "transition_pressure": 0.78,
    "temporal_consistency_score": 0.40,
    "drift": 24.0,
    "display_health": 2,
}
```

### Tetrahedral Output (spanning multiple frames)
```python
# Frames N-1, N, N+1 all have:
{
    "position": [0.45, 0.42, 0.40],  # Same position each frame
    "geometric_motion_class": "geometric_stationary",
    "speed": 0.003,
    "semantic_consistency": {
        "consistency_status": "tension",
        "tension_type": "high_drift_with_geometric_stasis",
        "semantic_context": (
            "System is dwelling in an elevated stress region. Drift is high, but "
            "metric values are not changing rapidly frame-to-frame, so the geometric "
            "position in tetrahedral space remains fixed. This is normal when the system "
            "is sustained at an elevated operating point."
        ),
    },
}
```

### UI Display
```
Geometric Motion: geometric_stationary (across multiple frames)
⚠️ Semantic Tension: high_drift_with_geometric_stasis

System is dwelling in an elevated stress region. Drift is high, but metric values
are not changing rapidly frame-to-frame, so the geometric position in tetrahedral
space remains fixed. This is normal when the system is sustained at an elevated
operating point.
```

### User Interpretation
⚠️ **Plateau State—Requires Intervention**
- System is at ALERT level but NOT changing/worsening
- Geometric position is fixed because all four metrics are **sustained** at high levels
- This is not "stationary" in the sense of being safe—it's **sustained at high stress**
- Geometric motion would resume if one metric starts improving or worsening faster than others
- Recommendation: System requires immediate intervention; current state is unsustainable and may degrade further

---

## Example 6: Transition Recovery (Geometric Motion Shows Improvement)

**Scenario:** System recovering from alert state.

### Frame Data (sequential frames showing recovery)
```python
# Frame 100 (ALERT, high drift)
{
    "policy_state": "ALERT",
    "structural_drift_score": 0.85,
    ...
}
# Tetrahedral position: [0.50, 0.45, 0.48]

# Frame 105 (Still ALERT, but drift declining)
{
    "policy_state": "ALERT",
    "structural_drift_score": 0.65,
    ...
}
# Tetrahedral position: [0.40, 0.38, 0.42]

# Frame 110 (WATCH, drift continuing to decline)
{
    "policy_state": "WATCH",
    "structural_drift_score": 0.42,
    ...
}
# Tetrahedral position: [0.30, 0.28, 0.32]
```

### Tetrahedral Output (Frame 110)
```python
{
    "state_label": "GEOMETRICALLY_NEUTRAL",
    "geometric_motion_class": "steady_drift",  # Moving back toward center
    "speed": 0.12,
    "semantic_consistency": {
        "consistency_status": "coherent",
        "tension_type": None,
        "semantic_context": "",
    },
}
```

### UI Display (showing trajectory)
```
Geometric Position: [0.30, 0.28, 0.32] (moving toward origin/center)
Geometric Motion: steady_drift (trajectory moving in healthy direction)
Policy State: WATCH → Trending down from ALERT
Interpreted Label: [recovering label indicating improvement]
```

### User Interpretation
✅ **Recovery Trajectory**
- System was at ALERT; now transitioning to WATCH
- Geometric motion shows active drift toward lower-stress region (center of tetrahedron)
- Speed of 0.12 indicates significant rate of improvement
- Recommendation: Continue current corrective actions; monitor for stabilization into STABLE state

---

## Summary: Key Changes in Semantic Clarity

| Situation | Old Behavior | New Behavior | Clarity Improvement |
|-----------|---|---|---|
| Frame 81 (ALERT + GEOMETRICALLY_NEUTRAL) | BALANCED geometry suggests calm | Flagged tension + explanation | User understands this is system-wide departure, not localized |
| High drift + stationary geometry | Two unrelated facts | Tension flagged + context | User knows metric values sustained, not changing |
| SUSTAINED_TRANSITION + stationary geometry | Contradictory signals | Tension flagged + distinction | User understands state change vs. geometric motion are different |
| System at alert plateau | Confusing stasis | Explained dwelling/persistence | User knows to take action, not wait for improvement |
| System in WATCH | May be invisible | Explicitly labeled + trending | User aware of intermediate state |

---

## Implementation Notes

### When Displaying Results:

1. **Always show policy state** (STABLE/WATCH/ALERT) prominently
2. **Show geometric_motion_class** with "geometric_" prefix to clarify it's spatial, not behavioral
3. **Flag semantic tensions** with ⚠️ and explanation
4. **Provide context** when tension exists explaining the contradiction
5. **Show drift/momentum** alongside geometric metrics
6. **Track trajectories** over multiple frames to show trend direction

### For API Consumers:

- Check `semantic_consistency.consistency_status` first
  - If `"coherent"`: geometry and policy align; no special explanation needed
  - If `"tension"`: display both the tension_type and semantic_context to user
- Use `geometric_motion_class` to distinguish from behavioral state changes
- Pass `policy_state` and `transition_state` when computing tetrahedral to get consistency flags

