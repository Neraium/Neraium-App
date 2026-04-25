# System Instability Intelligence (SII) Engine Architecture

## Overview

The SII Engine is a unified mathematical framework that consolidates all structural intelligence metrics into a single coherent pipeline. It replaces the previous fragmented approach with a formal, mathematically grounded system for detecting regime shifts before failure occurs.

**Key Principle:** All outputs derive from a single unified instability score I_t. No independent scoring systems. No duplicate logic.

---

## The Unified Pipeline

### Stage 1: Input Ingestion
```
x_t → forward_fill(NaNs) → x_t (clean)
```
- Accept raw sensor vector
- Handle missing values with forward-fill (assume last known value for NaN)
- Ensures data is in standard form for all downstream computations

### Stage 2: Baseline Modeling
```
{x₁, x₂, ..., x₅₀} → μ₀, Σ₀ (fixed after warmup)
```
- Compute baseline mean μ₀ and covariance Σ₀ from initial window
- Locked after warmup period (no rolling baseline)
- Defines the "normal" operating point
- Regularized inverse covariance Σ₀⁻¹ computed via pseudo-inverse for numerical stability

### Stage 3: Rolling Structure
```
Recent {x_{t-11}, ..., x_t} → Σ_t (rolling covariance)
```
- Maintain a rolling window of recent sensor vectors
- Compute covariance matrix Σ_t from this window
- Captures current correlation structure
- Default window = 12 samples

### Stage 4: Structural Drift
```
Σ_t, Σ₀ → S_t = ||Σ_t - Σ₀||_F / (||Σ₀||_F + ε)
```
- **Frobenius norm:** √(sum of squared differences)
- Measures how much the correlation structure has deformed
- Normalized to [0, 1] range
- **Why:** Covariance changes reveal structural evolution before sensors show direct anomalies

**Formula:**
```
S_t = ||Σ_t - Σ₀||_F / (||Σ₀||_F + ε)
```

### Stage 5: Drift Velocity
```
S_t, t → V_t = dS_t/dt (finite difference)
```
- Rate of change of structural drift
- Computed as: V_t = (S_t - S_{t-1}) / Δt
- High velocity indicates rapid deformation or shock
- Can be negative (recovery) or positive (degradation)

**Why:** Velocity captures the speed of regime transitions, not just magnitude

### Stage 6: Transition Pressure
```
S_t, V_t → P_t = (1 - exp(-S_t)) × |tanh(V_t)|
```
- Combines drift magnitude and velocity nonlinearly
- Drift term (1 - exp(-S_t)) saturates at 1, creating urgency as drift increases
- Velocity term bounds to [-1, 1] via tanh, captures directional change
- Result is in [0, 1]

**Why:** Measures the "force" pushing the system toward instability

### Stage 7: Unified Instability Score
```
S_t, V_t, P_t → I_t = α·S_t + β·V_t + γ·P_t
```
- **Weighted combination** of three components
- Default weights (normalized): α=0.40, β=0.35, γ=0.25
- Result in [0, 1]
- **Single source of truth** for all downstream decisions

**Formula:**
```
I_t = α·S_t + β·|tanh(V_t)| + γ·P_t
where α + β + γ = 1.0
```

**This is the fundamental score. Everything else derives from it.**

### Stage 8: Regime Classification
```
I_t → regime ∈ {STABLE, TRANSITION, UNSTABLE, LOCK_IN}
```

| Regime | Threshold | Interpretation |
|--------|-----------|-----------------|
| **STABLE** | I_t ≤ 0.30 | Normal operation, low risk |
| **TRANSITION** | 0.30 < I_t ≤ 0.65 | System changing, monitor closely |
| **UNSTABLE** | 0.65 < I_t ≤ 0.85 | High risk, intervention likely needed |
| **LOCK_IN** | I_t > 0.85 | Critical state, failure imminent or occurring |

### Stage 9: Urgency Mapping
```
regime, V_t → urgency ∈ {NOMINAL, WATCH, ALERT, CRITICAL}
```

