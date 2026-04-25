# System Instability Intelligence (SII) Engine
## Formal Mathematical Specification

**Version**: 1.0  
**Status**: PRODUCTION  
**Authority**: Single source of truth for all instability analysis  
**Date**: 2026-04-25

---

## EXECUTIVE SUMMARY

The SII Engine computes a single unified instability score **I_t** from which all downstream decisions derive:
- **regime** classification (STABLE, TRANSITION, UNSTABLE, LOCK_IN)
- **urgency** levels (NOMINAL, WATCH, ALERT, CRITICAL)
- **decision** narratives and operational guidance

There is **EXACTLY ONE** instability score. No alternative scoring methods are permitted in production.

---

## 1. MATHEMATICAL DEFINITION

### 1.1 Inputs

Let **x_t ∈ ℝ^d** be the sensor vector at time t, where d is the number of sensors.

Assume:
- **μ₀ ∈ ℝ^d** is the baseline mean (computed from first B samples)
- **Σ₀ ∈ ℝ^(d×d)** is the baseline covariance (computed from first B samples, regularized)
- **B** is the baseline window (default: 50 samples)

### 1.2 Core Components (Computed at Every Frame t)

#### A. Structural Drift: S_t

**Definition**: Frobenius norm of covariance deformation.

Compute rolling covariance Σ_t from the most recent W samples:
```
Σ_t = cov(x_{t-W+1}, ..., x_t)  [normalized]
```

where W is the recent window (default: 12 samples).

Then:
```
S_t = ||Σ_t - Σ₀||_F / (||Σ₀||_F + ε)
```

**Properties**:
- S_t ∈ [0, 1] (normalized by baseline norm)
- S_t = 0 when covariance matches baseline
- S_t → 1 as structure severely deforms
- **ε** = 1e-9 (numerical stability)

**Interpretation**: Measures how much the correlation structure has deformed from baseline.

---

#### B. Drift Velocity: V_t

**Definition**: Rate of change of structural drift.

```
V_t = dS_t/dt ≈ (S_t - S_{t-1}) / Δt
```

where Δt is the time step (≥ ε to avoid division by zero).

**Properties**:
- V_t ∈ ℝ (unbounded, typically |V_t| < 0.5)
- V_t > 0: deformation accelerating
- V_t < 0: deformation stabilizing
- V_t ≈ 0: structure static

**Interpretation**: Indicates how fast the system is changing. High velocity suggests rapid transition.

---

#### C. Transition Pressure: P_t

**Definition**: Combined effect of drift magnitude and velocity.

```
P_t = (1 - exp(-S_t)) × |tanh(V_t)|
```

**Properties**:
- P_t ∈ [0, 1]
- exp(-S_t) creates nonlinear urgency: as drift increases, the factor increases
- tanh(V_t) bounds velocity contribution to [-1, 1]
- |·| ensures pressure is always ≥ 0

**Interpretation**: Combines drift magnitude (how far from baseline) with velocity (how fast). Useful for detecting rapid transitions.

---

#### D. Recovery Alignment: R_t [DIAGNOSTIC ONLY]

**Definition**: Cosine similarity between system velocity and recovery force.

```
R_t = cos(velocity_vector, -gradient_vector)
     = (v · (-∇E)) / (||v|| × ||∇||)
```

where:
- velocity_vector = x_t - x_{t-1}
- gradient = 2 × Σ₀^(-1) × (x_t - μ₀)  [energy gradient]
- recovery_force = -gradient  [direction toward baseline]

**Properties**:
- R_t ∈ [-1, 1]
- R_t > 0.7: system moving toward stability
- R_t ≈ 0: system velocity orthogonal to recovery
- R_t < -0.5: system moving away from stability

**Interpretation**: Diagnostic signal indicating whether the system is self-correcting. Does NOT influence instability score or regime.

---

### 1.3 Unified Instability Score: I_t

**THE CANONICAL EQUATION**:

```
I_t = α × S_t + β × |tanh(V_t)| + γ × P_t
```

