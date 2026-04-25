# Phase 7: System Coherence and Output Quality - Audit

## Executive Summary

Phase 7 audits and improves the decision system to ensure:
1. **Coherence**: All fields are consistent (no contradictions)
2. **Clarity**: Messages are concise and stage-aware
3. **Simplification**: Remove redundant/overlapping fields
4. **Traceability**: Lightweight trace of decision reasoning
5. **Normalization**: Consistent output formatting
6. **Edge cases**: Validated behavior in extreme scenarios

---

## 1. FIELD REDUNDANCY AUDIT

### Current Decision Model Fields (models.py: 135-195)

**Confidence Metrics:**
- `finding_confidence: float` - confidence something happened
- `action_confidence: float` - confidence in the recommendation
- `transient_score: float` - likelihood of temporary event

**Severity & Trajectory:**
- `severity: SeverityLevel` - HIGH, ELEVATED, MODERATE, LOW
- `trajectory: TrajectoryLabel` - improving, stable, degrading, unstable
- In `TemporalContext`: `trajectory` (duplicate field)

**Recommendations (REDUNDANT):**
- `recommended_action: Optional[str]` - action from recommendation module
- `primary_action: Optional[str]` - action from action_horizon module (Phase 6)
- `stage_specific_recommendation: Optional[str]` - stage-based action
- `secondary_actions: list[str]` - supporting actions

**Summary/Text Fields:**
- `summary: str` - human-readable summary
- `reasons: list[str]` - decision reasoning

**Degradation & Staging:**
- `degradation_stage: DegradationStage` - stage classification
- `stage_transition_event: Optional[str]` - when stage changes
- `stage_specific_recommendation: Optional[str]` - recommendation for stage

**Temporal/Pattern Context:**
- `temporal_context: Optional[TemporalContext]` - detailed temporal info
- `pattern_match: Optional[PatternMatch]` - historical pattern match
- `pattern_influence_summary: Optional[str]` - how patterns influenced decision

**Action Planning (Phase 6):**
- `action_horizon: Optional[str]` - "now", "soon", "watchlist"
- `action_priority_reason: Optional[str]` - why this horizon
- `action_tradeoff_note: Optional[str]` - tradeoff explanation

### Identified Issues

#### 1a. Recommendation Field Redundancy
**Problem:** Three fields could map to the same recommendation:
- `recommended_action` (from recommendation module)
- `primary_action` (from action_horizon module - newer, Phase 6)
- `stage_specific_recommendation` (from degradation_stage)

**Impact:** Operators could see conflicting recommendations in output. Unclear which to follow.

**Solution:** Consolidate to:
- Primary source: `primary_action` (from Phase 6, horizon-aware)
- Secondary actions remain: `secondary_actions[]`
- Remove: `recommended_action`, `stage_specific_recommendation`

#### 1b. Duplicate Trajectory
**Problem:** `trajectory` appears in both:
- `Decision.trajectory` (top-level)
- `TemporalContext.trajectory` (nested)

**Impact:** Possible drift between the two; unclear which is authoritative.

**Solution:** Keep only `Decision.trajectory` as canonical. TemporalContext stores its own history for analysis.

#### 1c. Text Field Overlap
**Problem:** Multiple text fields could convey similar information:
- `summary` (human-readable)
- `reasons` (list of reasons)
- `operator_message` (in some contexts)
- Pattern/stage/action explanation fields

**Impact:** Repetitive messaging; inconsistent phrasing.

**Solution:** Simplify to:
- `summary`: concise stage-aware primary message
- `decision_trace`: lightweight explanation (NEW - Phase 7)
- Keep `reasons` for detailed reasoning (internal only)

---

## 2. COHERENCE CONTRADICTION ANALYSIS

### Possible Contradiction Patterns

1. **Suppress + Recommendation Conflict**
   - `suppress=True` but `primary_action` is set
   - **Rule:** If suppress=True, primary_action should be None

2. **Severity + Trajectory Mismatch**
   - `severity="HIGH"` + `trajectory="improving"`
   - **Rule:** trajectory should indicate direction but not override severity

3. **Action Horizon Misalignment**
   - `action_horizon="watchlist"` but `severity="HIGH"`
   - **Rule:** HIGH always maps to "now" or "soon"