| Regime | Low |V_t| | High |V_t| |
|--------|-------|-------|
| **STABLE** | NOMINAL | WATCH |
| **TRANSITION** | WATCH | ALERT |
| **UNSTABLE** | ALERT | ALERT |
| **LOCK_IN** | CRITICAL | CRITICAL |

**Why:** Combines regime severity with velocity to account for system momentum

---

## Output Object

All computations feed into a single `SIIEngineOutput`:

```python
{
    "timestamp": float,                    # Frame timestamp
    "instability_score": float,            # I_t ∈ [0, 1]
    "structural_drift": float,             # S_t ∈ [0, 1]
    "drift_velocity": float,               # V_t (unbounded)
    "transition_pressure": float,          # P_t ∈ [0, 1]
    "regime": str,                         # STABLE|TRANSITION|UNSTABLE|LOCK_IN
    "urgency": str,                        # NOMINAL|WATCH|ALERT|CRITICAL
    "confidence": float,                   # [0, 1] based on history length
    "gradient_norm": float,                # Direction of instability in sensor space
    "recovery_alignment": float,           # [-1, 1] motion toward/away from stability
    "velocity_history": [float],           # Last 50 velocity values
    "instability_history": [float],        # Last 50 I_t values
    "regime_history": [str],               # Last 50 regime labels
}
```

---

## Consolidation vs. Previous Approach

### Previous System (Fragmented)
- **Multiple independent scoring systems:** stability_energy, alignment scores, drift scores
- **Duplicate logic:** Computing metrics in multiple places
- **No clear derivation:** UI metrics not derived from core signals
- **Scattered calculations:** Across alignment.py, drift.py, stability_energy.py, etc.
- **Hard to maintain:** Changes to core logic require updates in multiple files

### Unified System (SII Engine)
- **Single source of truth:** I_t
- **Linear derivation:** All outputs trace back to fundamental pipeline
- **One implementation path:** No duplicate logic
- **Clear mathematical structure:** Every step documented with equations
- **Maintainable:** Changes to pipeline in one place

---

## Key Design Decisions

### 1. Covariance-Based Drift (Not Point Estimates)
Why not just track individual sensor values?
- **Correlation structure** reveals system-wide deformation
- Captures **coupling** between sensors
- Early warning before any single sensor shows anomaly
- More robust to noise in individual channels

### 2. Frobenius Norm (Not Spectral Norm)
Why Frobenius instead of largest eigenvalue?
- Frobenius: square root of sum of squared elements
- Captures **all** covariance changes
- Spectral norm: only largest eigenvalue
- Frobenius more sensitive to widespread changes

### 3. Nonlinear Pressure Function
Why not just add S_t and V_t linearly?
- Linear: I_t = 0.6·S_t + 0.4·V_t (simple but misses interactions)
- Nonlinear P_t = (1 - exp(-S_t)) × |tanh(V_t)| captures:
  - **Saturation:** High drift creates urgency that doesn't grow indefinitely
  - **Interaction:** Pressure depends on BOTH drift AND velocity
  - **Bounded behavior:** Result stays in [0, 1]

### 4. Fixed Baseline After Warmup
Why not rolling baseline?
- **Prevents absorption of degradation:** Once system fails, baseline shouldn't adapt
- **Clear reference point:** Baseline represents true "normal"
- **Simplified logic:** One baseline, not two competing signals
- Rolling baseline available if needed (can be enabled via configuration)

### 5. Stateless Update (Optional History Carryover)
Why streaming-safe design?
- Works with live data streams (one frame at a time)
- No requirement to keep full history in memory
- Optional: can save `(prev_drift, prev_velocity)` for next frame
- Suitable for edge deployment and real-time systems

---

## Mathematical Properties

### Normalization
All pipeline outputs are bounded:
- S_t ∈ [0, 1] (normalized Frobenius difference)
- V_t ∈ ℝ but bounded contribution via tanh to [-1, 1]
- P_t ∈ [0, 1] (product of bounded terms)
- I_t ∈ [0, 1] (weighted sum of bounded terms)
- Confidence ∈ [0, 1]

### Monotonicity
- As I_t increases, regime severity increases monotonically
- Regime transitions at fixed thresholds (no hysteresis)
- Urgency consistent with regime severity

