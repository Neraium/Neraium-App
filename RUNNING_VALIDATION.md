# Running Neraium for CMAPSS and iGrow

## CMAPSS (NASA Turbofan Engine Dataset)

### What It Is
- **Data**: Commercial turbofan engine degradation time series
- **System**: Multi-sensor monitoring of jet engine performance
- **Purpose**: Validate RUL (Remaining Useful Life) prediction
- **Format**: train_FD00X.txt (training data) + RUL_FD00X.txt (ground truth)
- **Datasets**: FD001, FD002, FD003, FD004 (different operational conditions & fault modes)

### Runner: `tools/cmapss_runner.py`

**Command:**
```bash
python tools/cmapss_runner.py \
  --data-dir /path/to/CMAPSSData \
  --datasets FD001 FD002 FD003 FD004 \
  --output validation_results \
  --system-type generic \
  --baseline-window 50 \
  --min-baseline 50 \
  --alert-mode strict \
  --progress
```

**Parameters:**
- `--data-dir`: Path containing train_FD00X.txt and RUL_FD00X.txt files
- `--datasets`: Which datasets to validate (default: all 4)
- `--baseline-window`: Initial stable period (cycles)
- `--min-baseline`: Minimum required samples
- `--alert-mode`: `strict` (core 5-factor) or `experimental` (all 15 metrics)
- `--system-type`: `generic`, `bearing`, `compressor`, etc.

**Output:**
```
validation_out_advanced/
├── summary.json           # Overall detection rates
├── FD001_results.json     # Per-dataset metrics
├── FD002_results.json
├── FD003_results.json
└── FD004_results.json
```

**What It Measures:**
- Detection rate: % of units with pre-failure alert
- Lead time: cycles before actual failure
- False positives: alerts that don't lead to failure
- RUL accuracy: predicted vs actual remaining life
- Degradation modes: linear, accelerating, oscillation, spike, etc.

---

## iGrow (WUR Greenhouse Climate Data)

### What It Is
- **Data**: Greenhouse climate sensor readings (temp, humidity, CO2, etc.)
- **Purpose**: Validate unsupervised anomaly detection (no failure labels)
- **Format**: CSV with timestamp, zone ID, sensor columns
- **Challenge**: Climate data has natural cycles, no clear "failures"

### Runner: `tools/wur_greenhouse_runner.py`

**Command:**
```bash
python tools/wur_greenhouse_runner.py \
  --data-file climate_data.csv \
  --output validation_results \
  --baseline-window 100 \
  --min-baseline 20 \
  --progress
```

**Parameters:**
- `--data-file`: CSV with climate data
- `--output`: Output directory
- `--baseline-window`: Initial stable period (hours/days)
- `--min-baseline`: Minimum required samples
- `--progress`: Show progress bar

**Expected CSV Format:**
```
timestamp,zone,temperature,humidity,co2,light,actuator1,actuator2
2024-01-01 08:00:00,zone1,22.5,65.3,450,850,0.2,0.1
2024-01-01 08:15:00,zone1,22.6,65.2,455,860,0.2,0.1
...
```

**Output:**
```
validation_out/
├── summary.json              # Overall stability stats
├── per_zone_results.json     # Per-zone anomalies
├── per_timestep_results.csv  # Per-sample diagnostics
└── zones_analysis.json       # Zone grouping insights
```

**What It Measures:**
- Zones with anomalies detected
- Total anomalies per zone
- % time system unstable
- Instability duration statistics
- Sensor contribution to instability
- No accuracy claims (unsupervised)

---

## Example Workflows

### Workflow 1: Validate CMAPSS Detection Quality

```bash
# 1. Download CMAPSS data (if not already available)
mkdir -p data/cmapss
# Download from NASA prognostics repository

# 2. Run strict mode (baseline performance)
python tools/cmapss_runner.py \
  --data-dir data/cmapss \
  --alert-mode strict \
  --output results_strict \
  --progress

# 3. Run experimental mode (advanced metrics)
python tools/cmapss_runner.py \
  --data-dir data/cmapss \
  --alert-mode experimental \
  --output results_experimental \
  --progress

# 4. Compare results
cat results_strict/summary.json
cat results_experimental/summary.json
```

### Workflow 2: Validate iGrow Stability Monitoring

```bash
# 1. Export climate data from iGrow system
# (Export as CSV with timestamp, zone, sensor columns)

# 2. Run unsupervised validation
python tools/wur_greenhouse_runner.py \
  --data-file exported_climate.csv \
  --output igrow_validation \
  --progress

# 3. Review stability report
cat igrow_validation/summary.json | jq '.stability_metrics'

# 4. Check per-zone anomalies
cat igrow_validation/per_zone_results.json | jq '.zones_with_anomalies'
```

### Workflow 3: System-Type Tuning

```bash
# Test different system types for CMAPSS
for system in generic bearing compressor motor; do
  echo "Testing $system..."
  python tools/cmapss_runner.py \
    --data-dir data/cmapss \
    --system-type $system \
    --output results_$system \
    --progress
done

# Compare detection rates by system type
for f in results_*/summary.json; do
  echo "$f:"
  jq '.detection_rate' $f
done
```

---

## Data Requirements

### CMAPSS
- **Minimum**: ~100 units × ~100 cycles = 10K samples
- **Sensors**: 21 engine sensors per timestep
- **Training phase**: 50 cycles to establish baseline
- **Typical runtime**: 2-5 minutes for all 4 datasets

### iGrow
- **Minimum**: ~1000 timesteps (hourly data = ~6 weeks)
- **Sensors**: Temperature, humidity, CO2, light, actuators (5-10 typical)
- **Zones**: 1-N (multi-zone support)
- **Typical runtime**: 30-60 seconds depending on data size

---

## Output Interpretation

### CMAPSS Results

```json
{
  "dataset": "FD001",
  "total_units": 100,
  "detected": 75,
  "detection_rate_pct": 75.0,
  "avg_lead_time_cycles": 12.5,
  "avg_novelty_score": 0.43,
  "avg_ensemble_agreement": 0.68,
  "degradation_modes": {
    "linear_drift": 45,
    "accelerating_drift": 20,
    "periodic_oscillation": 10
  }
}
```

**Interpretation:**
- Detection rate > 70% = good
- Lead time > 10 cycles = useful for maintenance scheduling
- Ensemble agreement > 0.6 = high factor consensus

### iGrow Results

```json
{
  "validation_type": "unsupervised_telemetry",
  "zones_with_anomalies": 3,
  "total_anomalies_detected": 127,
  "anomalies_per_zone": {
    "zone1": 45,
    "zone2": 32,
    "zone3": 50
  },
  "percent_time_unstable": 12.3,
  "instability_duration_stats": {
    "min_consecutive_cycles": 1,
    "max_consecutive_cycles": 8,
    "avg_duration": 2.1
  }
}
```

**Interpretation:**
- Anomalies = structural drift detected
- % unstable < 15% = normal operation
- Long durations = sustained deviations (possibly real issues)

---

## Troubleshooting

### CMAPSS: "Files not found"
- Check that files are named `train_FD001.txt`, `RUL_FD001.txt` etc.
- (Not `test_FD001.txt` - runner uses training data for validation)

### iGrow: "Autodetection failed"
- Ensure CSV has headers
- Timestamp column must be recognized (ISO format preferred)
- Need at least 5 numeric sensor columns

### Memory issues
- CMAPSS: Process one dataset at a time if RAM limited
- iGrow: Downsample (use every 10th reading) for large files

### Detection rates too low
- Increase `--baseline-window` (more stable data needed)
- Check data quality (missing values, outliers)
- Try different `--system-type` if available
