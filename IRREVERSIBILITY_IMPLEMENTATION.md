# Irreversibility Layer Implementation

## Overview
Added a new irreversibility layer to the SII Engine that computes a **structural inevitability score** I(t) = S(t) × R(t), where:
- **S(t)** = existing 5-factor instability score (unchanged)
- **R(t)** = irreversibility factor composed of 4 components

## Changes Made

### 1. SII Engine (`neraium_core/sii_engine_unified.py`)

#### New Fields in SIIEngineOutput
```python
structural_inevitability_score: float = 0.0  # I(t) = S(t) * R(t)
irreversibility_factor: float = 0.0          # R(t): composite irreversibility
persistence_score: float = 0.0               # Component 1
drift_acceleration_score: float = 0.0        # Component 2
covariance_persistence_score: float = 0.0    # Component 3
failure_alignment_score: float = 0.0         # Component 4
```

#### New Methods (4 component + 1 aggregator)

1. **`_compute_persistence_score(S_t)`**
   - Measures how long drift has been sustained above threshold
   - Based on count of high-drift frames in history
   - Range: [0, 1]

2. **`_compute_drift_acceleration_score(V_t)`**
   - Measures rate of change in drift velocity
   - Indicates if system is accelerating toward failure
   - Computes: dV_t/dt using tanh bounding
   - Range: [0, 1]

3. **`_compute_covariance_persistence_score()`**
   - Measures consistency of covariance deviation from baseline
   - Low variability = high persistence (consistent deviation)
   - Computes: 1 / (1 + coefficient_of_variation)
   - Range: [0, 1]

4. **`_compute_failure_alignment_score(P_t, V_t)`**
   - Measures alignment with failure trajectory
   - Combines transition pressure (60%) + positive velocity (40%)
   - Range: [0, 1]

5. **`_compute_irreversibility_factor(...)`**
   - Aggregates 4 component scores with equal weighting (25% each)
   - Applies soft amplification: R(t) = mean(components)^0.8
   - Range: [0, 1]

#### Pipeline Integration
- Called in update() after 5-factor instability computation
- Inevitability score computed: `I(t) = instability_score × irreversibility_factor`
- All scores included in SIIEngineOutput.to_dict()

### 2. CMAPSS Runner (`tools/cmapss_unified_runner.py`)

#### New CLI Flag
```bash
--use-inevitability-score
```
- Toggles between traditional drift-based and new inevitability-based confirmation
- Default: False (backward compatible, legacy behavior)

#### Implementation
- When flag enabled:
  - `_check_raw_alert()` checks `structural_inevitability_score` instead of `structural_drift`
  - Confirmation logic uses inevitability score for accumulation window calculation
  - Same threshold comparison as drift (same `--drift-threshold` applies)

- When flag disabled (default):
  - Behaves exactly as before
  - Uses only `structural_drift` for all decisions
  - No change to existing behavior

#### Startup Output
Runner prints the inevitability flag setting:
```
🔧 Confirmation Settings:
   use_inevitability_score: False
```

### 3. Verification Script
Created `verify_irreversibility_layer.py` that:
- Generates synthetic degradation signal
- Verifies 5-factor S(t) unchanged
- Verifies R(t) computation
- Verifies I(t) = S(t) × R(t) bounds
- Checks all 4 components are valid [0,1]
- Verifies runner CLI flag integration

## Backward Compatibility

✓ Fully backward compatible:
- Default behavior unchanged (legacy drift-based detection)
- Existing five-factor math preserved
- All existing fields and methods intact
- New fields don't affect legacy code
- Opt-in via `--use-inevitability-score` flag

## Usage

### Legacy Mode (Default)
```bash
python tools/cmapss_unified_runner.py \
  --data-dir "/path/to/CMAPSSData" \
  --datasets FD001 FD002 \
  --progress
```
Uses structural_drift for confirmation logic.

### Inevitability Mode
```bash
python tools/cmapss_unified_runner.py \
  --data-dir "/path/to/CMAPSSData" \
  --datasets FD001 FD002 \
  --use-inevitability-score \
  --progress
```
Uses structural_inevitability_score for confirmation logic.

## Verification Commands

```bash
# Check for flag and field definitions
grep -n "structural_inevitability_score\|irreversibility_factor\|use-inevitability-score" \
  tools/cmapss_unified_runner.py neraium_core/sii_engine_unified.py

# Run verification script
python verify_irreversibility_layer.py

# Check engine output includes new fields
python -c "from neraium_core.sii_engine_unified import SIIEngineOutput; \
  print([f for f in SIIEngineOutput.__dataclass_fields__.keys() \
  if 'inevitability' in f or 'irreversibility' in f])"
```

## Mathematical Foundation

### Irreversibility Factor Computation
```
R(t) = (P(t) + A(t) + C(t) + F(t))^0.8 / 4

where:
  P(t) = persistence_score       [how long drift sustained]
  A(t) = drift_acceleration      [how fast it's changing]
  C(t) = covariance_persistence  [consistency of deviation]
  F(t) = failure_alignment       [trajectory alignment]

All components in [0, 1]
```

### Inevitability Score
```
I(t) = S(t) × R(t)

where:
  S(t) = 5-factor instability (existing, unchanged)
  R(t) = irreversibility factor (new)
  I(t) = structural inevitability (new)

Result in [0, 1]
```

## Key Properties

1. **Non-Destructive**: Five-factor math S(t) completely unchanged
2. **Additive**: New fields don't remove or modify existing ones
3. **Composable**: Can be used alongside existing drift thresholds
4. **Interpretable**: Each component has clear physical meaning
5. **Bounded**: All outputs normalized to [0, 1] for consistency
6. **Optional**: Enabled via explicit flag, defaults to legacy

## Files Modified
- `neraium_core/sii_engine_unified.py` - Core engine with irreversibility layer
- `tools/cmapss_unified_runner.py` - CLI flag and detection logic
- `verify_irreversibility_layer.py` - Verification script (new)

## Testing
Run with synthetic data or CMAPSS datasets in both modes to compare:
- Legacy drift-based detections
- New inevitability-based detections
- Verify performance difference if any