### Stability
- Regularized covariance inversion: prevents singularity issues
- Forward-fill for missing data: no crashes on NaN
- Velocity bounded via tanh: no overflow from rapid changes
- All divisions protected by ε term

---

## Integration Points

### Replacing Previous Subsystems
1. **stability_energy.py** → Baseline model + gradient norm
2. **drift.py (DriftStateMachine)** → Structural drift + regime classification
3. **alignment.py (StructuralEngine)** → Consolidated into SII pipeline
4. **Various analytics** → Derive from I_t instead of independent scores

### For UI/API
- Draw **regime bar** using `regime` and `instability_score`
- Color threshold at 0.30 (STABLE→TRANSITION), 0.65 (TRANSITION→UNSTABLE), 0.85 (UNSTABLE→LOCK_IN)
- Show **velocity history** for trend visualization
- Use **urgency** for alert level (affects sound, color intensity, etc.)
- Use **gradient_norm** for directional indicators

### For Downstream Decision Logic
- **Discrete regime changes** trigger investigation steps
- **Velocity spikes** trigger fast-path responses
- **Confidence growth** increases weight of recommendations
- **Recovery alignment** positive indicates self-healing

---

## Configuration & Tuning

### Default Weights
```python
DEFAULT_DRIFT_WEIGHT = 0.40      # Structural changes (largest)
DEFAULT_VELOCITY_WEIGHT = 0.35   # Speed of change
DEFAULT_PRESSURE_WEIGHT = 0.25   # Interaction effects
```

These can be adjusted per-system if needed, but should sum to 1.0.

### Thresholds
```python
STABLE_THRESHOLD = 0.30          # Normal operation
TRANSITION_THRESHOLD = 0.65      # Active change
UNSTABLE_THRESHOLD = 0.85        # High risk
LOCK_IN_THRESHOLD = 0.95         # Critical
```

Thresholds are fixed (no quantile calibration), providing predictable behavior.

### Windows
```python
baseline_window = 50             # Samples for initial baseline
recent_window = 12               # Samples for rolling covariance
```

Larger windows = more stable but slower response. Smaller windows = sensitive but noisier.

---

## Usage Example

```python
from neraium_core.sii_engine_unified import SIIEngine

# Initialize engine
engine = SIIEngine(
    baseline_window=50,
    recent_window=12,
    drift_weight=0.40,
    velocity_weight=0.35,
    pressure_weight=0.25,
)

# Phase 1: Warmup (fit baseline)
for i, frame in enumerate(baseline_frames):
    output = engine.update(frame, timestamp=float(i))
    # output.regime == "WARMUP" during this phase
    # After baseline_window frames, baseline_ready becomes True

# Phase 2: Online operation
for i, frame in enumerate(stream_frames):
    output = engine.update(frame, timestamp=float(start + i))
    
    # Check instability score (all outputs derive from this)
    if output.urgency == "CRITICAL":
        trigger_emergency_response()
    elif output.regime == "UNSTABLE":
        increase_monitoring()
    
    # Use detailed metrics for UI
    update_gauge(output.instability_score)
    update_velocity_plot(output.velocity_history)
    update_regime_indicator(output.regime)
```

---

## Testing & Validation

The unified engine includes:
- **20+ unit tests** (test_sii_engine_unified.py)
- **Validation script** (validate_sii_engine.py)
- Tests cover:
  - Baseline fitting with missing data
  - Drift computation and monotonicity
  - Velocity accumulation and direction
  - Pressure dynamics
  - Score composition and normalization
  - Regime transitions
  - Urgency mapping
  - State persistence
  - Edge cases (all NaN, singular covariance, etc.)

---

## Summary

The SII Engine provides a **single, unified mathematical framework** for system instability intelligence:

1. **One pipeline** from raw input to actionable output
2. **One score** (I_t) that all decisions derive from
3. **No duplicate logic** across components
4. **No UI-specific code** in the engine layer
5. **Production-ready** with proper handling of edge cases
6. **Streaming-safe** for real-time and edge deployment
7. **Mathematically grounded** with clear equations and properties

This consolidation replaces a fragmented system with a coherent, maintainable architecture.
