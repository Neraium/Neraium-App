# IMS Bearing Runner

Validates the Neraium SII Engine on the NASA IMS bearing vibration dataset.

## Overview

The IMS bearing dataset contains vibration measurements from multiple bearings running until failure. This runner:
- Extracts time-domain features from raw vibration files
- Streams features into the SII Engine for real-time monitoring
- Applies confirmation logic (persistence + accumulation + irreversibility gating)
- Detects bearing degradation and failure onset

## IMS Data Format

### Directory Structure

```
data_dir/
  bearing1/
    2004.10.22.18.51.46
    2004.10.22.19.25.35
    2004.10.22.20.39.46
    ...
  bearing2/
    2004.10.22.18.51.46
    2004.10.22.19.25.35
    ...
  bearing3/
    ...
  bearing4/
    ...
```

### File Format

Each file contains vibration samples (typically sampled at 20 kHz).

**Single column** (one bearing channel):
```
0.1234
0.2156
-0.0987
0.3214
...
```

**Multiple columns** (4 bearing channels):
```
0.1234  -0.0456  0.2891  -0.1023
0.2156   0.0789  0.1234   0.0456
-0.0987  0.1234  0.0892   0.2345
0.3214  -0.0123  0.3456   0.1892
...
```

Features are extracted per timestep from all channels and concatenated.

## Features Extracted

Per timestep, the runner extracts 6 time-domain features from each channel:

1. **RMS** - Root mean square (overall energy)
2. **Peak** - Maximum absolute amplitude
3. **Kurtosis** - Fourth moment (impulsiveness, bounded [-10, 10])
4. **Crest Factor** - Peak / RMS ratio (bounded [0, 50])
5. **Standard Deviation** - Spread of values
6. **Skewness** - Asymmetry (bounded [-10, 10])

Total feature vector size = num_channels × 6

Example:
- Single channel: 6 features
- 4 channels: 24 features

## Runner Modes

### Unsupervised Mode (Default)

No known failure time required.

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --output results/ims_bearings
```

Output metrics:
- `first_confirmed_alert_timestep` - When degradation detected
- `max_instability_score` - Peak instability reached
- `unstable_percentage` - % of timesteps with raw alerts
- `confirmed_detected` - Whether degradation was detected

### Known-Failure Mode

If failure index is known, compute lead time.

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --failure-index 2048 \
  --output results/ims_bearings
```

Output metrics:
- `lead_time_steps` - Steps from detection to failure
- `mean_lead_time` - Average lead time across bearings
- `median_lead_time` - Median lead time

## Confirmation Logic

Detection requires:

1. **Raw Alert** triggered by:
   - High structural drift: `drift_score >= drift_threshold` (0.35)
   - OR regime shift: TRANSITION, UNSTABLE, DEGRADED, FAILURE
   - OR urgency: WATCH, ALERT, CRITICAL

2. **Post-Baseline Delay**:
   - No confirmation before `post_baseline_delay` steps (default: 10)
   - Allows engine to stabilize after baseline

3. **Persistence**:
   - `raw_alert_count >= confirmation_hits` (default: 3)
   - Within `confirmation_window` (default: 5 steps)

4. **OR Accumulation**:
   - `rolling_drift_sum >= accumulation_threshold` (default: 1.75)
   - Over `accumulation_window` (default: 5 steps)

5. **Optional Irreversibility Gate** (with `--use-inevitability-score`):
   - Requires `irreversibility_factor >= inevitability_threshold` (default: 0.5)
   - Filters transient spikes, requires sustained degradation

## Usage Examples

### Basic Usage

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --output results/ims_bearings \
  --progress
```

### With Custom Thresholds

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --baseline-window 30 \
  --drift-threshold 0.4 \
  --confirmation-hits 4 \
  --confirmation-window 6 \
  --post-baseline-delay 15 \
  --progress \
  --output results/ims_custom
```

### With Inevitability Gating

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --use-inevitability-score \
  --inevitability-threshold 0.55 \
  --progress \
  --output results/ims_inevitable
```

### With Known Failure Time

```bash
python tools/ims_bearing_runner.py \
  --data-dir /path/to/ims/data \
  --failure-index 2048 \
  --progress \
  --output results/ims_with_leadtime
