# Phase 6: Multi-Horizon Action Intelligence

## Overview

Phase 6 extends the decision layer to distinguish between immediate, near-term, and watchlist actions so recommendations become more operationally useful and less binary.

**Status:** ✅ Complete and validated

## Implementation Details

### 1. Action Horizons

Three distinct action horizons have been defined:

- **`now`**: Immediate attention required
  - Maps to: HIGH severity, failure_approach stage, or very short time-to-instability
  - Primary action: `escalate_to_operations` or `urgent_escalation`
  - Example: "System approaching failure; immediate intervention required"

- **`soon`**: Schedule inspection within near term
  - Maps to: ELEVATED severity with persistent degradation, or degrading trajectory
  - Primary action: `schedule_inspection` or `inspect_subsystem`
  - Example: "Degradation persisting; plan inspection within 24-48 hours"

- **`watchlist`**: Increase monitoring cadence
  - Maps to: MODERATE/LOW severity, early stages, or historical self-resolution
  - Primary action: `increase_monitoring` or `continue_observation`
  - Example: "Monitor for pattern confirmation; continue standard cadence"

### 2. Horizon-Aware Policy

The horizon computation maps:
- **Severity** (HIGH, ELEVATED, MODERATE, LOW)
- **Degradation Stage** (baseline → failure_approach)
- **Trajectory** (improving, stable, degrading, unstable)
- **Pattern Outcome** (self_resolved, persistent_degradation, failure_progression, unknown)
- **Time-to-Instability** (forecast cycles to threshold)

Into appropriate action horizons with reasoning.

#### Decision Tree Examples

```
HIGH + any stage          → now
failure_approach + ANY    → now
ELEVATED + persistent     → soon
ELEVATED + degrading      → soon
ELEVATED + short_window   → now (if ≤6 cycles)
MODERATE + degrading      → soon
MODERATE + early_shift    → watchlist
pattern:self_resolved     → downgrade one level
pattern:failure_progress  → upgrade to now
time < 3 cycles           → now
time < 6 cycles + ELEVATED → now
```

### 3. Primary and Secondary Actions

Each decision contains:

**Primary Action**: The recommended immediate action
- Examples: `escalate_to_operations`, `schedule_inspection`, `increase_monitoring`, `continue_observation`

**Secondary Actions**: Supporting complementary actions (up to 3)
- Examples: `validate_sensor_calibration`, `increase_sampling_frequency`, `inspect_subsystems`, `prepare_failover_routing`, `review_configuration_changes`

Secondary actions are contextual and depend on:
- Severity level
- Degradation stage
- Drift score
- System state

### 4. Action Stability (Bounce Prevention)

The system prevents unnecessary action horizon changes between frames:

**Allowed changes:**
- Horizon change if severity escalates
- Horizon change if degradation stage escalates significantly (>1 step)
- Downgrade to lower horizon after 3+ consecutive frames at proposed level
- Immediate upgrade to higher urgency

**Prevented changes:**
- Downgrade without severity or stage change
- Single-frame oscillation
- Noise-induced bouncing

**Example Progression:**
```
Frame 1: ELEVATED/persistent_degradation  → horizon: soon (baseline)
Frame 2: ELEVATED/persistent_degradation  → horizon: soon (STABLE - no change)
Frame 3: MODERATE/emerging_degradation    → horizon: watchlist (ALLOWED - severity dropped)
Frame 4: MODERATE/emerging_degradation    → horizon: watchlist (STABLE)
```

### 5. Pattern Outcome Influence

Historical pattern matching influences horizon decisions:

**Self-resolved patterns:**
- Lower urgency by one horizon level
- MODERATE at persistent_degradation → watchlist (if strong self-resolved match)

**Persistent degradation patterns:**
- Maintain or escalate urgency
- ELEVATED with persistent pattern → stay at soon

**Failure progression patterns:**
- Escalate to highest urgency
- ELEVATED + failure_progression (strong match) → now

**Time-to-outcome:**
- If historical pattern shows rapid progression, escalate
- If historical pattern shows slow progression, can lower

### 6. Time-to-Instability Pressure

Short forecast windows escalate action urgency:

| Time Window | Severity | Action |
|------------|----------|--------|
| ≤3 cycles  | Any      | → now  |
| ≤6 cycles  | ELEVATED | → now  |
| ≤12 cycles | MODERATE | → soon |

## Files Changed

### New Files

1. **`neraium_core/decision/action_horizon.py`** (400 lines)
   - `ActionHorizonPolicy`: Core horizon computation
   - `compute_primary_action()`: Maps horizon → primary action
   - `compute_secondary_actions()`: Generates supporting actions
   - Stability logic, pattern influence, time pressure

2. **`tests/test_phase6_action_horizons.py`** (500 lines)
   - 11 unit tests covering all horizons aspects
   - Pattern influence tests
   - Stability logic tests
   - Decision engine integration tests
   - Recommendation progression tests

3. **`tests/test_phase6_validation.py`** (300 lines)
   - End-to-end validation script
   - Can be run standalone: `python tests/test_phase6_validation.py`
   - Comprehensive output with progression tables

### Modified Files

1. **`neraium_core/decision/models.py`**
   - Extended `Decision` dataclass with Phase 6 fields:
     - `action_horizon: Optional[str]` ("now" | "soon" | "watchlist")
     - `primary_action: Optional[str]` (recommended action)
     - `secondary_actions: list[str]` (supporting actions)
     - `action_priority_reason: Optional[str]` (explanation)
     - `action_tradeoff_note: Optional[str]` (tradeoff notes)
   - Updated `to_dict()` method to include Phase 6 fields

2. **`neraium_core/decision/engine.py`**
   - Import `ActionHorizonPolicy` and action computation functions
   - Initialize `ActionHorizonPolicy` in `__init__`
   - Compute action horizon before building `Decision` object
   - Populate Phase 6 fields in decision output

