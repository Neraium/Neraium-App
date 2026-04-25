# Decision Layer: Intelligence to Action

The decision layer sits between structural intelligence (SII) outputs and operator-facing APIs. It transforms raw metrics into **actionable, confident recommendations** while minimizing false alarms.

## Architecture

```
SII Output (drift, state, instability, attribution)
           ↓
    Decision Layer
    ├─ Confidence Scoring (finding vs action)
    ├─ Transient Detection (temporary vs sustained)
    ├─ Specificity Extraction (what changed, not generic drift)
    ├─ Causal Chains (cause → effect propagation)
    ├─ Pattern Matching (historical similarity)
    └─ Recommendation Generation
           ↓
    Decision Object
    ├─ finding_confidence: [0, 1] how sure something happened
    ├─ action_confidence: [0, 1] how sure the action helps
    ├─ transient_score: [0, 1] likelihood this is temporary
    ├─ suppress: bool whether to hide from operators
    ├─ severity: CRITICAL | HIGH | MODERATE | LOW
    ├─ findings: list of specific changes
    ├─ causal_chain: cause→effect sequence
    ├─ pattern_match: similarity to prior behavior
    ├─ recommended_action: what the operator should do
    └─ reasons: why we made this decision
           ↓
      API/UI Layer
```

## Key Principles

### 1. Never Suppress CRITICAL Severity
```python
if severity == "CRITICAL":
    suppress = False  # Always surface critical findings
```

### 2. Separate Finding & Action Confidence
```python
finding_confidence = 0.9  # We're sure something changed
action_confidence = 0.4   # But we're not sure what to do
→ Surface the finding, but don't recommend action
```

### 3. Specific Findings, Not Generic Drift
Instead of: "Drift increased +0.34"
We extract:
- "Correlation loss in pressure-temperature (−0.23)"
- "Vibration subsystem became unstable"
- "Regime shifted from nominal to degraded"

### 4. Transient Events Suppressed Unless High Severity
```python
if transient_score > 0.75 and severity in {"LOW", "MODERATE"}:
    suppress = True  # Likely self-resolving
else:
    suppress = False
```

## Output Contract

Every frame now includes a `decision` field:

```python
result = engine.ingest_frame(
    timestamp=1704067200.0,
    unit_id="pump_A0_001",
    sensors={"temp": 65.3, "vibration": 0.12}
)

# result.decision contains:
{
    "finding_confidence": 0.75,
    "action_confidence": 0.6,
    "transient_score": 0.2,
    "suppress": False,
    "severity": "HIGH",
    "summary": "⚡ HIGH: Structural alignment degraded — Action needed soon",
    "findings": [
        {
            "category": "structural_drift",
            "description": "Structural alignment degraded (score 0.62)",
            "confidence": 0.85,
            "magnitude": 0.24,
            "affected_signals": ["vibration", "pressure"]
        },
        {
            "category": "coordination_failure",
            "description": "Signal relationships became unstable (instability 0.48)",
            "confidence": 0.76,
            "affected_signals": ["vibration", "pressure", "temperature"]
        }
    ],
    "causal_chain": {
        "steps": [
            {
                "trigger": "Baseline-to-recent structural misalignment",
                "effect": "Correlation matrices diverged",
                "strength": 0.62,
                "involved_signals": ["vibration", "pressure"]
            },
            {
                "trigger": "Correlation breakdown",
                "effect": "Relational instability metrics elevated",
                "strength": 0.34,
                "involved_signals": ["vibration", "pressure", "temperature"]
            }
        ],
        "root_cause": "structural_misalignment",
        "confidence": 0.7
    },
    "pattern_match": {
        "pattern_id": "asset_pump_001:run_42",
        "similarity": 0.82,
        "prior_outcome": "self_resolved",
        "time_to_outcome_hours": 8.0,
        "confidence": 0.82
    },
    "recommended_action": "schedule_inspection",
    "recommended_target": "vibration",
    "reasons": [
        "Finding is high-confidence",
        "Causal chain is well-supported",
        "Unlikely to be transient"
    ]
}
```

## Usage Examples

### Example 1: Process a Live Frame with Decision
```python
from neraium_core import Engine

engine = Engine()
result = engine.ingest_frame(
    timestamp=1704067200.0,
    unit_id="pump_A0_001",
    sensors={"temp": 65.3, "vibration": 0.12, "pressure": 101.5}
)

# Check if this should be surfaced to operators
if not result.decision["suppress"]:
    severity = result.decision["severity"]
    summary = result.decision["summary"]
    print(f"{severity}: {summary}")

    # If action is recommended
    if result.decision["recommended_action"]:
        action = result.decision["recommended_action"]
        target = result.decision["recommended_target"]
        print(f"Recommended: {action} on {target}")
```

### Example 2: Pattern Learning
```python
from neraium_core.decision import DecisionEngine, PatternMemory

decision_engine = DecisionEngine()

# After a pattern resolves, record it for future matching
pattern_features = [0.65, 0.48, 0.3, 0.5, 0.5]  # [drift, instability, shock, regime, phase]
decision_engine.pattern_memory.add_pattern(
    pattern_id="pump_001:cycle_42",
    features=pattern_features,
    outcome="self_resolved",
    metadata={"time_to_outcome_hours": 6.5, "severity": "HIGH"}
)

# Next similar event will match this pattern
result = engine.ingest_frame(...)
if result.decision["pattern_match"]:
    match = result.decision["pattern_match"]
    print(f"Similar to {match['pattern_id']}: {match['prior_outcome']}")
```

