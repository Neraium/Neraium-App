# SIIEngine Integration as Single Source of Truth

## Overview

This integration establishes `sii_engine_unified.py` as the canonical engine for all system state computation, ensuring that:

1. **Instability Score** is computed once via unified mathematical pipeline
2. **Regime Classification** (STABLE, TRANSITION, UNSTABLE, LOCK_IN) is deterministic from instability score
3. **Urgency Mapping** (NOMINAL, WATCH, ALERT, CRITICAL) is deterministic from regime + velocity
4. **No UI/API component computes these independently** - all derive from SIIEngine outputs

## Architecture

### Core Components

#### 1. `sii_engine_unified.py` (Pre-existing)
**The mathematical foundation.** Implements the unified pipeline:

```
Raw Sensor Vector
    ↓
Baseline Modeling (μ₀, Σ₀)
    ↓
Rolling Covariance (Σ_t)
    ↓
Structural Drift: S_t = ||Σ_t - Σ₀||_F
Drift Velocity: V_t = dS_t/dt
Transition Pressure: P_t = f(S_t, V_t, d²S_t/dt²)
    ↓
Unified Instability Score: I_t = α*S_t + β*V_t + γ*P_t
    ↓
Regime Classification: regime = classify(I_t)
    ↓
Urgency Mapping: urgency = compute_urgency(regime, V_t)
```

**Outputs:**
- `instability_score` [0, 1]: Normalized composite metric
- `structural_drift` [0, 1]: Frobenius norm of covariance change
- `drift_velocity`: Rate of structural change
- `transition_pressure` [0, 1]: Combined drift × velocity effect
- `regime`: One of {STABLE, TRANSITION, UNSTABLE, LOCK_IN}
- `urgency`: One of {NOMINAL, WATCH, ALERT, CRITICAL}
- `confidence` [0, 1]: Based on baseline quality and history depth

**Fixed Thresholds:**
- STABLE: I_t ≤ 0.30
- TRANSITION: 0.30 < I_t ≤ 0.65
- UNSTABLE: 0.65 < I_t ≤ 0.85
- LOCK_IN: I_t > 0.85

#### 2. `sii_engine_adapter.py` (New)
**Manages per-asset SIIEngine instances and exposes unified state.**

```python
adapter = SIIEngineAdapter()

# Ingest sensor data for asset
state = adapter.ingest(
    sensor_vector=np.array([...]),
    timestamp=1234567.0,
    asset_id="asset_001",
    run_id="run_default"
)

# Returns UnifiedSystemState with ALL state from SIIEngine
assert state.instability_score  # From SIIEngine
assert state.regime  # From SIIEngine (never computed locally)
assert state.urgency  # From SIIEngine (never computed locally)
assert state.structural_drift  # From SIIEngine
assert state.drift_velocity  # From SIIEngine
assert state.detection_context  # For evidence panel
```

**Key Constraint:** The adapter is the ONLY source of regime/urgency/instability_score. No other module computes these.

#### 3. `sii_baseline_comparison.py` (New)
**Validates SIIEngine detection against alternative methods.**

Implements four independent detectors:
- **SIIEngine**: Unified score from structural drift + velocity + pressure
- **Threshold-based**: Fixed threshold on instability (e.g., > 0.65)
- **Z-Score Anomaly**: Multi-dimensional statistical deviation
- **PCA Reconstruction**: Anomaly via principal component residuals

Compares detection timing and lead times:

```python
runner = BaselineComparisonRunner()
result = runner.run(
    sensor_data=np.array([...]),  # Shape (N, d)
    timestamps=np.array([...]),
    unit_id="turbine_042",
    failure_cycle=1250
)

# Output
assert result.sii_detection_cycle == 1100
assert result.sii_lead_time == 150  # Cycles before failure
assert result.threshold_detection_cycle == 1120
assert result.zscore_detection_cycle == 1080
assert result.pca_detection_cycle == 1110

# Export results
runner.export_csv([result], "comparison_results.csv")
```

#### 4. `sii_evidence_builder.py` (New)
**Generates evidence panels for operator display.**

Evidence block includes:
- **Detection Summary**: When was instability first detected?
- **Lead Time**: Cycles remaining before critical threshold
- **Regime Transitions**: Historical transitions with timing
- **Trends**: Instability trend (rising/falling/stable), velocity trend (accelerating/decelerating/stable)
- **Recovery Direction**: Is system moving toward stability?
- **Actionable Observations**: Recommendations for operator

```python
builder = EvidenceBuilder()
evidence = builder.build(state=unified_system_state)

# All evidence derived from SIIEngine outputs only
assert evidence.lead_time_cycles is not None
assert evidence.instability_trend in ["rising", "falling", "stable"]
assert evidence.recovery_alignment == state.recovery_alignment
```

**Evidence Panel Message Examples:**
- "STABLE + NOMINAL": "System operating normally. No action required."
- "TRANSITION + WATCH": "System transitioning. Close monitoring required. Estimated 45 cycles before high-risk state."
- "UNSTABLE + ALERT": "System at high risk of failure. Intervention required within hours."
- "LOCK_IN + CRITICAL": "Imminent failure detected. Escalate to emergency procedures."