where:
- α = 0.40 / (α + β + γ)  [drift weight, normalized]
- β = 0.35 / (α + β + γ)  [velocity weight, normalized]
- γ = 0.25 / (α + β + γ)  [pressure weight, normalized]
- Final result: I_t ∈ [0, 1]

**Properties**:
- I_t is the **SINGLE SOURCE OF TRUTH** for system state
- **IMMUTABLE**: Once computed by SIIEngine, no modification is permitted
- All regime and urgency decisions derive ONLY from I_t (and velocity for urgency)
- No parallel scoring methods are allowed

**Weight Justification**:
- 40%: Drift captures static deformation (correlation structure change)
- 35%: Velocity captures dynamics (how fast system is changing)
- 25%: Pressure amplifies rapid transitions (multiplicative effect)

---

### 1.4 Regime Classification

**Definition**: Deterministic mapping from instability score to regime.

```
regime(I_t) = {
    "STABLE"      if I_t ≤ 0.30
    "TRANSITION"  if 0.30 < I_t ≤ 0.65
    "UNSTABLE"    if 0.65 < I_t ≤ 0.85
    "LOCK_IN"     if I_t > 0.85
}
```

**Threshold Rationale**:
- **0.30**: First meaningful deviation from baseline (5-sigma confidence interval)
- **0.65**: Transition zone where corrective action can still be effective
- **0.85**: Critical deformation; failure imminent
- **0.95+**: Locked-in failure state (recovery not possible)

**Constraint**: 
- Regime MUST be computed by `SIIEngine.classify_regime(I_t)` ONLY
- No other module may assign regime

---

### 1.5 Urgency Mapping

**Definition**: Mapping from (regime, velocity) to urgency level.

```
urgency(regime, V_t) = {
    "CRITICAL"  if regime == "LOCK_IN"
    "ALERT"     if (regime == "UNSTABLE") 
                   OR (regime == "TRANSITION" AND |V_t| > 0.1)
    "WATCH"     if (regime == "TRANSITION" AND |V_t| ≤ 0.1)
                   OR (regime == "STABLE" AND |V_t| > 0.05)
    "NOMINAL"   if regime == "STABLE" AND |V_t| ≤ 0.05
}
```

**Interpretation**:
- **CRITICAL**: System failure imminent. Activate emergency procedures.
- **ALERT**: System at high risk. Immediate corrective action required.
- **WATCH**: System changing. Close monitoring and investigation required.
- **NOMINAL**: System stable. Continue routine operations.

**Constraint**: 
- Urgency MUST be computed by `SIIEngine.compute_urgency(regime, V_t)` ONLY
- No other module may assign urgency

---

## 2. PIPELINE ARCHITECTURE

### 2.1 Data Flow

```
┌─────────────────────┐
│  Sensor Vector x_t  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│  SIIEngine.update(x_t, time)    │
└─────────┬───────────────────────┘
          │
          ├─→ Compute Σ_t (covariance)
          │
          ├─→ Compute S_t (drift)
          │
          ├─→ Compute V_t (velocity)
          │
          ├─→ Compute P_t (pressure)
          │
          ├─→ Compute R_t (recovery) [diagnostic]
          │
          ├─→ I_t = α×S_t + β×|tanh(V_t)| + γ×P_t
          │
          ├─→ regime = classify_regime(I_t)
          │
          └─→ urgency = compute_urgency(regime, V_t)
          
          ▼
┌──────────────────────────────────┐
│  SIIEngineOutput                 │
│  ├─ timestamp                    │
│  ├─ instability_score (I_t)     │
│  ├─ structural_drift (S_t)      │
│  ├─ drift_velocity (V_t)        │
│  ├─ transition_pressure (P_t)   │
│  ├─ recovery_alignment (R_t)    │
│  ├─ regime                       │
│  ├─ urgency                      │
│  ├─ confidence                   │
│  └─ histories                    │
└──────────────────────────────────┘
           │
           ▼ (NO MODIFICATION)
┌──────────────────────────────────┐
│  SIIEngineAdapter                │
│  ├─ Wraps SIIEngine              │
│  ├─ Per-asset state management   │
│  └─ Exposes UnifiedSystemState   │
└──────────────────────────────────┘
           │
           ▼ (CONSUME ONLY)
┌──────────────────────────────────┐
│  Downstream Consumers             │
│  ├─ EvidenceBuilder               │
│  ├─ DecisionNarrativeEngine       │
│  ├─ API Responses                 │
│  ├─ UI Components                 │
│  └─ Alert Service                 │
└──────────────────────────────────┘
```

