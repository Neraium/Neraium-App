# Neraium SII Engine Architecture

## Core Mathematical Foundation

The Neraium Advanced SII Engine is built on a single, unified 5-factor core formula that serves as the source of truth for all detection capabilities:

```
S(t) = w₁·D_M(t) + w₂·D_cov(t) + w₃·V_d(t) + w₄·P_t(t) + w₅·κ(t)
```

### The Five Core Factors

1. **D_M(t) - Mahalanobis Distance** (w₁ = 0.25)
   - **Purpose**: How far the current observation is from the baseline state
   - **Computation**: `D_M = √((x_t - μ₀)ᵀ Σ₀⁻¹ (x_t - μ₀))`
   - **Range**: [0, 1] (clipped)
   - **Interpretation**: High D_M indicates novel or anomalous operating conditions

2. **D_cov(t) - Covariance Drift** (w₂ = 0.30)
   - **Purpose**: Structural breakdown of the correlation matrix
   - **Computation**: `D_cov = ||Σ_t - Σ₀||_F / (||Σ₀||_F + ε)` (Frobenius norm)
   - **Range**: [0, 1]
   - **Interpretation**: Measures how much the sensor correlations have changed from baseline

3. **V_d(t) - Drift Velocity** (w₃ = 0.20)
   - **Purpose**: Rate of degradation - how fast the system is destabilizing
   - **Computation**: `V_d = dD_cov/dt` (finite difference)
   - **Range**: Unbounded (bounded via tanh for score)
   - **Interpretation**: Rapid velocity indicates accelerating failure

4. **P_t(t) - Transition Pressure** (w₄ = 0.15)
   - **Purpose**: Combined effect of drift magnitude and velocity indicating state shift likelihood
   - **Computation**: `P_t = (1 - e^(-D_cov)) × |tanh(V_d)|`
   - **Range**: [0, 1]
   - **Interpretation**: High pressure means the system is under active deformation stress

5. **κ(t) - Curvature** (w₅ = 0.10)
   - **Purpose**: Second derivative of drift - acceleration of the destabilization rate
   - **Computation**: `κ = |dV_d/dt|` (absolute value of velocity derivative)
   - **Range**: [0, 1]
   - **Interpretation**: Increasing curvature indicates the degradation process itself is accelerating

### Normalized Weights

The weights normalize to sum to 1.0:
- w₁ + w₂ + w₃ + w₄ + w₅ = 1.0
- Default weights: [0.25, 0.30, 0.20, 0.15, 0.10]

## Architecture Layers

### Layer 1: Unified Engine (`sii_engine_unified.py`)

The unified engine computes the 5-factor score as its core responsibility:

```python
class SIIEngine:
    def update(self, x_t: np.ndarray, timestamp: float) -> SIIEngineOutput:
        # Stage 1: Covariance
        cov_t = self.compute_covariance(sensor_history)
        
        # Stage 2: Structural drift D_cov(t)
        D_cov = self.compute_structural_drift(cov_t)
        
        # Stage 3: Velocity V_d(t)
        V_d = self.compute_velocity(D_cov, timestamp)
        
        # Stage 3.5: Mahalanobis distance D_M(t)
        D_M = self.compute_mahalanobis_distance(x_t)
        
        # Stage 4: Transition pressure P_t(t)
        P_t = self.compute_transition_pressure(D_cov, V_d)
        
        # Stage 4.5: Curvature κ(t)
        κ = self.compute_curvature(V_d, timestamp)
        
        # Stage 5: 5-factor core score
        S(t) = w₁·D_M + w₂·D_cov + w₃·V_d + w₄·P_t + w₅·κ
        
        # Regime classification from S(t)
        regime = classify_regime(S(t))
        
        return SIIEngineOutput(
            instability_score=S(t),
            structural_drift=D_cov,
            drift_velocity=V_d,
            transition_pressure=P_t,
            mahalanobis_distance=D_M,
            curvature=κ,
            regime=regime,
            ...
        )
```

### Layer 2: Advanced Engine (`sii_engine_advanced.py`)

The advanced engine derives 15 interpretable metrics from the 5 core factors. No independent detection methods—all flow from the core formula:

#### Derived from D_M (Mahalanobis Distance)
- **Novelty Detection**: High D_M → novel sensor pattern
  - Combined with Isolation Forest for multi-modal detection
  - Score ranges [0, 1], flags if > 0.4

#### Derived from D_cov (Covariance Drift)
- **Multi-Scale Drift Analysis**: D_cov computed over different time windows
  - Fast (12-cycle): immediate shocks
  - Medium (120-cycle): intermediate degradation
  - Slow (1200-cycle): long-term drift
- **Sensor Contribution**: Which sensors drive D_cov changes?
  - SHAP-style attribution: drift_with_sensor - drift_without_sensor

#### Derived from V_d (Drift Velocity)
- **RUL Estimation**: Linear extrapolation to failure threshold
  - `cycles_to_failure = (threshold - S(t)) / V_d`
  - Confidence bounds: ±30%
  - Mode classification from velocity patterns

#### Derived from κ (Curvature)
- **Early Warning Signals**: κ spikes indicate acceleration
  - Velocity_acceleration: increasing |dV_d/dt|
  - Volatility increase: instability_score σ trending up
  - Cycles until transition estimated