#### 5. `sii_decision_narratives.py` (New)
**Generates operator copy from regime + urgency ONLY.**

Deterministic mapping: (regime, urgency) → DecisionNarrative

```python
engine = DecisionNarrativeEngine()
narrative = engine.build_narrative(
    regime="UNSTABLE",
    urgency="ALERT",
    asset_id="pump_003"
)

# Output
assert narrative.primary_message == "[pump_003] System at HIGH RISK. Immediate intervention required."
assert "Emergency response procedures" in narrative.recommended_action
assert narrative.escalation_threshold == "CRITICAL state possible within hours."
```

**Decision Matrix (9 states):**

| Regime | NOMINAL | WATCH | ALERT |
|--------|---------|-------|-------|
| **STABLE** | "Operating normally" | "Elevated activity, investigate" | N/A |
| **TRANSITION** | "Gradual change" | "Close monitoring required" | "Rapid transition, intervention required" |
| **UNSTABLE** | N/A | N/A | "High risk, immediate intervention" |
| **LOCK_IN** | N/A | N/A | "CRITICAL, imminent failure" |

### Integration Points

#### Output Contract
The `output_contract.py` module must pass SIIEngine outputs directly through:

```python
# BEFORE (old way - computed locally)
risk_level = compute_risk_locally(instability_score)  # FORBIDDEN

# AFTER (new way - from SIIEngine)
sii_state = adapter.ingest(...)
risk_level = {
    "LOW": state.regime == "STABLE" and state.urgency == "NOMINAL",
    "MEDIUM": state.regime in ["TRANSITION", "STABLE"] and state.urgency != "NOMINAL",
    "HIGH": state.regime in ["UNSTABLE", "LOCK_IN"],
}
```

#### Alerts Service
The `apps/api/services/alerts.py` module must use only urgency + regime:

```python
# BEFORE (old way - independent thresholds)
if instability_score > 1.5:  # FORBIDDEN
    alert_severity = "high"

# AFTER (new way - from SIIEngine)
if sii_state.urgency == "ALERT" or sii_state.urgency == "CRITICAL":
    alert_severity = "high" if sii_state.urgency == "ALERT" else "critical"
```

#### UI Components
All UI components must consume state from unified endpoint, never compute internally:

```typescript
// BEFORE (old way - computed in component)
const regime = computeRegime(instabilityScore);  // FORBIDDEN

// AFTER (new way - from unified state)
const { regime, urgency, instabilityScore } = useSIIState(assetId);
// regime is guaranteed to match SIIEngine classification
```

## Usage Examples

### Scenario 1: Monitor an Asset

```python
from neraium_core.sii_engine_adapter import get_sii_adapter

adapter = get_sii_adapter()

for cycle in range(1000):
    sensor_data = fetch_sensor_data(asset_id, cycle)
    timestamp = time.time()
    
    # Get unified state (ONLY SOURCE OF TRUTH)
    state = adapter.ingest(sensor_data, timestamp, asset_id)
    
    # Log metrics
    print(f"Cycle {state.cycle}: regime={state.regime}, urgency={state.urgency}, score={state.instability_score:.3f}")
    
    # Generate evidence for operator
    evidence = EvidenceBuilder.build(state)
    print(f"Lead time: {evidence.lead_time_cycles} cycles")
    
    # Generate decision
    narrative = DecisionNarrativeEngine.build_narrative(
        state.regime, state.urgency, asset_id
    )
    print(narrative.primary_message)
```

### Scenario 2: Baseline Comparison

```python
from neraium_core.sii_baseline_comparison import BaselineComparisonRunner

runner = BaselineComparisonRunner(baseline_window=50)

# Load historical data
historical_data = load_cmapss_data("turbofan_042.csv")
X = historical_data["sensors"].values  # Shape (1000, 14)
t = historical_data["timestamp"].values
failure_cycle = 960

# Compare all detectors
result = runner.run(X, t, "turbofan_042", failure_cycle)

print(f"SII detected at cycle {result.sii_detection_cycle}, "
      f"lead time: {result.sii_lead_time} cycles")
print(f"Threshold detected at cycle {result.threshold_detection_cycle}")
print(f"Z-score detected at cycle {result.zscore_detection_cycle}")
print(f"PCA detected at cycle {result.pca_detection_cycle}")

# Export comparison
runner.export_csv([result], "comparison.csv")
```

### Scenario 3: API Response

