# Drift Detection Test Runner - CMAPSS FD004

## Overview

This is an efficient, multi-dimensional drift detection test runner that uses all 5 intelligence components from the Neraium framework to detect early signals of system degradation on NASA CMAPSS FD004 dataset.

### FD004 Complexity (Hardest CMAPSS Variant)

FD004 is the most challenging CMAPSS subset:

- **249 units** in the test set (vs 100 in FD001-FD003)
- **6 operating conditions** with non-linear degradation interactions
- **2 fault modes**:
  - HPC (High Pressure Compressor) degradation
  - Fan degradation
- **Highly variable degradation rates** - Different conditions and fault modes produce very different degradation trajectories

This complexity requires:
- **Operating condition awareness** - Same component signal means different things in different operating states
- **Fault mode differentiation** - Different intelligence components activate for HPC vs Fan failures
- **Adaptive thresholding** - Baseline varies significantly across conditions
- **Multi-scale temporal analysis** - Some signals appear at short timescales, others long timescales

### Intelligence Components

The runner integrates **5 QIT (Quantum-Information-Topological) intelligence signals**:

1. **Quantum Component** - Phase-space anomaly detection using quantum basis decomposition
2. **Information Component** - Entropy-based degradation signal from sensor uncertainty changes  
3. **Free Energy Component** - Thermodynamic proxy for system disorder
4. **Topological Component** - Structural connectivity drift detection
5. **Algorithmic Component** - Algorithmic complexity changes from sensor evolution

Each component produces independent drift signals that are fused to create:
- **Raw drift score**: Unsmoothed combined signal
- **EMA drift score**: Exponential moving average for trend detection
- **Component activation rates**: How often each detector fires

## Quick Start

### Installation

The runner uses existing dependencies. Ensure you have CMAPSS FD004 data accessible:

```bash
# Expected data path: train_FD004.txt
# Alternative: Specify via --path argument
```

### Two Runner Options

#### 1. Basic Runner (Comprehensive Analysis)
Run the complete drift detection pipeline on all 249 units:

```bash
python -m fd00x.run_drift_detection_demo
```

**With Options:**
```bash
# Test only first 50 units (faster)
python -m fd00x.run_drift_detection_demo --max-units 50

# Skip visualization generation (faster)
python -m fd00x.run_drift_detection_demo --no-plots

# Custom output directory
python -m fd00x.run_drift_detection_demo --output-dir ./my_results

# Visualize specific units
python -m fd00x.run_drift_detection_demo --units 1 5 10 15

# All options combined
python -m fd00x.run_drift_detection_demo \
  --max-units 100 \
  --output-dir ./test_results \
  --units 1 5 \
  --no-plots
```

#### 2. Advanced Runner (Multi-Condition & Fault Mode Analysis)
For detailed analysis of FD004's complexity:

```bash
python -m fd00x.run_advanced_fd004_demo
```

**Features:**
- **Operating condition segmentation** - Analyzes all 6 FD004 conditions separately
- **Fault mode inference** - Distinguishes HPC degradation from Fan degradation
- **Per-condition lead times** - Different degradation rates per condition
- **Component sensitivity analysis** - Which detectors activate in each condition

**With Options:**
```bash
# Analyze first 50 units
python -m fd00x.run_advanced_fd004_demo --max-units 50

# Custom output
python -m fd00x.run_advanced_fd004_demo --output-dir ./fd004_analysis
```

## Output Files

The runner generates comprehensive results in a configurable output directory (default: `drift_test_results/`):

### Metrics & Data

- **fd004_drift_detection_results.csv** - Per-unit detailed metrics:
  - Unit ID, total cycles, warning cycle, lead time
  - False positive flag
  - Raw drift mean/max, EMA drift mean/max
  - Component peaks and means (quantum, information, free_energy, topological, algorithmic)
  - Dominant alert component, state change count

- **fd004_drift_detection_summary.json** - Aggregated statistics:
  - Detection rate (% of units with alerts)
  - False positive rate
  - Lead time statistics (median, mean, min, max, quartiles)
  - Component activation ranking
  - Performance metrics (elapsed time, throughput)

- **RESULTS.txt** - Human-readable summary report

### Visualizations

For each sampled unit:

- **unit_{ID}_signals.png** - Multi-panel comprehensive view:
  - Raw vs EMA drift with threshold and alert markers
  - All 5 component signals overlaid
  - Individual component details (peak activity, trends)
  - Healthy zone and degradation region highlighted

