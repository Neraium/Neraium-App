# Shadow Mode: Production Validation & Evidence Pipeline

Shadow mode enables read-only deployment of the Neraium engine in production to process live or replayed telemetry while recording all outputs as structured evidence. No external actions are triggered—only observations are recorded.

## Overview

Shadow mode is designed for:
- **Production validation** before deploying policy changes
- **Doctrine version comparison** (compare old vs. new decision logic)
- **Compliance audit trails** (complete record of all decisions)
- **Deterministic replay** (exact same telemetry → reproducible analysis)

## Architecture

```
Telemetry Input
    ↓
[ShadowModeRunner]
    ↓
[ProductionEngine] (read-only, no external actions)
    ↓
[EvidenceLogger] → JSONL evidence log
    ↓
[SummaryReport] → JSON summary
    ↓
[ReplayDiff] (optional: compare to baseline)
```

## Quick Start

### 1. Process Telemetry File

```python
from validation.shadow_mode.runner import ShadowModeRunner
from neraium_core import ProductionEngine

# Initialize engine
engine = ProductionEngine(...)

# Create shadow-mode runner
runner = ShadowModeRunner(
    decision_fn=engine.process_frame,
    output_dir="/var/shadow_runs/2024-04-12",
    run_name="doctrine_v2024_04",
    engine_version="2.0.0",
    doctrine_version="2024-04",
)

# Process telemetry
result = runner.process_telemetry_file("/data/telemetry.jsonl")
print(f"Processed {result['frames_processed']} frames")

# Finalize and generate reports
summary = runner.finalize()
print(f"Evidence: {summary['paths']['evidence_log']}")
print(f"Report: {summary['paths']['summary_report']}")
```

### 2. CLI Usage

```bash
# Process a telemetry file
python -m validation.shadow_mode.runner process \
    --telemetry /data/telemetry.jsonl \
    --output /var/shadow_runs/2024-04-12 \
    --run-name doctrine_v2024_04

# Output files:
# /var/shadow_runs/2024-04-12/doctrine_v2024_04_evidence.jsonl
# /var/shadow_runs/2024-04-12/doctrine_v2024_04_summary.json
# /var/shadow_runs/2024-04-12/doctrine_v2024_04_metadata.json
```

## Artifacts

### Evidence Log (`_evidence.jsonl`)

Append-only JSONL file with one frame per line. Each line contains:

```json
{
  "timestamp_utc": "2024-04-12T12:34:56.123456+00:00",
  "frame_index": 0,
  "processing_latency_ms": 1.234,
  "asset_id": "turbine_001",
  "unit_id": "unit_a",
  "domain": "wind",
  "system_type": "generator",
  "state": "STABLE",
  "policy_state": "STABLE",
  "structural_drift_score": 0.123,
  "structural_drift_score_smoothed": 0.115,
  "relational_instability_score": 0.045,
  "transition_pressure": 0.0,
  "confidence_score": 0.95,
  "data_quality_summary": { "all_good": true },
  "active_sensor_count": 12,
  "missing_sensor_count": 0,
  "transition_detected": false,
  "transition_state": "NONE",
  "regime_name": null,
  "regime_distance": null,
  "dominant_driver": "vibration_x",
  "top_drivers": [
    { "name": "vibration_x", "score": 0.87 },
    { "name": "temperature", "score": 0.61 }
  ],
  "validation_errors": null,
  "input_validation_passed": true,
  "raw_engine_output": { ... }
}
```

### Summary Report (`_summary.json`)

High-level statistics including:

```json
{
  "overview": {
    "total_frames": 10000,
    "unique_assets": 42,
    "time_range": {
      "start": "2024-04-12T00:00:00Z",
      "end": "2024-04-12T23:59:59Z"
    }
  },
  "per_asset": {
    "turbine_001": {
      "frame_count": 240,
      "state_distribution": {
        "STABLE": 200,
        "WATCH": 35,
        "ALERT": 5
      },
      "avg_drift_score": 0.152,
      "transitions_detected": 8
    }
  },
  "state_distribution": {
    "state_counts": {
      "STABLE": 8500,
      "WATCH": 1200,
      "ALERT": 300
    },
    "state_percentages": {
      "STABLE": 85.0,
      "WATCH": 12.0,
      "ALERT": 3.0
    }
  },
  "transitions": {
    "total_transitions": 247,
    "transition_types": {
      "STABLE->WATCH": 150,
      "WATCH->STABLE": 75,
      "WATCH->ALERT": 22
    }
  },
  "data_quality": {
    "validation_pass_rate": 99.8,
    "failed_frames": 20,
    "avg_active_sensors": 10.5,
    "error_summary": { ... }
  },
  "latency": {
    "samples": 10000,
    "min_ms": 0.5,
    "max_ms": 12.3,
    "mean_ms": 2.15,
    "median_ms": 1.95,
    "p95_ms": 4.2,
    "p99_ms": 8.1
  }
}
```

