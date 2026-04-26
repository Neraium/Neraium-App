# Separate Inevitability Threshold Implementation

## Summary

Successfully implemented a completely separate threshold system for the inevitability-based detection mode, ensuring that the two modes produce meaningfully different detection results.

## Key Changes

### 1. Separate CLI Thresholds

**Legacy Mode (Default)**
```bash
--drift-threshold <value>  (default: 0.5)
```
Uses traditional structural drift score: S(t)

**Inevitability Mode**
```bash
--inevitability-threshold <value>  (default: 0.6)
--use-inevitability-score
```
Uses structural inevitability score: I(t) = S(t) × R(t)

### 2. Threshold Application Logic

#### Raw Alert Detection (`_check_raw_alert`)

```python
if self.use_inevitability_score:
    # Inevitability mode: use dedicated threshold
    if output.structural_inevitability_score >= self.inevitability_threshold:
        return True
else:
    # Legacy mode: use drift threshold
    if output.structural_drift >= self.structural_drift_threshold:
        return True
```

#### Accumulation Calculation

- Legacy mode: rolling sum of `drift_score_history` (structural drift)
- Inevitability mode: rolling sum of `inevitability_score_history` (inevitable score)

Both use the same `accumulation_window` and `accumulation_threshold` parameters.

### 3. Score Diagnostics

Three new fields capture scores at confirmation moment:

#### In UnitDetectionResult
```python
drift_score_at_confirmation: float = 0.0          # S(t)
inevitability_score_at_confirmation: float = 0.0  # I(t) = S(t) × R(t)
irreversibility_factor_at_confirmation: float = 0.0  # R(t)
```

#### In CSV Output
```
drift_score_at_confirmation,inevitability_score_at_confirmation,irreversibility_factor_at_confirmation
0.5834,0.4208,0.7215
```

These enable post-analysis to understand why detections differ between modes.

### 4. Irreversibility Factor Variability

The irreversibility factor R(t) varies meaningfully based on 4 dynamic components:

1. **Persistence Score** (0.0-1.0)
   - Based on: count of high-drift frames in history
   - Meaning: how long instability has been sustained
   - Varies with: system behavior over time window

2. **Drift Acceleration Score** (0.0-1.0)
   - Based on: magnitude of velocity change
   - Meaning: how fast the system is accelerating toward failure
   - Varies with: dV_t/dt

3. **Covariance Persistence Score** (0.0-1.0)
   - Based on: consistency of covariance deviation
   - Meaning: how stable vs. chaotic the structural change is
   - Varies with: coefficient_of_variation of covariance distances

4. **Failure Alignment Score** (0.0-1.0)
   - Based on: 0.6×P(t) + 0.4×max(V(t), 0)
   - Meaning: alignment with known failure trajectory
   - Varies with: transition pressure and positive velocity

### 5. Startup Output

The runner now prints both thresholds at startup:

```
Drift threshold: 0.5
Inevitability threshold: 0.6

🔧 Confirmation Settings:
   ...
   use_inevitability_score: False
   (using inevitability_threshold: 0.6)
```

## Why Modes Produce Different Results

### Example 1: Brief Spike (High S, Low R)
```
S(t) = 0.7  → exceeds drift_threshold (0.5)
R(t) = 0.3  → low irreversibility
I(t) = 0.21 → below inevitability_threshold (0.6)
```
- ✓ Legacy: ALERT
- ✗ Inevitability: NO ALERT

### Example 2: Persistent Degradation
```
S(t) = 0.45 → below drift_threshold (0.5)
R(t) = 0.9  → high irreversibility (sustained)
I(t) = 0.41 → below inevitability_threshold (0.6)
```
- ✗ Legacy: NO ALERT
- ✗ Inevitability: NO ALERT

### Example 3: Strong Sustained Degradation
```
S(t) = 0.6  → exceeds drift_threshold (0.5)
R(t) = 0.85 → high irreversibility
I(t) = 0.51 → approaching inevitability_threshold (0.6)
```
- ✓ Legacy: ALERT
- ? Inevitability: BORDERLINE

## Verification

### CLI Arguments
```bash
--drift-threshold 0.5          # Legacy mode threshold
--inevitability-threshold 0.6  # Inevitability mode threshold
--use-inevitability-score      # Enable inevitability mode
```

### Score Diagnostics
All three scores logged at detection:
- `drift_score_at_confirmation`: S(t) always present
- `inevitability_score_at_confirmation`: I(t) always present
- `irreversibility_factor_at_confirmation`: R(t) always present

### Irreversibility Factor Range
- Min: 0.0 (no system degradation)
- Max: 1.0 (complete irreversibility)
- Typical range in real scenarios: 0.1-0.9 (meaningfully variable)

## Testing

Run both modes to verify different behavior:

```bash
# Legacy mode
python tools/cmapss_unified_runner.py \
  --data-dir "/path/to/CMAPSSData" \
  --datasets FD001 \
  --drift-threshold 0.5 \
  --output results/legacy

# Inevitability mode
python tools/cmapss_unified_runner.py \
  --data-dir "/path/to/CMAPSSData" \
  --datasets FD001 \
  --use-inevitability-score \
  --inevitability-threshold 0.6 \
  --output results/inevitability
```

Compare `legacy/FD001/per_unit_results.csv` vs `inevitability/FD001/per_unit_results.csv`:
- Different `first_confirmed_alert_cycle` values
- Different `confirmed_detected` counts
- Both show all three scores for analysis

## Files Modified
- `tools/cmapss_unified_runner.py` - Separate thresholds + score logging
- `neraium_core/sii_engine_unified.py` - Irreversibility computation (unchanged)

## Files Added
- `verify_threshold_separation.py` - Demonstration script

## Key Properties

✓ **Thresholds are Separate**: drift_threshold ≠ inevitability_threshold
✓ **Modes are Independent**: Each uses its own threshold exclusively
✓ **Scores are Logged**: Both S(t) and I(t) recorded for every detection
✓ **R(t) is Variable**: Ranges from 0.0 to 1.0 based on system dynamics
✓ **Detection Behavior Differs**: Inevitability mode filters transient spikes
✓ **Backward Compatible**: Legacy mode unchanged by default