- **unit_{ID}_early_warning.png** - Zoomed focus on alert region:
  - Early warning phase signals around alert time
  - Component activations in ±window cycles
  - Warning state transitions
  - Perfect for understanding what triggered the alert

## Key Metrics Explained

### Detection Rate
Percentage of units that produced a warning/alert signal. High detection rate = model is sensitive to degradation.

### False Positive Rate  
Percentage of alerts that fired in the "healthy zone" (first 15% of unit life). Should be very low (<5%) for trustworthy operation.

### Lead Time
**Degradation onset** is defined as the last 10% of cycles (walk-forward safe). **Lead time** = cycles between alert and degradation onset.

- Positive lead time: Alert came before failure
- Negative lead time: Alert came after failure
- Large lead time (>100 cycles): Very early detection

### Component Activation
Ranks which intelligence components most frequently triggered alerts:

```
Component Activation Ranking:
  quantum         : 45 units (90.0%)
  information     : 40 units (80.0%)
  topological     : 35 units (70.0%)
  free_energy     : 30 units (60.0%)
  algorithmic     : 25 units (50.0%)
```

High quantum activation suggests phase-space anomalies are primary degradation signals.

## Configuration

The detector uses **DetectorConfig** with many tunable parameters:

```python
from fd00x.config import DetectorConfig
from fd00x.test_runner_drift_detection import EfficientDriftTestRunner

config = DetectorConfig(
    ema_alpha=0.15,                    # EMA smoothing factor
    threshold_std=2.0,                 # Threshold = mean + 2σ
    persistence=5,                     # Cycles to confirm alert
    fusion_activation_floor=0.3,       # Min component score to activate
    enable_ensemble_voting=True,       # Multi-scale voting
)

runner = EfficientDriftTestRunner(detector_config=config, verbose=True)
results, summary = runner.run_fd004(max_units=100)
```

## Performance

### Typical Throughput
- **2-5 units/second** on modern hardware
- Full FD004 (100 units) completes in ~20-50 seconds
- Visualization adds ~10-20 seconds for sampled units

### Memory Efficiency
- Per-unit memory: ~2-3 MB
- No full dataset preloading
- Rolling window operations use O(1) memory

## Integration Examples

### Direct API Usage

```python
from fd00x.test_runner_drift_detection import EfficientDriftTestRunner, DriftDetectionMetrics
from fd00x.config import DetectorConfig

# Initialize runner
runner = EfficientDriftTestRunner(verbose=True)

# Run on subset
results, summary = runner.run_fd004(max_units=50)

# Access per-unit metrics
for metric in results:
    print(f"Unit {metric.unit_id}: Lead time = {metric.lead_time_cycles} cycles")
    print(f"  Components: Q={metric.quantum_peak:.2f}, I={metric.information_peak:.2f}")
    print(f"  Dominant: {metric.dominant_component}")

# Save results
runner.save_results(results, summary, output_dir="my_results")
```

### Visualization of Existing Results

```python
from fd00x.test_runner_visualizer import DriftSignalVisualizer
from fd00x.detector import StructuralDriftDetector
from fd00x.evaluation import load_cmapss_dataset

# Load data
data_dict = load_cmapss_dataset("FD004")
detector = StructuralDriftDetector()

# Process a unit
unit_data = data_dict[1]
sensors = unit_data[:, 4:]  # Skip cycle + operating settings
scores = detector.process_unit(sensors)

# Visualize
viz = DriftSignalVisualizer()
viz.plot_unit_signals(
    unit_id=1,
    sensor_data=sensors,
    scores=scores,
    output_path="unit_1_signals.png"
)
viz.plot_early_warning_signals(
    unit_id=1,
    sensor_data=sensors,
    scores=scores,
    window=150,
    output_path="unit_1_early_warning.png"
)
```

## Understanding the Signals

### Raw vs EMA Drift

- **Raw drift**: Direct output of QIT detector, can be noisy
- **EMA drift**: Exponentially weighted average, smooths noise while preserving trends
- **Threshold**: Typically μ + 2σ of baseline EMA values

The warning threshold is adaptive—it's automatically calibrated from the healthy reference window so that false positives are minimized.

### Component Fusion

Each cycle, the 5 components produce independent scores [0, 1]:

```
Total Fused Score = w_q × Q + w_i × I + w_fe × FE + w_t × T + w_a × A

Where:
  w_q = 0.30  (Quantum weight)
  w_i = 0.25  (Information weight)
  w_fe = 0.20 (Free Energy weight)
  w_t = 0.15  (Topological weight)
  w_a = 0.10  (Algorithmic weight)
```

### Warning State Machine

```
STABLE → (if EMA exceeds threshold for 'persistence' cycles) → ALERT
ALERT  → (if EMA drops below 0.85×threshold for 'exit_persistence' cycles) → STABLE
```

This prevents chattering and ensures sustained, high-confidence alerts.

## Advanced Topics

### Multi-Condition Analysis (Advanced Runner)

The advanced FD004 runner (`AdvancedFD004TestRunner`) handles the complexity of 6 operating conditions:

```python
from fd00x.test_runner_advanced_fd004 import AdvancedFD004TestRunner

runner = AdvancedFD004TestRunner(verbose=True)
results, summary = runner.run_fd004_advanced()

# Results include:
# - operating_conditions_present: Which of 6 conditions appear in each unit
# - lead_time_by_condition: Different lead times per condition
# - component_by_condition: Which component dominates each condition
# - inferred_fault_mode: "HPC_like", "Fan_like", or "mixed"
# - degradation_trajectory: "smooth", "stepped", or "variable"
```

**Output Example:**
```
Operating Condition Analysis (6 conditions):
  Condition 1 : 45 detections, lead_time=150 cycles
  Condition 2 : 38 detections, lead_time=120 cycles
  Condition 3 : 42 detections, lead_time=180 cycles
  ...

Inferred Fault Modes (249 units, 2 modes):
  HPC_like     : 145 units (58.2%)
  Fan_like     : 104 units (41.8%)
```

### Fault Mode Signature Recognition

The advanced runner infers fault mode from component activation patterns:

**HPC Degradation Pattern:**
- Higher information component activation
- More topological changes
- Typical lead time: ~150 cycles
- Degradation trajectory: Monotonic (steady decline)

**Fan Degradation Pattern:**
- Higher algorithmic component changes
- More quantum phase-space anomalies
- Typical lead time: ~120 cycles
- Degradation trajectory: Stepped (sudden jumps)

### Walk-Forward Safety

All reference statistics (mean, covariance, correlation, drift distribution) are computed **only** from the healthy segment and frozen before scoring. This prevents:
- Data leakage from future anomalies
- Overfitting to unit-specific patterns
- Threshold bias from degradation signal

### Degradation Proxy Definition

CMAPSS training data has no explicit "failure onset" label. We use:

```
degradation_onset = n_cycles - int(n_cycles × degradation_proxy_fraction)
```

With default `degradation_proxy_fraction=0.1`:
- A 200-cycle unit has degradation onset at cycle 180
- Lead time = 180 - alert_cycle

### Ensemble Voting (Optional)

Enable `enable_ensemble_voting=True` for multi-scale detection:

```python
config = DetectorConfig(
    enable_ensemble_voting=True,
    micro_window=5,      # Short-term trend
    meso_window=25,      # Medium-term trend
    macro_window=100,    # Long-term trend
    acceleration_window=10,  # Rate of change
)
```

This requires majority vote from multiple temporal scales before alerting, reducing false positives further.

## Troubleshooting

### No Data Loaded
```
FileNotFoundError: Could not resolve CMAPSS FD004 data
```
Ensure `train_FD004.txt` is in the current directory, `./data/`, or specify path:
```bash
python -m fd00x.run_drift_detection_demo --path /path/to/train_FD004.txt
```

### Very Low Detection Rate
- Try increasing `healthy_fraction` (default 0.15) to use more data for reference
- Try decreasing `threshold_std` (default 2.0) to lower the alert threshold
- Try enabling `enable_ensemble_voting` for more sophisticated detection

### Too Many False Positives
- Increase `threshold_std` (default 2.0) to make threshold stricter
- Increase `persistence` (default 5) to require longer sustained signal
- Disable `require_upward_ema_trend` if degradation isn't monotonic

## References

The detector implements concepts from:
- QIT (Quantum-Information-Topological) hierarchical detection
- Structural drift theory (covariance/correlation matrix changes)
- Ensemble voting across temporal scales
- Walk-forward validation paradigm

See repository architecture docs for detailed theory.
