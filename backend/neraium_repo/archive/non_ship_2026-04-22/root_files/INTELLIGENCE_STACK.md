# Neraium Intelligence Stack

## Overview

The Neraium Intelligence Stack is a layered, mathematically interpretable architecture for online detection of degradation and state transitions in multivariate sensor systems. It combines structural, relational, and temporal evidence through a causal, non-leaky inference pipeline.

Unlike conventional anomaly detection (which flags deviation from an arbitrary baseline), the Intelligence Stack detects **structural state changes** — discontinuous shifts in the system's intrinsic geometry, correlations, and trajectory properties.

**Key Property**: No future data is used at any layer. All computation is online-safe.

---

## Layered Architecture

### Layer 1: Structural Geometry

**Purpose**: Detect changes in the *location* and *shape* of the system state cloud.

**Signals**:
- **Mahalanobis Distance**: Shift in mean position relative to reference precision (inverse covariance)
- **Covariance Drift**: Change in the volume and orientation of the state cloud (Frobenius norm)
- **Correlation Drift**: Breakdown of pairwise sensor relationships (cross-sensor structure)

**Math**:
```
mahalanobis[t] = sqrt((x[t] - μ_ref)^T Σ_ref^{-1} (x[t] - μ_ref))

cov_drift[t] = || Σ_recent(t) - Σ_ref ||_F

corr_drift[t] = || R_recent(t) - R_ref ||_F
```

Where μ_ref, Σ_ref, R_ref are frozen reference statistics from the healthy (early) segment.

**Computation**: Rolling window (typically 15 cycles) to estimate recent covariance and correlation without future leakage.

**Interpretation**: Positive drift indicates the system's operating point or intrinsic correlations are changing.

---

### Layer 2: Relational Instability

**Purpose**: Detect when sensor relationships *break down* or become unreliable.

**Signals**:
- **Rolling Correlation Breakdown**: Abrupt loss of correlation structure between pairs of sensors
- **Dependency Fracture**: Failure of normally-coupled sensor dynamics to remain coupled

**Math**:
```
rel_instability[t] = detect_correlation_change(window[t-w:t])
```

Uses correlation matrix comparison: if Frobenius distance exceeds threshold over consecutive windows, flag as breakdown.

**Interpretation**: Correlation breakdown often precedes loss of redundancy; indicates system topology change or failure initiation.

---

### Layer 3: Trajectory Dynamics

**Purpose**: Detect changes in *motion* through state space — velocity and curvature shifts.

**Signals**:
- **EMA Smoothing**: Stabilizes noisy structural signals; reduces transient false alarms
- **Velocity**: First derivative of smoothed drift score (rate of change)
- **Acceleration / Curvature**: Second derivative (rapid escalation); indicates transition onset
- **Change-Point Detection**: CUSUM-based flagging of sustained elevation

**Math**:
```
drift_ema[t] = α * drift[t] + (1 - α) * drift_ema[t-1]     (α ≈ 0.2)

velocity[t] = drift_ema[t] - drift_ema[t-1]

acceleration[t] = velocity[t] - velocity[t-1]
```

**Interpretation**: Acceleration spikes indicate regime transitions; persistent elevation indicates sustained degradation.

---

### Layer 4: Regime Transition Modeling

**Purpose**: Assign latent regime labels and track state transitions with confidence and persistence metrics.

**Signals**:
- **Regime Assignment**: Online clustering of structural feature vectors
- **Transition Confidence**: Strength of evidence for a state change
- **Persistence / Dwell Time**: How long the system has been in current regime
- **Transition Probability**: Likelihood of further transitions

**Math**:

Feature vector at cycle t:
```
φ[t] = [mahal_distance[t], cov_drift[t], corr_drift[t]]
```

Online regime assignment (no future leakage):
```
regime[t] = argmin_k || φ[t] - centroid_k[t-1] ||
```

Transition detection:
```
transition_score[t] = ||φ[t] - φ[t-1]|| / (moving_std(φ) + ε)
transition_detected[t] = transition_score[t] > 1.5   (or learned threshold)
```

Persistence counter:
```
persistence[t] = persistence[t-1] + 1  if regime[t] == regime[t-1]
                = 1                       if regime[t] != regime[t-1]
```

**Interpretation**:
- `regime_id`: Current latent state (0=healthy, 1=early degradation, 2=advanced, etc.)
- `transition_detected`: Boolean flag for regime change events
- `transition_score`: Normalized distance indicating strength of evidence
- `regime_persistence`: Cycles spent in current regime; high persistence = high confidence in regime assignment

---

