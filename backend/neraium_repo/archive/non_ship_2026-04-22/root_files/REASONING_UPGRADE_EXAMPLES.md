# Decision Reasoning Upgrade - Before vs After Examples

## Overview

This document demonstrates the improvements in decision reasoning quality across three core areas:
1. **Causal Abstraction** - from signal-level artifacts to subsystem themes
2. **Temporal Judgment** - explicit classification of degradation phase
3. **Uncertainty Handling** - confidence-aware reasoning under partial evidence

## Example 1: Relational Breakdown Pattern

### Scenario
Unit 001 at cycle 15: Pressure-temperature correlation drops from 0.87 to 0.23 while vibration variance increases 3x. System remains nominally stable on individual signals.

### Before (Phase 1-6)
```
decision_trace: {
  "primary_factor": "signal_13__pressure_correlation dropped",
  "secondary_factors": [
    "Persisted 4 frames",
    "Pattern: persistent_degradation"
  ],
  "confidence_rationale": "High confidence (multi-signal, pattern match)"
}
```

**Problem**: 
- Direct signal references leak implementation details
- Doesn't explain WHY correlation loss matters (subsystem-level causality)
- Operator sees "dropped correlation" not "relational breakdown"

### After (Phase 8+)
```
decision_trace: {
  "primary_factor": "Relational breakdown is the primary driver",
  "secondary_factors": [
    "Persistent degradation confirmed (4 frames)",
    "Trajectory unstable"
  ],
  "confidence_rationale": "High confidence (multi-frame sustained signal)"
}
```

**Improvement**:
- Causal theme abstracts away signal details → "relational breakdown"
- Explains ROOT CAUSE (relational stability loss) not symptoms
- Temporal phase (persistent) + trajectory made explicit
- No raw signal names

---

## Example 2: External Shock vs Persistent Degradation

### Scenario A: External Shock (transient)
Unit 003 at cycle 8: Sudden 0.8 drift spike, trajectory unstable, resolves within 1 frame.

### Before
```
decision_trace: {
  "primary_factor": "HIGH severity detected",
  "secondary_factors": ["First appearance"],
  "confidence_rationale": "Moderate confidence (confirmed signal)"
}
```

**Problem**: Cannot distinguish external shock from persistent problem.

### After (Phase 8+)
```
decision_trace: {
  "primary_factor": "External shock or sudden change detected",
  "secondary_factors": [
    "Signal emerging but not yet persistent"
  ],
  "confidence_rationale": "Pattern match weak; relying on live evidence"
}
```

**Improvement**: Explicit causal theme identifies this as transient anomaly, not structural failure.

---

### Scenario B: Persistent Degradation
Unit 001 at cycle 26: Sustained 0.65 drift over 8 frames, degrading trajectory, coherence declining.

### Before
```
decision_trace: {
  "primary_factor": "HIGH severity with degrading trajectory",
  "secondary_factors": [
    "Persisted 8 frames",
    "Pattern: failure_progression"
  ],
  "confidence_rationale": "High confidence (sustained signal)"
}
```

**Problem**: Same confidence level for both transient and persistent cases.

### After (Phase 8+)
```
decision_trace: {
  "primary_factor": "Persistent structural degradation detected",
  "secondary_factors": [
    "Persistent degradation confirmed (8 frames)",
    "Acceleration detected (drift increasing)"
  ],
  "confidence_rationale": "High confidence (multi-frame sustained signal)"
}
```

**Improvement**: 
- Causal theme distinguishes persistent structural from transient shock
- Temporal phase (persistent) + acceleration velocity made explicit
- Operator understands this is NOT just a blip but sustained failure progression

---

## Example 3: Uncertainty Under Partial Evidence

### Scenario: Early Signal Emergence
Unit 002 at cycle 12: Moderate instability (0.5 score), confidence 0.65, only 2 frames at ELEVATED level, weak pattern match.