```python
from neraium_core.sii_engine_adapter import get_sii_adapter
from neraium_core.sii_evidence_builder import EvidenceBuilder
from neraium_core.sii_decision_narratives import DecisionNarrativeEngine

adapter = get_sii_adapter()

# Process request
state = adapter.ingest(sensor_vector, timestamp, asset_id, run_id)

# Build API response
response = {
    "schema_version": "2026-03-29",
    "timestamp": state.timestamp,
    "cycle": state.cycle,
    "state": {
        "instability_score": state.instability_score,
        "regime": state.regime,
        "urgency": state.urgency,
        "structural_drift": state.structural_drift,
        "drift_velocity": state.drift_velocity,
        "confidence": state.confidence,
    },
    "evidence": EvidenceBuilder.build(state).to_dict(),
    "decision": DecisionNarrativeEngine.to_decision_dict(
        state.regime, state.urgency, asset_id
    ),
    "history": {
        "instability": state.instability_history[-50:],
        "regime": state.regime_history[-50:],
        "velocity": state.velocity_history[-50:],
    },
}

return response
```

## Testing Strategy

### Unit Tests
- `test_sii_engine_unified.py`: SIIEngine pipeline correctness (existing)
- `test_sii_integration_constraints.py`: Proves no UI computes regime/urgency independently (new)

### Integration Tests
Tests must verify:
1. All regime values come from `SIIEngine.classify_regime()`, not computed elsewhere
2. All urgency values come from `SIIEngine.compute_urgency()`, not computed elsewhere
3. All instability_score values come from `SIIEngine.compute_instability_score()`, not computed elsewhere
4. API endpoints return values matching SIIEngine outputs exactly
5. Alerts service uses only urgency + regime (never independent thresholds)
6. UI components receive state from unified endpoint (never compute internally)

### Validation Tests
- Baseline comparison runner: Verify SIIEngine outperforms legacy methods
- Lead time analysis: Confirm detection occurs before failure
- Reproducibility: Same input → same output (deterministic)

## Migration Checklist

When integrating with existing systems:

- [ ] Replace all `composite_instability_score_normalized()` calls with `adapter.ingest()` + `state.instability_score`
- [ ] Remove all independent regime computation logic
- [ ] Remove all independent urgency computation logic
- [ ] Update `output_contract.py` to use SIIEngine outputs
- [ ] Update `apps/api/services/alerts.py` to use urgency + regime
- [ ] Update `grow/state_engine.py` to delegate to SIIEngine
- [ ] Add tests proving regime/urgency not computed independently
- [ ] Update UI to consume state from unified endpoint
- [ ] Run baseline comparison: SII vs. old methods
- [ ] Review decision copy: should derive from regime + urgency only
- [ ] Archive deprecated scoring modules

## Performance Notes

- **Baseline Fitting**: ~50 samples to compute baseline covariance (configurable)
- **Update Latency**: Single update call: O(d²) where d = number of sensors
- **Memory**: Per-asset engine stores ~200 samples of history (configurable)
- **Scaling**: Linear in number of assets (one engine per asset)

## Troubleshooting

### "Regime oscillating near thresholds"
Add hysteresis: `if score > threshold + epsilon:` (with configurable epsilon)

### "Baseline computed on abnormal data"
Ensure first `baseline_window` samples are from normal operation

### "Timestamp consistency issues"
Enforce monotonic timestamps; validate `dt > 0` in velocity computation

### "Covariance singular matrix"
Use regularized inverse; SIIEngine applies automatic regularization with `COVARIANCE_REGULARIZATION = 1e-4`

## Architecture Decision Record (ADR)

### Decision: Unified Score vs. Component Transparency
- **Option 1**: Single unified I_t (chosen)
  - **Pros**: Eliminates conflicting signals, single point of configuration
  - **Cons**: Cannot tune components independently
- **Option 2**: Expose component scores separately
  - **Pros**: Fine-grained control
  - **Cons**: Risk of divergent operator interpretations

### Decision: Fixed Weights vs. Dynamic Adaptation
- **Option 1**: Fixed normalized weights (chosen)
  - **Pros**: Stable, reproducible, auditable
  - **Cons**: Cannot adapt to domain-specific characteristics
- **Option 2**: Learn weights from historical data
  - **Pros**: Adaptive to domain
  - **Cons**: Black box, harder to validate

### Decision: Baseline Locking vs. Online Adaptation
- **Option 1**: Lock baseline after warmup (chosen)
  - **Pros**: Prevents "drift creep", reproducible
  - **Cons**: Cannot recover from true baseline shifts
- **Option 2**: Continuous retraining
  - **Pros**: Adapts to real changes
  - **Cons**: Absorbs anomalies into "new baseline"

## References

- `/home/user/neraium-core/neraium_core/sii_engine_unified.py`: Core engine
- `/home/user/neraium-core/neraium_core/sii_engine_adapter.py`: Per-asset wrapper
- `/home/user/neraium-core/neraium_core/sii_baseline_comparison.py`: Validation runner
- `/home/user/neraium-core/neraium_core/sii_evidence_builder.py`: Evidence panel
- `/home/user/neraium-core/neraium_core/sii_decision_narratives.py`: Decision copy
- `/home/user/neraium-core/tests/test_sii_integration_constraints.py`: Integration tests

## Support

For questions or issues:
1. Review this guide's Troubleshooting section
2. Check test cases in `test_sii_integration_constraints.py`
3. Review SIIEngine docstrings in `sii_engine_unified.py`
4. Consult Architecture Decision Records (ADR) section above
