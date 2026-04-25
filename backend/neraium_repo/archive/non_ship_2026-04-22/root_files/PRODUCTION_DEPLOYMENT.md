# Neraium Structural Engine - Production Deployment Guide

## Overview

The Neraium Structural Engine is a deterministic system for continuous monitoring of structural drift and instability in multivariate systems. This guide covers production deployment, configuration, and operation.

## What the Engine Does

The engine:
- **Ingests multivariate sensor data** from industrial systems
- **Builds a baseline model** from early frames to understand "normal" structure
- **Computes structural drift** by comparing recent data geometry to baseline
- **Tracks state transitions** (STABLE → WATCH → ALERT) based on calibrated thresholds
- **Returns deterministic, explainable metrics** (no black-box ML)

### Output States

- **STABLE**: System operating within normal structural parameters
- **WATCH**: Elevated drift detected, system may be degrading
- **ALERT**: Significant structural instability detected, action recommended

### Key Metrics

- **drift_score** [0.0-1.0]: How far the current structure has drifted from baseline
- **stability_score** [0.0-1.0]: Measure of internal structural coherence
- **health_percentage** [0-100]: Overall system health indicator

## Production Architecture

```
Input (sensors)
    ↓
[Strict Schema Validation]
    ↓
[StructuralEngine]
    ├─ Baseline model (first 24 frames)
    ├─ Drift computation (covariance + Mahalanobis)
    └─ State machine (with persistence)
    ↓
[Strict Output Validation]
    ↓
Output (result with state, scores, health)
```

## Getting Started

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Basic Usage

```python
from neraium_core.engine.production import ProductionEngine, InputFrame

# Create engine (uses defaults or env vars)
engine = ProductionEngine()

# Process a frame
frame = InputFrame(
    timestamp=1234567890.0,  # Unix timestamp
    unit_id="turbine-001",
    sensors={
        "vibration": 0.5,
        "temperature": 65.0,
        "pressure": 100.0,
    }
)

result = engine.process_frame(frame)
print(f"State: {result.state}")
print(f"Health: {result.health_percentage}%")
print(f"Drift: {result.drift_score:.3f}")
```

### 3. Run Example

```bash
python examples/production_example.py
```

## Configuration

### Environment Variables

The engine reads configuration from environment variables. All have safe defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `NERAIUM_BASELINE_WINDOW` | 24 | Frames to build initial baseline model |
| `NERAIUM_RECENT_WINDOW` | 8 | Frames to compare against baseline |
| `NERAIUM_MAX_FRAMES` | 500 | Maximum frames to keep in memory |
| `NERAIUM_LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `NERAIUM_LOG_TIMESTAMPS` | 1 | Include timestamps in logs |
| `NERAIUM_LOG_CALLER` | 1 | Include caller location in logs |

### Programmatic Configuration

```python
from neraium_core.engine.config import ProductionEngineConfig
from neraium_core.engine.production import ProductionEngine

config = ProductionEngineConfig(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
    mahal_weight=0.65,
    cov_weight=0.35,
)
config.validate()

engine = ProductionEngine(config=config)
```

## Input Format

### InputFrame Schema

Each frame must have:

```python
frame = InputFrame(
    timestamp: float,           # Unix timestamp (seconds)
    unit_id: str,              # Unique identifier for the asset
    sensors: dict[str, float]  # Sensor name → value mapping
)
```

**Validation rules:**
- `timestamp` must be a positive number
- `unit_id` must be a non-empty string
- `sensors` must be a non-empty dict
- All sensor values must be numbers (not NaN)

**Example:**
```python
InputFrame(
    timestamp=1704067200.0,  # 2024-01-01 00:00:00 UTC
    unit_id="pump-47",
    sensors={
        "inlet_pressure": 15.2,
        "outlet_pressure": 28.5,
        "temperature": 72.3,
        "vibration": 0.18,
    }
)
```

## Output Format

### EngineResult Schema

The engine returns results with this structure:

```python
result = EngineResult(
    timestamp: float,           # Frame timestamp
    unit_id: str,              # Unit identifier
    frame_count: int,          # Total frames processed for this unit
    state: str,                # STABLE, WATCH, or ALERT
    drift_score: float,        # [0.0, 1.0]
    stability_score: float,    # [0.0, 1.0]
    health_percentage: int,    # [0, 100]
    baseline_ready: bool,      # True when baseline is established
    sensor_count: int,         # Number of sensors
    model_age_frames: int,     # Frames in engine buffer
)
```

**Example output:**
```python
EngineResult(
    timestamp=1704067200.0,
    unit_id="pump-47",
    frame_count=42,
    state="STABLE",
    drift_score=0.23,
    stability_score=0.87,
    health_percentage=82,
    baseline_ready=True,
    sensor_count=4,
    model_age_frames=42,
)
```

## Operational Patterns

### Pattern 1: Stream Processing

Process frames as they arrive from sensors:

```python
engine = ProductionEngine()

def on_sensor_data(timestamp, unit_id, sensors):
    frame = InputFrame(timestamp=timestamp, unit_id=unit_id, sensors=sensors)
    result = engine.process_frame(frame)
    
    # Use result
    if result.state == "ALERT":
        send_alert(unit_id, result)
    
    # Store for reporting
    log_result(result)
```

### Pattern 2: Batch Processing

Process historical or batched data:

```python
engine = ProductionEngine()

frames = [
    InputFrame(timestamp=t, unit_id=unit, sensors=s)
    for t, unit, s in load_historical_data()
]

batch_result = engine.process_batch(frames)

for result in batch_result.results:
    print(f"{result.unit_id}: {result.state}")