```

## CLI Arguments

### Data Input

- `--data-dir PATH` (required) - Directory containing bearing subdirectories
- `--output PATH` (default: ims_results) - Output directory for results

### Engine Configuration

- `--baseline-window N` (default: 25) - Samples for baseline learning
- `--min-baseline N` (default: 10) - Minimum baseline samples
- `--drift-threshold FLOAT` (default: 0.35) - Structural drift alert threshold

### Confirmation Logic

- `--confirmation-hits N` (default: 3) - Raw alerts for persistence confirmation
- `--confirmation-window N` (default: 5) - Timesteps to look back for persistence
- `--post-baseline-delay N` (default: 10) - Delay before confirming alerts
- `--accumulation-window N` (default: 5) - Timesteps for drift accumulation sum
- `--accumulation-threshold FLOAT` (default: 1.75) - Accumulation sum threshold

### Inevitability Mode

- `--use-inevitability-score` - Enable irreversibility gating
- `--inevitability-threshold FLOAT` (default: 0.5) - R(t) gate threshold

### Other

- `--failure-index N` (optional) - Known failure timestep (enables known-failure mode)
- `--progress` - Show progress bar

## Output Files

### summary.json

Overall statistics:
```json
{
  "total_bearings": 4,
  "bearings_detected": 3,
  "bearings_undetected": 1,
  "bearings_error": 0,
  "detection_rate": 75.0,
  "runner_mode": "known-failure",
  "baseline_window": 25,
  "drift_threshold": 0.35,
  "mean_lead_time_steps": 120.5,
  "median_lead_time_steps": 115.0
}
```

### per_bearing_results.csv

Per-bearing detection results:
```csv
bearing_name,total_files,baseline_files,first_raw_alert_timestep,
first_confirmed_alert_timestep,confirmed_detected,lead_time_steps,
max_instability_score,unstable_percentage,confirmation_method,
first_drift_spike,final_instability,irreversibility_at_detection,error_message
bearing1,2048,25,50,65,1,1983,0.8234,65.3,persistence,0.3156,0.7892,0.6234,
bearing2,2048,25,45,68,1,1980,0.8124,62.1,accumulation,0.3045,0.7654,0.5891,
bearing3,2048,25,-,-,0,-,0.4567,12.5,-,0.1234,0.4321,0.0000,
bearing4,2048,25,1800,1820,0,-,0.6789,45.2,-,0.2456,0.6543,0.0000,
```

## Example Data Structure

For testing, create a minimal dataset:

```bash
mkdir -p test_data/bearing1 test_data/bearing2

# Create synthetic vibration files
for i in {0..50}; do
  python3 -c "
import numpy as np
data = np.random.randn(1024) * 0.1  # 1024 samples per file
np.savetxt('test_data/bearing1/file_$i', data, fmt='%.6f')
  "
done
```

Run the runner:
```bash
python tools/ims_bearing_runner.py \
  --data-dir test_data \
  --progress \
  --output test_results
```

## Verification

```bash
# Check help
python tools/ims_bearing_runner.py --help

# Verify all CLI args present
grep -E "add_argument.*confirmation|add_argument.*baseline|add_argument.*drift|add_argument.*inevitability" \
  tools/ims_bearing_runner.py

# Check syntax
python3 -m py_compile tools/ims_bearing_runner.py
```

## Comparison with CMAPSS Runner

| Aspect | CMAPSS | IMS Bearing |
|--------|--------|-------------|
| Input | NASA CMAPSS RUL dataset | NASA IMS vibration files |
| Features | 21 sensors (pre-extracted) | 6 time-domain features per channel |
| Cycles | Run-to-failure indices | Timesteps in vibration files |
| RUL | Known (RUL file) | Optional (failure-index arg) |
| Output | Detection timing + lead time | Detection + unstable % + lead time |

## Notes

- Features are normalized and bounded to prevent extreme values
- Kurtosis, skewness, and crest factor are bounded to [-10, 10] / [0, 50]
- Files are processed in alphabetical order (should be chronological)
- Multiple bearing channels are concatenated into a single feature vector
- Baseline learning uses first N files (configurable)
- Confirmation requires both persistence/accumulation AND irreversibility (if enabled)