### Before
```
decision_trace: {
  "primary_factor": "ELEVATED severity with stable trajectory",
  "secondary_factors": [
    "Confidence trend up"
  ],
  "confidence_rationale": "Emerging confidence (early stage)"
}
```

**Problem**: 
- Doesn't quantify the uncertainty
- No explicit mention that pattern match is weak
- Operator doesn't know how much to trust this signal

### After (Phase 8+)
```
decision_trace: {
  "primary_factor": "Multi-signal instability observed",
  "secondary_factors": [
    "Signal emerging but not yet persistent"
  ],
  "confidence_rationale": "Pattern match weak; relying on live evidence"
}
```

**Improvement**:
- Uncertainty context is EXPLICIT: low_evidence, conflicting_signals, unstable_trajectory, or high_confidence
- Operator knows: "this is emerging, not yet confirmed"
- Confidence rationale explains WHY we're uncertain (weak pattern, not yet persistent)
- Can distinguish "early noise" from "early signal" by monitoring trajectory

---

## Example 4: Temporal Phase Progression

Same unit over multiple frames:

### Frame 22: Onset
```
temporal_phase: "onset"
confidence_rationale: "Signal emerging but not yet persistent"
```
→ Operator: "Watching early signal, not yet actionable"

### Frame 25: Persistent
```
temporal_phase: "persistent"  
confidence_rationale: "High confidence (multi-frame sustained signal)"
```
→ Operator: "Signal confirmed over multiple frames, elevation justified"

### Frame 28: Accelerating
```
temporal_phase: "accelerating"
confidence_rationale: "Trajectory unstable; monitoring for confirmation"
```
→ Operator: "Degradation is worsening, escalation may be needed soon"

---

## Decision Trace Structure (Phase 8+)

```python
decision_trace = {
    "primary_factor": "<causal_theme>",  # One of:
                                          # - relational_breakdown
                                          # - persistent_structural_degradation
                                          # - multi_signal_instability
                                          # - transient_anomaly
                                          # - external_shock
    
    "secondary_factors": [               # 1-3 supporting factors:
        "<temporal_phase>",               # - Persistent degradation confirmed (N frames)
        "<trajectory>",                   # - Trajectory improving/unstable/etc
        "<persistence>"                   # - Acceleration detected, etc
    ],
    
    "confidence_rationale": "<text>"     # Uncertainty-aware explanation:
                                          # - High confidence (multi-frame sustained...)
                                          # - Pattern match weak; relying on live evidence
                                          # - Trajectory unstable; monitoring for confirmation
}
```

---

## Validation Requirements Met

✅ **Deterministic**: All classification functions are pure, no randomness  
✅ **Decision-layer only**: No changes to SII math, signal processing, or detection timing  
✅ **Backward compatible**: New decision_trace replaces old fields, no API breakage  
✅ **Preserves detection timing**: Unit 001 HIGH at cycle 26 remains unchanged  
✅ **No new UI**: Trace format is programmatically stable  
✅ **No new states**: Uses existing Decision model fields  
✅ **No complexity increase**: Reasoning functions are simple, linear-time logic  

---

## Key Improvements Summary

| Aspect | Before | After |
|--------|--------|-------|
| Causal Attribution | Signal-level (signal_13__...) | Subsystem-level (relational_breakdown) |
| Temporal Understanding | Only persistence duration | Phase (onset/persistent/accelerating/chronic/resolving) |
| Uncertainty Explanation | Generic confidence tier | Explicit context (low_evidence/conflicting_signals/unstable_trajectory/high_confidence) |
| Operator Understanding | "What triggered?" | "What's happening + why should we trust it?" |
| Signal Abstraction | Raw metrics visible | Causal themes only |

---

## Testing Coverage

Unit tests verify:
1. **Causal Abstraction** - All 5 themes correctly identified
2. **Temporal Phase Classification** - All 5 phases correctly classified
3. **Uncertainty Handling** - 4 scenarios (high confidence, low evidence, conflicting, unstable)
4. **Formatting** - All outputs are human-readable strings
5. **Enum Validity** - No invalid enum values produced