3. **`tests/test_decision_layer.py`**
   - Updated `test_decision_output_structure` to expect Phase 5+6 fields
   - Test now validates all new fields are present

## Validation Results

### Test Coverage

All 19 tests pass:
- ✅ 11 unit tests (action horizons)
- ✅ 8 validation tests (end-to-end)

### Test Scenarios

1. **Horizon Definitions** (4 tests)
   - HIGH → now
   - ELEVATED + persistent → soon
   - MODERATE + early_shift → watchlist
   - LOW → watchlist

2. **Pattern Influence** (2 tests)
   - Self-resolved patterns lower urgency
   - Failure progression escalates to now

3. **Time Pressure** (1 test)
   - Short window (4 cycles) escalates ELEVATED to now

4. **Action Stability** (1 test)
   - Prevents downgrade without justification
   - Allows downgrade with severity drop

5. **Primary Actions** (1 test)
   - Correct mapping from horizon → action

6. **Secondary Actions** (1 test)
   - HIGH severity generates contextual secondary actions

7. **Decision Engine Integration** (1 test)
   - All Phase 6 fields populated
   - JSON serializable output

8. **Recommendation Progression** (3 tests)
   - Self-resolving scenario: watchlist → soon → watchlist
   - Persistent degradation: watchlist → soon → now
   - Failure progression: rapid escalation to now

9. **Unit 001 Regression** (1 test)
   - HIGH severity maps correctly to action_horizon="now"

10. **Backward Compatibility** (1 test)
    - Existing fields preserved
    - to_dict() includes all fields

### Example Progression Output

```
Frame          Drift    Severity     Horizon      Action
-------        -----    --------     -------      ------
Frame 1        0.10     LOW          watchlist    continue_observation
Frame 2        0.20     LOW          watchlist    continue_observation
Frame 3        0.35     MODERATE     soon         schedule_inspection
Frame 4        0.45     MODERATE     soon         schedule_inspection
Frame 5        0.55     MODERATE     soon         schedule_inspection
Frame 6        0.62     MODERATE     soon         schedule_inspection
Frame 7        0.70     MODERATE     soon         schedule_inspection
Frame 8        0.78     HIGH         now          urgent_escalation
Frame 9        0.85     HIGH         now          urgent_escalation
Frame 10       0.92     HIGH         now          urgent_escalation
```

## Constraints Satisfied

✅ **Deterministic Only**: No randomization, stable across runs
✅ **Decision Layer Only**: No SII math changes, no detection threshold changes
✅ **No UI Work**: Backend only
✅ **No Threshold Retuning**: All existing thresholds preserved
✅ **Live Evidence Preference**: Honors current severity and stage
✅ **Core Math Unchanged**: SII drift/instability computation untouched
✅ **Unit 001 Preserved**: HIGH at cycle 26 still maps correctly
✅ **Backward Compatible**: Existing fields retained, new fields optional

## Key Design Decisions

### 1. Stability Over Reactivity
The system prioritizes consistent action horizons over rapid response to noise. This reduces alert fatigue and provides operators with stable, actionable recommendations.

### 2. Pattern History Integration
Historical pattern matches inform horizon decisions, allowing the system to defer escalation for self-resolving patterns and escalate for failure-prone patterns.

### 3. Time-Window Pressure
Forecasted time-to-instability can override base classification, escalating urgency for short windows while maintaining stability for longer windows.

### 4. Secondary Actions for Context
Primary action defines the main recommendation; secondary actions provide complementary context without creating multiple conflicting directives.

### 5. Deterministic Reasoning
Every horizon decision includes a structured reason explaining why that horizon was chosen, enabling operator understanding and debugging.

## Future Enhancements

Potential extensions (not in Phase 6 scope):

1. **Operator Feedback Loop**: Track which recommendations led to actions and outcomes
2. **Cost-Based Prioritization**: Incorporate operational cost of different actions
3. **Risk Aggregation**: Combine multiple asset horizons for fleet-level perspective
4. **Action Tradeoffs**: Populate `action_tradeoff_note` for cost/benefit analysis
5. **Machine Learning**: Learn horizon-outcome mappings from operational data

## Integration Points

### Upstream (SII)
- No changes required; uses existing drift/instability metrics

### Downstream
- `Decision.action_horizon`: Use for UI/alert categorization
- `Decision.primary_action`: Display as main recommendation
- `Decision.secondary_actions`: Show as supporting context
- `Decision.action_priority_reason`: Explain reasoning to operators

### Backward Compatibility
- All Phase 1-5 fields remain unchanged
- Phase 6 fields are optional (default to None/empty)
- Existing code can ignore Phase 6 fields
- JSON output includes all fields for completeness

## Testing Instructions

Run comprehensive validation:
```bash
python tests/test_phase6_validation.py
```

Run pytest tests:
```bash
python -m pytest tests/test_phase6_action_horizons.py -v
python -m pytest tests/test_phase6_validation.py -v
```

Verify backward compatibility:
```bash
python -m pytest tests/test_decision_layer.py::TestIntegration::test_decision_output_structure -v
```

## Conclusion

Phase 6 successfully implements multi-horizon action intelligence that:
1. ✅ Distinguishes between now/soon/watchlist actions
2. ✅ Maps stage + severity + trajectory + pattern to appropriate horizons
3. ✅ Provides both primary and secondary actions
4. ✅ Maintains action stability over long runs
5. ✅ Preserves all existing functionality and constraints
6. ✅ Is fully validated with 19 comprehensive tests
7. ✅ Is ready for integration with operational systems

The decision layer now produces more operationally useful and less binary recommendations, enabling better resource allocation and more informed human decision-making.