### 2.2 Constraints (ENFORCED)

**C1**: SIIEngine is IMMUTABLE  
- Once `update()` returns, outputs cannot be modified
- Any modification is a violation of mathematical integrity

**C2**: No Parallel Scoring  
- Only I_t may be used for state determination
- All other scoring functions (composite_instability_score_normalized, etc.) are DEPRECATED
- Legacy code must be removed or isolated to archive

**C3**: Adapter Does Not Compute  
- SIIEngineAdapter wraps, it does not modify
- It traces inputs to SIIEngine, outputs to consumers
- No business logic in adapter

**C4**: Consumers Only Read  
- EvidenceBuilder reads (regime, urgency, I_t, histories)
- DecisionNarrativeEngine reads (regime, urgency, velocity)
- UI reads complete state
- None compute (regime, urgency, I_t)

**C5**: No Thresholds Outside SIIEngine  
- No module may have independent instability thresholds
- No module may classify regime
- No module may assign urgency

---

## 3. BASELINE FITTING

### 3.1 Initial Baseline (Warmup Phase)

On engine initialization:
- Accumulate first B samples (default: B=50)
- Compute μ₀ = mean(x_1, ..., x_B)
- Compute Σ₀ = cov(x_1, ..., x_B)
- Apply regularization: Σ₀ ← Σ₀ + λI where λ = 1e-4
- Compute Σ₀^(-1) via regularized pseudo-inverse

**Output during warmup**: 
```
regime = "WARMUP"
urgency = "NOMINAL"
I_t = 0.0 (neutral)
confidence = 0.0
```

### 3.2 Baseline Locking

After first B samples:
- **Baseline is LOCKED** — never updated
- Rolling window moves forward, baseline remains fixed
- Ensures reproducibility and prevents "drift creep"

**Rationale**: 
- Adaptive baselines can absorb anomalies into "new normal"
- Fixed baseline is auditable and reproducible
- True baseline shifts can be handled via explicit re-baseline (admin function)

---

## 4. CONFIDENCE METRIC

The confidence score C_t indicates reliability of I_t:

```
C_t = history_factor × (1.0 - volatility_penalty)
```

where:
- history_factor = min(frame_count / (2×B), 1.0)
- volatility_penalty = min(std(V_t over last 5 frames), 0.3)

**Interpretation**:
- C_t = 0.0 during warmup (insufficient history)
- C_t → 1.0 as history accumulates and volatility stabilizes
- C_t ≤ 0.7 indicates high velocity (low confidence in regime)
- C_t ≥ 0.85 indicates stable regime (high confidence)

---

## 5. PROHIBITED LOGIC

The following are **EXPLICITLY FORBIDDEN** in production:

1. **Independent regime computation**:
   ```python
   # FORBIDDEN:
   regime = "UNSTABLE" if subsystem_score > 0.7 else "STABLE"
   ```

2. **Parallel instability scores**:
   ```python
   # FORBIDDEN:
   composite_score = 0.3×drift + 0.4×entropy + 0.3×spectral
   ```

3. **Threshold-based urgency**:
   ```python
   # FORBIDDEN:
   urgency = "ALERT" if instability > 1.5 else "NOMINAL"
   ```

4. **Regime libraries or prototypes**:
   ```python
   # FORBIDDEN:
   regime = match_regime_prototype(signature, regime_library)
   ```

5. **Subsystem-specific decisions**:
   ```python
   # FORBIDDEN:
   if hvac_instability > 0.8: escalate_hvac_team()
   ```

