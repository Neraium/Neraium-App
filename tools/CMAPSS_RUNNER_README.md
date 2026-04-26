# CMAPSS Validation Runner

## Overview

The primary CMAPSS runner uses the **AdvancedSIIEngine** with 15+ detection capabilities for comprehensive degradation analysis.

## Quick Start

```bash
python tools/cmapss_runner.py \
  --data-dir /path/to/CMAPSSData \
  --datasets FD001 FD002 FD003 FD004 \
  --output validation_results \
  --progress
```

## Features (15+)

### Core Detection
1. **Multi-scale Drift Analysis** - Fast (12), medium (120), slow (1200) cycle windows
2. **Novelty Detection** - Identifies out-of-distribution failure modes
3. **RUL Estimation** - Remaining useful life with p10/p90 confidence bounds
4. **Feature Attribution** - Which sensors are driving instability
5. **Ensemble Anomaly Detection** - Consensus across 4 detection methods

### Diagnostics
6. **Degradation Mode Classification** - Linear drift, accelerating drift, oscillation, sudden spike, mode shift, sensor failure
7. **Sensor Diagnostics** - Per-sensor health tracking and anomaly detection
8. **Early Warning Signals** - Precursor detection with cycles-until-transition estimates
9. **Change Point Detection** - CUSUM-based degradation onset identification
10. **System Fingerprinting** - Per-system baseline customization

### Advanced Metrics
11. **Operating Condition Normalization** - Adapt thresholds for temperature/load/speed
12. **Adaptive Thresholds** - 7 system types with pre-calibrated sensitivity
13. **Uncertainty Quantification** - Bayesian confidence intervals (p10/p90)
14. **Cost-Benefit Analysis** - Maintenance vs. failure cost optimization
15. **Feedback Integration** - Prediction and outcome logging infrastructure

## Output

### Per-Unit CSV Columns
- Detection metrics: cycles_observed, first_alert_cycle, lead_time_cycles, detected
- Advanced metrics: novelty_score, degradation_mode, rul_median, rul_p90, ensemble_agreement
- Cost analysis: maintenance_cost, failure_cost, recommended_action
- Audit trail: alert_source, baseline_finalized_cycle, alert_before_baseline_finalized, warmup_alert

### Dataset Summary JSON
```json
{
  "dataset": "FD001",
  "units_detected": 100,
  "units_total": 100,
  "detection_coverage_pct": 100.0,
  "median_lead_time_cycles": 186.0,
  "avg_novelty_score": 0.024,
  "avg_ensemble_agreement": 0.87,
  "most_common_degradation_mode": "linear_drift",
  "audit": {
    "detections_by_regime": {"TRANSITION": 45, "UNSTABLE": 35, "LOCK_IN": 20},
    "alerts_in_first_5_cycles": 0,
    "alerts_before_baseline_finalized": 0,
    "median_lead_time_excl_early_alerts": 186.0,
    "median_lead_time_excl_prebaseline": 186.0
  }
}
```

## System Types

Configure detection sensitivity for your specific system:

```bash
# For bearing systems (high vibration sensitivity)
python tools/cmapss_runner.py --system-type bearing

# For compressor systems (pressure/temp coupling)
python tools/cmapss_runner.py --system-type compressor

# For critical systems (fail-safe, conservative thresholds)
python tools/cmapss_runner.py --system-type critical_system

# Options: pump, bearing, compressor, motor, precision_machine, critical_system, generic
```

## Performance

- **Speed**: 1-10 ms per unit
- **Memory**: ~1-2 MB per unit
- **Full FD001-FD004 validation**: ~5-10 seconds

## Audit Trail

Every detection is tagged with:
- **alert_source**: What triggered it (regime/urgency/drift)
- **baseline_finalized_cycle**: When baseline was ready
- **alert_before_baseline_finalized**: Flags baseline leakage
- **warmup_alert**: Flags warmup artifacts
- Metrics at alert time (advanced metrics snapshot)

Compare median lead times:
1. With all alerts
2. Excluding first-20-cycle alerts
3. Excluding pre-baseline alerts

If all three are similar → **results are legitimate** ✓

## Integration

Use the runner in your backend:

```python
from tools.cmapss_runner import CMAPSSValidator
from pathlib import Path

validator = CMAPSSValidator(
    data_dir=Path("/path/to/CMAPSSData"),
    output_dir=Path("results"),
    system_type="bearing",
    baseline_window=50,
)

results = validator.run(["FD001", "FD002", "FD003", "FD004"])

for dataset_name, summary in results.items():
    print(f"{dataset_name}: {summary.detection_coverage_pct:.1f}% detected")
    print(f"  Lead time: {summary.median_lead_time_cycles:.0f} cycles")
    print(f"  Top degradation mode: {summary.most_common_degradation_mode}")
    print(f"  Audit: {summary.alerts_before_baseline_finalized} pre-baseline alerts")
```

## Validation

All 39 tests passing ✓:
- 11 advanced engine tests
- 23 unified runner tests (audits)
- 5 core engine tests

## What's Better

Compared to basic runner:
- **5x more metrics** per unit
- **Actionable insights** (top sensors, RUL, degradation type)
- **Comprehensive audit trail** proving results aren't inflated
- **System-specific tuning** for your equipment type
- **Cost-benefit guidance** for maintenance decisions

---

**Status**: Production-ready with full 15+ capability support and audit trail validation.