### Layer 5: Evidence Fusion

**Purpose**: Combine evidence from all four layers with confirmation gating and interpretable output.

**Signals Combined**:
1. Structural geometry evidence (layers 1)
2. Relational instability evidence (layer 2)
3. Trajectory dynamics evidence (layer 3)
4. Regime transition evidence (layer 4)

**Confirmation Gating**:
- Require at least 2 independent signals to exceed activation threshold
- At least 1 must be *structural* (geometry, instability, or regime change)
- Prevents false alarms from single noisy detector

**Persistent Warning State**:
- Once confirmed, warning state locks in; no oscillation
- Exit only after evidence drops and persists below exit threshold
- Prevents fluttering and ensures actionable lead times

**Interpretable Explanation**:
```
warning_fired = {
    "timestamp": cycle_index,
    "active_layers": [layer1, layer3, layer4],  # which layers exceeded threshold
    "dominant_signal": "regime_transition",      # strongest evidence
    "structural_confidence": 0.87,               # [0,1] geometry evidence
    "relational_confidence": 0.45,               # [0,1] instability evidence
    "trajectory_confidence": 0.92,               # [0,1] dynamics evidence
    "regime_transition_score": 2.31,             # normalized transition strength
    "confirmation_passed": true,                 # ≥2 independent signals
}
```

---

## Computational Pipeline

### Training (Offline)

1. Load healthy segment (first 35% of unit lifecycle)
2. Compute and **freeze** reference statistics:
   - Mean, covariance, correlation
   - Precision matrix (inverse covariance)
3. Compute reference velocity/acceleration baseline

### Scoring (Online, Per Cycle)

1. **Structural Geometry**: Compute mahal, cov_drift, corr_drift → drift score
2. **EMA Smoothing**: Apply exponential moving average
3. **Trajectory**: Compute velocity, acceleration, CUSUM
4. **Relational Instability**: Check for correlation breakdown
5. **Regime Transition**: Update online regime assignment, compute transition scores
6. **Evidence Fusion**: Combine all signals with confirmation gating
7. **Warning Logic**: Check if confirmed and not already in warning state; lock state if confirmed

**Time Complexity**: O(s²) per cycle where s = number of sensors (covariance updates)  
**Space Complexity**: O(s²) for reference and recent covariance matrices

---

## Differences from Classical Anomaly Detection

| Classical AD | Neraium Intelligence Stack |
|---|---|
| Detects deviation from centroid | Detects structural state transitions |
| Single global threshold | Layer-specific thresholds + confirmation gating |
| May oscillate on boundary | Persistent warning state prevents fluttering |
| Black-box ML ensembles | Interpretable math (linear algebra, statistics) |
| Often uses future data (offline) | Purely causal, online-safe pipeline |
| Ambiguous alert (what changed?) | Interpretable: which layers triggered why |

---

## Design Principles

1. **Causality**: No future data at any stage
2. **Interpretability**: Each component produces human-readable outputs
3. **Trustworthiness**: Conservative confirmation gating; multiple independent signals
4. **Online-Safety**: Streaming-friendly; no model retraining required
5. **Production-Grade**: Mathematically grounded; avoids opaque deep learning
6. **Dimensionality**: Works on raw high-dimensional sensor data without feature engineering

---

## Configuration & Tuning

### Key Hyperparameters

- `healthy_fraction` (0.25–0.45): Fraction of lifecycle used to freeze reference statistics
- `ema_alpha` (0.15–0.30): EMA smoothing rate; smaller = smoother
- `fusion_activation_floor` (0.1–0.3): Threshold above which a component is counted as "active"
- `regime_transition_threshold` (1.5–2.5): Z-score-like threshold for regime change detection
- `warning_exit_threshold_ratio` (0.80–0.90): Multiple of entry threshold for exit

All tuning is transparent and documented. No hyperparameter search required for new domains.

---

## Future Extensions

- **Adaptive Reference**: Slow-learning reference update in truly non-stationary environments (with leak protection)
- **Hierarchical Regimes**: Coarse (health/failure) and fine-grained (stage) regime hierarchies
- **Cross-Unit Transfer**: Sharing regime centroids across units in the same fleet
- **Predictive Regime**: Markov-chain regime transition model for RUL estimation (outside detection)

---

## References

- Mahalanobis, P.C. (1936). *On the generalized distance in statistics*
- Page, E.S. (1954). *Continuous inspection schemes* (CUSUM)
- Goldstein, M. & Uchida, S. (2016). *A Comparative Evaluation of Unsupervised Anomaly Detection Algorithms*
- Neraium core papers: TBD