4. **Stage + Severity Mismatch**
   - `degradation_stage="failure_approach"` but `severity="LOW"`
   - **Rule:** failure_approach implies at least ELEVATED

5. **Confidence Inversions**
   - `finding_confidence=0.1` but `suppress=False`
   - `action_confidence=0.9` but `severity="LOW"`
   - **Rule:** Low finding_confidence with action should be rare

### Consistency Checks to Implement

```python
def validate_decision_coherence(decision: Decision) -> tuple[bool, list[str]]:
    """Validate internal consistency of decision."""
    errors = []
    
    # Check 1: Suppress consistency
    if decision.suppress and decision.primary_action:
        errors.append("Suppress=True but primary_action is set")
    
    # Check 2: HIGH severity always actionable
    if decision.severity == "HIGH":
        if decision.action_horizon not in {"now", "soon"}:
            errors.append(f"HIGH severity must have horizon 'now'|'soon', got {decision.action_horizon}")
    
    # Check 3: Stage vs Severity alignment
    stage_severity_map = {
        "failure_approach": "HIGH",
        "accelerated_deterioration": "HIGH",
        "chronic_degraded_state": "ELEVATED",
        "persistent_degradation": "ELEVATED",
        "emerging_degradation": "MODERATE",
    }
    expected_min = stage_severity_map.get(decision.degradation_stage)
    if expected_min and decision.severity < expected_min:
        errors.append(f"Stage {decision.degradation_stage} implies min severity {expected_min}")
    
    # Check 4: Action horizon alignment
    if decision.action_horizon == "now":
        if decision.severity not in {"HIGH", "ELEVATED"}:
            errors.append(f"'now' horizon implies HIGH/ELEVATED, got {decision.severity}")
    
    # Check 5: Confidence coherence
    if decision.finding_confidence < 0.3 and decision.action_confidence > 0.8:
        errors.append("Low finding_confidence but high action_confidence")
    
    return len(errors) == 0, errors
```

---

## 3. MESSAGE CLARITY ANALYSIS

### Current Summary Generation (policy.py)

**Examples:**
```
"System stable"
"Early shift detected in structural relationships"
"Persistent degradation observed"
```

### Issues

1. **Inconsistent Stage Awareness**
   - Some summaries mention stage, others don't
   - Horizon information sometimes missing

2. **Repetition in Output**
   - Summary often repeats what's in severity/stage/trajectory
   - Could be more concise

3. **Non-Uniform Phrasing**
   - Some summaries are 1 clause, others are 5
   - No consistent pattern for operator parsing

### Improved Summary Pattern

**Template by Horizon:**
- **"now"**: `"[Stage] degradation detected; immediate attention required."`
- **"soon"**: `"[Stage] degradation persistent; plan inspection soon."`
- **"watchlist"**: `"[Stage] change observed; increase monitoring."`
- **stable**: `"System stable under current analysis."`

**Example Outputs:**
- "Persistent degradation detected; immediate attention required."
- "Emerging degradation persistent; plan inspection soon."
- "Early shift change observed; increase monitoring."

---

## 4. DECISION TRACEABILITY

### Current State
- `reasons: list[str]` exists but is verbose
- No explicit top contributing factors
- Difficult to extract "why was this decision made" in compact form

### Proposed `decision_trace` Field

```python
@dataclass
class DecisionTrace:
    """Lightweight explanation of why this decision was made."""
    primary_factor: str        # Top contributing signal (max 50 chars)
    secondary_factors: list[str]  # 1-2 supporting factors (max 30 chars each)
    confidence_rationale: str   # Brief rationale for confidence level
```

**Example Trace:**
```json
{
  "decision_trace": {
    "primary_factor": "Relational drift elevated (0.82)",
    "secondary_factors": [
      "Persistent at ELEVATED for 5 frames",
      "Trajectory degrading"
    ],
    "confidence_rationale": "Multi-signal agreement (0.87)"
  }
}
```

---

## 5. EDGE CASE SCENARIOS