Any violation of these rules is a **DEFECT** requiring immediate remediation.

---

## 6. VALIDATION REQUIREMENTS

### 6.1 FD004 Validation

Run all methods on FD004 dataset (all units):

**Methods**:
1. SIIEngine (I_t, regime, urgency)
2. Threshold-based (fixed threshold on instability)
3. Z-score anomaly (statistical deviations)
4. PCA reconstruction (unsupervised outliers)

**Metrics per method**:
- detection_cycle (first alert)
- lead_time = failure_cycle - detection_cycle
- mean lead time (across all units)
- median lead time
- std dev of lead time
- detection_rate (% units detected before failure)

**Success Criterion**:
- SII mean lead time > other methods (detects earlier)
- SII detection_rate ≥ 95%
- SII lead time std dev < other methods (more consistent)

### 6.2 Consistency Checks

**At runtime**:
- Verify I_t ∈ [0, 1]
- Verify regime ∈ {STABLE, TRANSITION, UNSTABLE, LOCK_IN, WARMUP}
- Verify urgency ∈ {NOMINAL, WATCH, ALERT, CRITICAL}
- Verify regime matches I_t threshold boundaries
- Verify urgency matches regime+velocity mapping

**On state changes**:
- regime transitions are logged (with cycle, I_t, V_t)
- urgency transitions are logged
- no contradictory states (e.g., STABLE with CRITICAL urgency)

### 6.3 Audit Trail

Each update produces:
```
{
  timestamp: t,
  cycle: n,
  instability_score: I_t,
  structural_drift: S_t,
  drift_velocity: V_t,
  transition_pressure: P_t,
  recovery_alignment: R_t,
  regime: regime_t,
  urgency: urgency_t,
  confidence: C_t,
  reason: "transition from STABLE to TRANSITION (I_t=0.32)" [optional]
}
```

---

## 7. MATHEMATICAL CORRECTNESS CHECKLIST

- [ ] I_t defined as weighted sum of S_t, V_t, P_t
- [ ] All weights normalize to 1.0
- [ ] I_t ∈ [0, 1] (clipped)
- [ ] regime(I_t) is deterministic and exhaustive
- [ ] urgency(regime, V_t) is deterministic and exhaustive
- [ ] R_t is computed but NOT included in I_t
- [ ] S_t, V_t, P_t are mathematically consistent
- [ ] No parallel scoring methods exist
- [ ] No independent regime assignment logic exists
- [ ] No independent urgency assignment logic exists
- [ ] Baseline is locked after warmup
- [ ] Confidence metric is defined and tracked
- [ ] All outputs trace back to I_t

---

## 8. IMPLEMENTATION RULES

### Rule 1: Single Equation
The equation I_t = α×S_t + β×|tanh(V_t)| + γ×P_t is the ONLY instability computation in the system.

### Rule 2: Immutable Output
SIIEngineOutput is immutable. No component may modify I_t, regime, or urgency after creation.

### Rule 3: Deterministic Classification
regime(I_t) and urgency(regime, V_t) are pure functions with no side effects or external dependencies.

### Rule 4: No Exceptions
Any code that computes instability, regime, or urgency outside SIIEngine is a defect.

### Rule 5: Audit Everything
Every state change must be logged with (timestamp, cycle, I_t, regime, urgency, V_t, reason).

---

## 9. WHITE PAPER CLAIM

**Formal Claim**:

"The System Instability Intelligence Engine detects structural degradation via a unified instability metric I_t derived from covariance drift, drift velocity, and transition pressure. On the FD004 turbofan dataset, SII achieves [X] cycles earlier detection compared to threshold-based methods, with [Y]% detection rate and [Z] cycles median lead time before failure."

---

## 10. SIGN-OFF

This specification is the definitive source for all SII implementations.

Any deviation requires explicit justification and architectural review.

**Version**: 1.0  
**Effective Date**: 2026-04-25  
**Review Date**: 2026-05-25  
**Authority**: System Architecture