if batch_result.errors:
    print(f"Errors: {len(batch_result.errors)}")
```

### Pattern 3: Multi-Unit Monitoring

The engine automatically isolates state per unit:

```python
engine = ProductionEngine()

for event in event_stream:
    frame = InputFrame(
        timestamp=event.timestamp,
        unit_id=event.unit_id,  # Different units are tracked separately
        sensors=event.sensors,
    )
    result = engine.process_frame(frame)
```

## Performance Characteristics

### Memory

- **Per-unit memory**: ~5-10 MB with default config (500 frame buffer)
- **100 units**: ~500 MB - 1 GB total
- Memory is capped and doesn't grow unbounded

### CPU

- **Per-frame latency**: 1-5 ms typical
- **Throughput**: ~200-1000 frames/second single-threaded
- Fully deterministic, no variance from randomness

### Latency

- **Warmup period**: First 24 frames (baseline building)
- **Alert response**: 2-5 frames after instability begins (configurable)

## Error Handling

The engine is designed to degrade gracefully:

- **Invalid frame**: Raises `ValueError`, frame is skipped
- **Processing error**: Returns safe "STABLE" result with default health
- **Missing sensors**: Handles gracefully, adjusts analysis
- **Out-of-order data**: Maintains internal consistency

Example:
```python
try:
    result = engine.process_frame(frame)
except ValueError as e:
    # Frame schema violation
    log_error(f"Invalid frame: {e}")
    # Continue processing other frames
```

## Monitoring and Diagnostics

### Engine Diagnostics

```python
diag = engine.get_diagnostics()
print(f"Units tracked: {diag['units_tracked']}")
print(f"Frames in buffer: {diag['engine_frames_stored']}")
print(f"Frame counts: {diag['frame_counts_by_unit']}")
```

### Logging

Structured logging is enabled by default:

```
[INFO] Processed frame for unit turbine-001: state=STABLE, drift=0.234, health=82%
[INFO] Processed batch: 1000 successful, 0 errors, time=4.234s
```

Configure logging level:
```bash
export NERAIUM_LOG_LEVEL=DEBUG
```

## Scaling Recommendations

### Single-Node Deployment

- **Capacity**: 50-200 units
- **Frame rate**: 1-10 frames/sec per unit
- **Hardware**: 2-4 CPU cores, 2-4 GB RAM

### Multi-Node Deployment

For larger deployments:
- Create one engine per process/container
- Use load balancing to distribute units across engines
- Each engine maintains independent state per unit
- No cross-engine state sharing required

Example:
```
Load Balancer
├─ Node 1 (Engine 1): units 1-50
├─ Node 2 (Engine 2): units 51-100
└─ Node 3 (Engine 3): units 101-150
```

## Troubleshooting

### Issue: All results are STABLE

**Possible causes:**
- Baseline not yet built (need 24+ frames)
- Sensors have constant value (no variation)
- Threshold config too loose

**Solution:**
```python
result = engine.get_diagnostics()
print(f"Baseline ready: {result.baseline_ready}")
print(f"Model age: {result.model_age_frames}")
```

### Issue: Too many false positives (ALERT)

**Solutions:**
1. Increase baseline window (more history for better model)
2. Increase watch/alert persistence (require sustained signal)
3. Collect more data before deploying (better baseline)

### Issue: Memory usage growing

**Check:**
```python
diag = engine.get_diagnostics()
print(f"Frames stored: {diag['engine_frames_stored']}")
```

**Solutions:**
1. Reduce `NERAIUM_MAX_FRAMES` if not needed for historical analysis
2. Monitor for stuck units (units not processing new frames)

## Production Checklist

Before deploying to production:

- [ ] Run `examples/production_example.py` successfully
- [ ] Test with your actual sensor data (5+ units recommended)
- [ ] Validate that alert thresholds match business requirements
- [ ] Set up log aggregation (structured JSON logs)
- [ ] Configure monitoring of `engine.get_diagnostics()`
- [ ] Have runbook for common alerts
- [ ] Document alert response procedures
- [ ] Test graceful shutdown and restart
- [ ] Verify memory usage under expected load
- [ ] Set up health checks (engine should return non-error results)

## Support and Troubleshooting

### Common Questions

**Q: Can I change baseline window mid-stream?**
A: No, create a new engine instance with new config.

**Q: How do I reset a unit's state?**
A: Create a new engine. Unit state is isolated within an engine instance.

**Q: What if a sensor goes offline?**
A: The engine detects missing sensors and adjusts analysis (returns safe defaults if needed).

**Q: Can I use old timestamps?**
A: Yes, timestamps are absolute (Unix seconds), not relative to current time.

### Debug Mode

For detailed diagnostics:

```python
from neraium_core.engine.config import ProductionLoggingConfig
from neraium_core.engine.logging_setup import setup_logging

logging_config = ProductionLoggingConfig(level="DEBUG")
logger = setup_logging(logging_config)

engine = ProductionEngine(logging_config=logging_config)
```

## References

- **Core Algorithm**: Structural drift computed via normalized covariance + Mahalanobis distance
- **State Machine**: Watch/Alert states use configurable persistence (default: 5/3 frames)
- **Calibration**: Alert thresholds calibrated from first 28 baseline frames
- **Memory**: Fixed-size ring buffers, maximum bounded by `max_frames` config

## Version Info

- **Neraium Core**: See `neraium_core.__version__`
- **Python**: 3.9+
- **Dependencies**: numpy, dataclasses (builtin 3.7+)

---

**Last Updated**: 2024
**Status**: Production Ready