#### Derived from P_t and Combinations
- **Degradation Mode Classification**: Pattern analysis
  - NORMAL: V_d ≈ 0
  - LINEAR_DRIFT: constant velocity
  - ACCELERATING_DRIFT: κ > σ(V_d)
  - PERIODIC_OSCILLATION: σ(V_d) >> mean(V_d)
  - SUDDEN_SPIKE: max(V_d) - min(V_d) >> mean(V_d)

- **Ensemble Agreement**: Do all 5 factors agree on instability?
  - Each factor checked against threshold
  - Score = (# factors signaling) / 5
  - Range [0.0, 1.0]

- **Operating Condition Adjustment**: Linear scaling by temp/load/speed
  
- **Uncertainty Quantification**: Bayesian confidence intervals
  - From sensor noise estimate + score volatility
  - 95% CI: ±1.96×uncertainty

- **Cost-Benefit Analysis**: Maintenance vs. failure costs
  - RUL used to estimate failure risk
  - Probability of failure within 30 cycles

- **Change Point Detection**: CUSUM-based regime shift detection
  - Tracks when degradation started

- **Sensor Diagnostics**: Per-sensor health tracking
  - Deviation from baseline (σ units)
  - Drift rate (change per cycle)
  - Anomaly flags (>3σ or faulty)
  - Top 3 contributing sensors

## Regime Classification

All regimes derive from a single metric: S(t)

| Regime | S(t) Range | Interpretation |
|--------|-----------|-----------------|
| WARMUP | N/A | Baseline still being established |
| STABLE | S(t) ≤ 0.30 | Normal operation |
| TRANSITION | 0.30 < S(t) ≤ 0.65 | System changing, monitor closely |
| UNSTABLE | 0.65 < S(t) ≤ 0.85 | High risk, prepare for action |
| LOCK_IN | S(t) > 0.85 | Critical state, failure imminent |

## Code Organization

```
neraium_core/
├── sii_engine_unified.py
│   ├── SIIEngine (base class)
│   ├── SIIEngineOutput (5-factor output)
│   └── BaselineProfile
│
└── sii_engine_advanced.py
    ├── AdvancedSIIEngine (inherits from SIIEngine)
    ├── AdvancedSIIOutput (extends with 15 derived metrics)
    ├── DegradationMode (enum)
    ├── EarlyWarningSignal
    ├── RULEstimate
    └── SensorDiagnostics

tools/
├── cmapss_runner.py (advanced validation)
├── cmapss_unified_runner.py (core validation)
├── wur_greenhouse_runner.py (unsupervised validation)
└── run_mode (examples)
```

## Key Design Principles

1. **Mathematical Purity**
   - Single core formula is source of truth
   - No redundant or conflicting detection methods
   - All metrics derive from the 5 factors

2. **Interpretability**
   - Each factor has clear physical meaning
   - Advanced metrics trace back to core factors
   - No black-box voting or ensemble averaging

3. **Efficiency**
   - Core computation O(d²) per frame (covariance)
   - Advanced metrics O(d) per frame (mostly linear)
   - No expensive feature engineering

4. **Robustness**
   - Regularized inverse covariance (avoids singularity)
   - Forward-fill for missing values
   - Adaptive baseline for short data streams

5. **Testability**
   - Each factor computable independently
   - Output always includes all components
   - Audit trail for verification

## Usage Example

```python
from neraium_core.sii_engine_advanced import AdvancedSIIEngine

# Initialize with 5-factor weights
engine = AdvancedSIIEngine(
    baseline_window=50,
    system_type="bearing"
)

# Fit baseline (stable operation period)
engine.fit_baseline(baseline_data)

# Process sensor streams
for x_t, timestamp in sensor_stream:
    output = engine.update(x_t, timestamp)
    
    # Access core factors
    print(f"Core factors: D_M={output.mahalanobis_distance:.3f}, "
          f"D_cov={output.structural_drift:.3f}, "
          f"V_d={output.drift_velocity:.3f}, "
          f"P_t={output.transition_pressure:.3f}, "
          f"κ={output.curvature:.3f}")
    
    # Access unified score
    print(f"S(t) = {output.instability_score:.3f}, Regime: {output.regime}")
    
    # Access derived metrics
    print(f"RUL: {output.rul.median_cycles if output.rul else 'N/A'} cycles")
    print(f"Degradation mode: {output.degradation_mode.value}")
    print(f"Ensemble agreement: {output.ensemble_agreement:.2f}")
```

## Validation Approaches

### Strict Mode (Baseline)
- Uses only core 5-factor formula
- Conservative thresholds
- Production-grade confidence

### Experimental Mode
- Adds validation strength scoring
- Tracks gained detections vs baseline
- Research layer for advanced metrics

### Unsupervised Mode (Greenhouse)
- No failure labels needed
- Tracks operational metrics
- Stability distribution analysis

## Performance Characteristics

- **Baseline window**: 50 samples (configurable)
- **Memory**: ~1 MB per unit (rolling buffers)
- **Speed**: ~1 ms per frame on modern CPU
- **Startup latency**: 50 frames (warmup period)
- **Max detection delay**: 5-10 cycles (after clear degradation)

## Future Extensions

The 5-factor core enables straightforward extensions:

1. **Multi-phase learning**: Different w₁-w₅ weights per degradation phase
2. **Sensor weighting**: D_cov computed per sensor group
3. **Failure mode adaptation**: Different thresholds per failure class
4. **Recursive Bayesian filtering**: Kalman filter for state estimation
5. **Predictive maintenance optimization**: Cost-benefit under uncertainty

All maintain the same core formula—only parameters and the baseline change.
