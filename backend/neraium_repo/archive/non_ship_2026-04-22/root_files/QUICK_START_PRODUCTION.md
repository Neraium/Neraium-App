# Quick Start: Production Engine

Get the Neraium Structural Engine running in 5 minutes.

## Installation

```bash
# Install the package
pip install -e .
```

## Basic Usage

```python
from neraium_core.engine.production import ProductionEngine, InputFrame

# Create engine
engine = ProductionEngine()

# Create a frame
frame = InputFrame(
    timestamp=1234567890.0,  # Unix timestamp
    unit_id="pump-47",
    sensors={
        "pressure": 100.0,
        "temperature": 65.0,
        "vibration": 0.5,
    }
)

# Process frame
result = engine.process_frame(frame)

# Use result
print(f"State: {result.state}")  # STABLE, WATCH, or ALERT
print(f"Health: {result.health_percentage}%")
print(f"Drift: {result.drift_score:.3f}")
print(f"Baseline ready: {result.baseline_ready}")
```

## Run Example

```bash
python examples/production_example.py
```

Shows processing 50 frames with synthetic sensor data and full diagnostics.

## Key Classes

### InputFrame
Input to the engine with strict schema:
```python
InputFrame(
    timestamp: float,           # Unix timestamp
    unit_id: str,              # Asset identifier
    sensors: dict[str, float]  # Sensor name → value
)
```

### EngineResult
Output from the engine:
```python
EngineResult(
    timestamp: float,          # Frame timestamp
    unit_id: str,             # Unit identifier
    frame_count: int,         # Frames processed for unit
    state: str,               # STABLE | WATCH | ALERT
    drift_score: float,       # [0.0, 1.0]
    stability_score: float,   # [0.0, 1.0]
    health_percentage: int,   # [0, 100]
    baseline_ready: bool,     # Baseline established?
    sensor_count: int,        # Number of sensors
    model_age_frames: int,    # Frames in buffer
)
```

## Configuration

### Environment Variables

All optional, sensible defaults:
```bash
export NERAIUM_BASELINE_WINDOW=24    # Frames to build baseline
export NERAIUM_RECENT_WINDOW=8       # Frames to compare
export NERAIUM_MAX_FRAMES=500        # Memory buffer size
export NERAIUM_LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Programmatic

```python
from neraium_core.engine.config import ProductionEngineConfig
from neraium_core.engine.production import ProductionEngine

config = ProductionEngineConfig(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)
engine = ProductionEngine(config=config)
```

## Operational Patterns

### Stream Processing
```python
for sensor_event in sensor_stream:
    frame = InputFrame(
        timestamp=sensor_event.time,
        unit_id=sensor_event.unit,
        sensors=sensor_event.values,
    )
    result = engine.process_frame(frame)
    
    if result.state == "ALERT":
        send_alert(result)
```

### Batch Processing
```python
frames = [InputFrame(...), InputFrame(...), ...]
batch_result = engine.process_batch(frames)

for result in batch_result.results:
    print(f"{result.unit_id}: {result.state}")
```

### Multi-Unit Monitoring
```python
engine = ProductionEngine()  # Single engine tracks multiple units

for unit_id in ["pump-1", "pump-2", "pump-3"]:
    result = engine.process_frame(InputFrame(
        timestamp=now,
        unit_id=unit_id,
        sensors=get_sensors(unit_id),
    ))
    process(result)
```

## Output States

- **STABLE**: Normal operation, no concerns
- **WATCH**: Elevated drift, monitor closely
- **ALERT**: Significant instability, action needed

## Metrics

- **drift_score** [0.0-1.0]: How far from baseline
- **stability_score** [0.0-1.0]: Internal coherence
- **health_percentage** [0-100]: Overall health

## Logging

Structured JSON logs by default:

```json
{
  "level": "INFO",
  "timestamp": "2024-04-12T10:30:45+00:00",
  "message": "Processed frame for unit pump-1: state=STABLE, drift=0.234, health=82%"
}
```

## Diagnostics

```python
diag = engine.get_diagnostics()
print(f"Units: {diag['units_tracked']}")
print(f"Memory frames: {diag['engine_frames_stored']}")
```

## Common Issues

| Problem | Solution |
|---------|----------|
| All results STABLE | Need 24+ frames (baseline warmup) |
| Too many ALERT | Increase alert_quantile, add persistence |
| Memory growing | Monitor frame_counts_by_unit |

## Performance

- **Latency**: 1-5 ms per frame
- **Throughput**: 200-1000 frames/second
- **Memory**: ~5-10 MB per unit
- **CPU**: Minimal, fully deterministic

## Full Documentation

- See `PRODUCTION_DEPLOYMENT.md` for comprehensive guide
- See `PRODUCTION_READINESS_SUMMARY.md` for implementation details

## Next Steps

1. Run the example: `python examples/production_example.py`
2. Review `PRODUCTION_DEPLOYMENT.md` for your use case
3. Integrate into your application
4. Configure logging and monitoring
5. Deploy to production

---

**Ready for production deployment**. All core requirements met: deterministic behavior, safe error handling, structured logging, strict schemas.