### Example 3: High-Confidence Filtering
```python
# Only alert if we're confident AND not transient
finding_conf = result.decision["finding_confidence"]
action_conf = result.decision["action_confidence"]
transient = result.decision["transient_score"]

if finding_conf > 0.8 and transient < 0.3:
    print("High-confidence, sustained finding → Alert operator")
elif finding_conf > 0.7 and not result.decision["suppress"]:
    print("Medium-confidence → Monitor, don't alert yet")
else:
    print("Low confidence or transient → Suppress")
```

## Module Structure

### `models.py`
Data classes for the decision output:
- `Decision`: Top-level decision object
- `Finding`: Specific observable change
- `CausalChain`, `CausalStep`: Cause-effect relationships
- `PatternMatch`: Historical similarity
- `Recommendation`: What the operator should do

### `engine.py`
Main orchestrator. Calls sub-modules and assembles the Decision:
```python
decision_engine = DecisionEngine()
decision = decision_engine.decide(sii_output, prev_output)
```

### `confidence.py`
Scores two independent confidence metrics:
- `score_finding_confidence()`: How sure something happened (drift, instability, state)
- `score_action_confidence()`: How sure the action helps (causal chains, patterns, clarity)

### `transient_gating.py`
Detects and suppresses temporary spikes:
- `score_transient_likelihood()`: [0, 1] chance this is temporary
- `is_known_safe_transient()`: Matches startup, maintenance, mode changes
- `apply_transient_suppression()`: Never suppresses CRITICAL

### `specificity.py`
Extracts specific, actionable findings instead of generic drift:
- `extract_findings()`: Builds list of specific changes
- `compute_delta_summary()`: What changed frame-to-frame

### `causal_chains.py`
Builds simple cause→effect chains:
- `build_causal_chain()`: root_cause → intermediate effects → current state
- `chain_strength()`: Confidence in the causal explanation

### `pattern_memory.py`
Matches current state against historical patterns:
- `PatternMemory`: In-memory store with cosine similarity
- `build_feature_vector()`: Normalize metrics to [drift, instability, shock, regime, phase]
- `cosine_similarity()`: Measure vector similarity

### `recommendation.py`
Generates human-facing advisory actions:
- `recommend_action()`: Based on severity and confidence
- Actions: "monitor", "increase_cadence", "schedule_inspection", "urgent_escalation"

### `policy.py`
Decision rules and thresholds:
- `classify_severity()`: STATE + metrics → CRITICAL | HIGH | MODERATE | LOW
- `compute_suppress_flag()`: When to hide findings
- `should_recommend()`: When to suggest action

## Integration Points

### In Engine
The decision layer is integrated into `neraium_core/engine/unified.py`:

```python
# After SII processes a frame:
raw_result = engine.process_frame(engine_frame)

# Decision layer wraps it:
decision_engine = self._get_decision_engine_for_unit(unit_id)
decision = decision_engine.decide(raw_result, prev_output)

# Attached to result:
result.decision = decision.to_dict()
```

### In API
The decision field flows to REST endpoints:

```python
@app.post("/ingest")
def ingest_frame(request: IngestRequest):
    result = engine.ingest_frame(...)
    return {
        "state": result.state,
        "drift_score": result.drift_score,
        "decision": result.decision,  # ← Full decision metadata
    }
```

### In UI
The UI consumes the decision for rendering:

```javascript
const { decision } = await fetch("/ingest").then(r => r.json());

if (!decision.suppress) {
    showAlert(decision.severity, decision.summary);
}

if (decision.recommended_action) {
    showRecommendation(decision.recommended_action, decision.recommended_target);
}

if (decision.pattern_match) {
    showHistoricalContext(
        decision.pattern_match.pattern_id,
        decision.pattern_match.prior_outcome
    );
}
```

## Testing

The decision layer is deterministic and testable:

```python
from neraium_core.decision import DecisionEngine

engine = DecisionEngine()

# Craft a test SII output
sii = {
    "state": "ALERT",
    "structural_drift_score": 0.75,
    "relational_instability_score": 0.5,
    "system_phase": "degrading",
    "attribution": {"top_drivers": ["vibration", "pressure"]},
}

decision = engine.decide(sii)

assert decision.severity == "HIGH"
assert decision.finding_confidence > 0.7
assert not decision.suppress
assert decision.recommended_action is not None
```

## Performance

- **Per-frame overhead**: ~0.5–2ms per decision (Python, no ML)
- **Memory**: ~10MB per decision engine (pattern memory + state tracking)
- **Deterministic**: No randomness, fully reproducible

## Assumptions & Limitations

1. **No future data**: Decisions are made per-frame; no lookahead
2. **Simple causality**: First-pass propagation, not full causal inference
3. **Advisory only**: No control authority or automation
4. **Pattern learning manual**: Operators must explicitly record outcomes
5. **Transient heuristics**: Hardcoded thresholds (can be tuned)

## Next Steps

1. **Collect pattern outcomes**: As operators resolve alerts, record the pattern + outcome
2. **Tune thresholds**: Adjust `policy.py` severity/suppression rules based on production data
3. **Add domain knowledge**: Customize `transient_gating.py` for known equipment behaviors
4. **Expand specificity**: Add more finding categories in `specificity.py`