### Metadata (`_metadata.json`)

Run configuration and timing:

```json
{
  "run_name": "doctrine_v2024_04",
  "start_time_utc": "2024-04-12T12:00:00Z",
  "end_time_utc": "2024-04-12T12:15:30Z",
  "duration_seconds": 930,
  "frame_count": 10000,
  "asset_count": 42,
  "engine_version": "2.0.0",
  "doctrine_version": "2024-04",
  "config": { "param_1": "value_1" }
}
```

## Replay Comparison

Compare outputs from two runs on identical telemetry:

```python
from validation.shadow_mode.replay_diff import generate_replay_diff

# Compare doctrine versions
report = generate_replay_diff(
    run_a_evidence=Path("/shadow_runs/doctrine_v2024_03_evidence.jsonl"),
    run_b_evidence=Path("/shadow_runs/doctrine_v2024_04_evidence.jsonl"),
    run_a_name="Doctrine v2024.03",
    run_b_name="Doctrine v2024.04",
    output_path=Path("/shadow_runs/comparison_report.json"),
)

# Inspect report
print(f"Frames with differences: {report['summary']['frames_with_differences']}")
print(f"Match rate: {report['summary']['match_rate']}%")

# Critical field mismatches
for field in report['field_level_diff']['critical_field_mismatches']:
    print(f"{field['field']}: {field['mismatch_count']} mismatches")
```

## Integration with ProductionEngine

The runner accepts any decision function that matches this signature:

```python
def decision_fn(frame: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        frame: Raw telemetry frame with asset_id, sensors, etc.
    
    Returns:
        Dictionary with at minimum:
        - state: str (STABLE, WATCH, ALERT)
        - policy_state: str
        - structural_drift_score: float
        - relational_instability_score: float
        - transition_detected: bool
        - ... (and any other engine outputs)
    """
    pass
```

### Connecting to Real Engine

```python
# Wrap engine's process_frame method
from neraium_core.engine.orchestration import CoreDetectionOrchestrator

orchestrator = CoreDetectionOrchestrator()

def engine_decision_fn(frame):
    # Extract sensor data
    sensors = frame.get("sensors", {})
    asset_id = frame.get("asset_id")
    
    # Process through orchestrator
    results = orchestrator.process_windows(...)
    
    # Format as standard output
    return {
        "state": results["alert_state"],
        "structural_drift_score": results["drift_score"],
        # ... map all required fields
    }

runner = ShadowModeRunner(decision_fn=engine_decision_fn)
```

## Export & Analysis

### Export to CSV

```python
from validation.shadow_mode.evidence import EvidenceDataFrame
from pathlib import Path

rows = EvidenceDataFrame.export_to_csv(
    jsonl_path=Path("evidence.jsonl"),
    csv_path=Path("evidence.csv"),
)
print(f"Exported {rows} rows to CSV")
```

### Generate Report from Evidence

```python
from validation.shadow_mode.report import generate_report_from_evidence

report = generate_report_from_evidence(
    evidence_path=Path("_evidence.jsonl"),
    output_path=Path("_summary.json"),
)
```

## Error Handling

The runner continues processing even when frames fail:

```python
# Process stream with potential errors
runner.process_telemetry_stream(frames)

# Review errors
for error in runner.errors:
    print(f"Frame {error['frame_index']}: {error['error']}")

# Finalize still works
summary = runner.finalize()
print(f"Error rate: {summary['summary_stats']['error_rate']}%")
```

Failed frames are recorded as ERROR state in the evidence log with validation errors captured.

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_shadow_mode.py -v

# Specific test class
pytest tests/test_shadow_mode.py::TestShadowModeRunner -v

# With coverage
pytest tests/test_shadow_mode.py --cov=validation.shadow_mode
```

Test coverage includes:
- Evidence frame creation and JSONL logging
- Summary report generation
- State distribution analysis
- Latency statistics
- Transition counting
- Per-asset isolation
- Error handling
- Replay comparison
- CSV export
- Full integration workflow

## Performance

Shadow mode is designed for production:
- **No external calls** made (read-only)
- **Minimal overhead** (~1-5ms per frame typical)
- **Memory efficient** (streaming JSONL, no buffering)
- **Per-unit isolation** (asset tracking)
- **Append-only logs** (safe concurrent access)

## Key Files

```
validation/shadow_mode/
├── __init__.py          # Package definition
├── runner.py            # Main entry point (ShadowModeRunner)
├── evidence.py          # JSONL logging (EvidenceLogger)
├── report.py            # Summary generation (ShadowModeSummaryReport)
└── replay_diff.py       # Replay comparison (ReplayDiff)