### Scenario 1: Rapid Oscillation
**Frames 1-5:**
```
Frame 1: ELEVATED → severity
Frame 2: MODERATE → downgrade (valid)
Frame 3: ELEVATED → back up (oscillation detected)
Frame 4: MODERATE → back down
Frame 5: LOW → stable
```

**Expected Behavior:** Suppress action changes, emit suppression warnings.

### Scenario 2: Short-Lived Spike
**Frames:**
```
Frame 1-10: LOW/stable
Frame 11: HIGH (spike)
Frame 12: ELEVATED (falling)
Frame 13: MODERATE (recovering)
Frame 14: LOW (back to baseline)
```

**Expected Behavior:** HIGH at frame 11 escalates properly, then graceful descent.

### Scenario 3: Long Chronic Degradation
**Frames 1-60:**
```
Frame 1: MODERATE
Frame 2-60: ELEVATED (persistent)
Frame 61: HIGH (escalation)
```

**Expected Behavior:** Consistent "soon" horizon for 60 frames, escalation to "now" at frame 61.

### Scenario 4: Near-Failure Acceleration
**Frames 1-30:**
```
Frame 1-20: ELEVATED/stable
Frame 21-25: ELEVATED/degrading (slight trend change)
Frame 26-28: HIGH/degrading (acceleration)
Frame 29: HIGH/failure_approach (critical)
Frame 30: FAILURE
```

**Expected Behavior:** Gradual escalation, critical alert at frame 29.

---

## 6. NUMERIC NORMALIZATION

### Current Issues
- Confidence scores: float, sometimes 8+ decimal places
- Drift scores: raw values, variable precision
- Transient score: [0,1] but sometimes printed with excess decimals

### Standards to Apply

1. **Confidence fields** ([0, 1]): Round to 2 decimal places
   ```python
   round(finding_confidence, 2)  # 0.87 not 0.8723456
   ```

2. **Score fields** ([0, 3]): Round to 3 decimal places
   ```python
   round(drift_score, 3)  # 1.234 not 1.23456789
   ```

3. **Percentage fields**: Round to 1 decimal place
   ```python
   round(oscillation_frequency * 100, 1)  # 45.2% not 45.234%
   ```

4. **Integer fields**: Ensure no decimal point
   ```python
   int(persistence_frames)  # 5 not 5.0
   ```

---

## 7. VALIDATION CHECKLIST

### Unit 001 Regression
- [ ] Frame 26: HIGH severity, "now" horizon
- [ ] Action matches historical expectation
- [ ] Summary is coherent and concise

### FD004 Full Dataset
- [ ] No contradictory outputs across 100+ units
- [ ] Consistent field presence/absence
- [ ] Message quality consistent

### Edge Case Tests
- [ ] Oscillation handled without action bouncing
- [ ] Spike properly escalates then descends
- [ ] Chronic runs maintain horizon without drift
- [ ] Acceleration properly detected and escalated

---

## 8. IMPLEMENTATION ROADMAP

1. **Phase 7a: Audit & Validation** (done - this document)
   - Identify redundancies ✓
   - Identify contradictions ✓
   - Propose solutions ✓

2. **Phase 7b: Coherence Validation Layer**
   - Implement `validate_decision_coherence()`
   - Add validation to DecisionEngine.decide()
   - Create coherence test suite

3. **Phase 7c: Simplification**
   - Remove redundant fields from Decision
   - Consolidate recommendation fields
   - Update Decision.to_dict() and models

4. **Phase 7d: Traceability & Messages**
   - Add `decision_trace` field
   - Improve summary generation
   - Add trace population in engine

5. **Phase 7e: Output Normalization**
   - Implement rounding standards
   - Normalize all numeric output
   - Add serialization formatting

6. **Phase 7f: Edge Case Testing**
   - Create synthetic test scenarios
   - Validate all 4 edge cases
   - Ensure stability across 100+ frames

7. **Phase 7g: Final Validation**
   - Run Unit 001 regression
   - Run FD004 full dataset
   - Validate all assertions

---

## Key Principles

✓ Do NOT modify core SII math
✓ Do NOT modify detection thresholds  
✓ Do NOT modify decision policies (only fix contradictions)
✓ Only add traceability, NOT new decision logic
✓ Focus on clarity, consistency, and reliability
✓ Preserve backward compatibility where possible