tests/
└── test_shadow_mode.py  # Comprehensive test suite

SHADOW_MODE_README.md    # This file
```

## Workflow Examples

### Example 1: Validate New Doctrine

```python
# Run old doctrine in shadow mode
old_runner = ShadowModeRunner(
    decision_fn=old_engine.process_frame,
    run_name="doctrine_v2024_03",
    doctrine_version="2024-03",
)
old_runner.process_telemetry_file("prod_telemetry.jsonl")
old_summary = old_runner.finalize()

# Run new doctrine in shadow mode
new_runner = ShadowModeRunner(
    decision_fn=new_engine.process_frame,
    run_name="doctrine_v2024_04",
    doctrine_version="2024-04",
)
new_runner.process_telemetry_file("prod_telemetry.jsonl")
new_summary = new_runner.finalize()

# Compare
diff_report = generate_replay_diff(
    run_a_evidence=Path(old_summary['paths']['evidence_log']),
    run_b_evidence=Path(new_summary['paths']['evidence_log']),
)

# Analyze
if diff_report['summary']['match_rate'] > 99.5:
    print("✓ Doctrine change is compatible")
else:
    print(f"⚠ {diff_report['summary']['frames_with_differences']} frames differ")
    for mismatch in diff_report['per_frame_mismatches'][:5]:
        print(f"  Frame {mismatch['frame_index']}: {mismatch['differences']}")
```

### Example 2: Continuous Audit Trail

```python
# Process daily telemetry in shadow mode
for day in date_range:
    runner = ShadowModeRunner(
        decision_fn=engine.process_frame,
        output_dir=f"/var/audit_logs/{day}",
        run_name=f"daily_shadow_{day}",
        engine_version=current_engine_version,
    )
    
    runner.process_telemetry_file(f"/data/daily/{day}.jsonl")
    summary = runner.finalize()
    
    # Archive
    subprocess.run([
        "aws", "s3", "sync",
        str(summary['paths']['output_directory']),
        f"s3://audit-logs/{day}/"
    ])
```

### Example 3: Replay & Analyze

```python
# Replay same telemetry through multiple versions
versions = ["2.0", "2.1", "2.2"]
evidence_logs = {}

for version in versions:
    engine = load_engine(version)
    runner = ShadowModeRunner(
        decision_fn=engine.process_frame,
        run_name=f"replay_v{version}",
        engine_version=version,
    )
    runner.process_telemetry_file("replayed_telemetry.jsonl")
    summary = runner.finalize()
    evidence_logs[version] = Path(summary['paths']['evidence_log'])

# Compare v2.0 → v2.1 and v2.1 → v2.2
for i in range(len(versions) - 1):
    diff = generate_replay_diff(
        evidence_logs[versions[i]],
        evidence_logs[versions[i + 1]],
        run_a_name=f"v{versions[i]}",
        run_b_name=f"v{versions[i + 1]}",
    )
    print(f"v{versions[i]} → v{versions[i + 1]}: {diff['summary']['match_rate']}% match")
```

## Safety & Reliability

- ✅ **Read-only**: No external actions triggered
- ✅ **Error isolation**: Failed frames don't stop processing
- ✅ **Deterministic**: Same telemetry → same outputs (for comparison)
- ✅ **Auditable**: All decisions recorded with timestamps
- ✅ **Reproducible**: Config snapshot in metadata
- ✅ **Scalable**: Streaming JSONL (no memory buffering)

## Troubleshooting

### High error rate in shadow mode?

```python
# Check what's failing
summary = runner.finalize()
print(f"Error rate: {summary['summary_stats']['error_rate']}%")

# Review first error
if summary['errors']:
    error = summary['errors'][0]
    print(f"Frame {error['frame_index']}: {error['error']}")
```

### Evidence log too large?

Evidence logs can be compressed after run completion:
```bash
gzip -9 doctrine_v2024_04_evidence.jsonl
```

### Comparison showing unexpected differences?

Check that both runs used identical telemetry:
```python
# Verify frame count
with open(evidence_a) as f:
    frames_a = sum(1 for _ in f if _.strip())
with open(evidence_b) as f:
    frames_b = sum(1 for _ in f if _.strip())

assert frames_a == frames_b, f"Frame count mismatch: {frames_a} vs {frames_b}"
```

## Future Enhancements

- Real-time telemetry streaming (Kafka/MQTT)
- Interactive dashboard for evidence exploration
- Automated statistical testing (confidence intervals)
- Policy impact estimation
- Per-region/customer isolation reports

## Support

For questions or issues, see the main neraium-core documentation and issue tracker.
