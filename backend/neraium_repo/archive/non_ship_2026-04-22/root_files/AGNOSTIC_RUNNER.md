# Neraium Agnostic Runner

A unified, pluggable interface for running Neraium's structural intelligence engine on **any data source** and **any output destination**, with **any engine configuration**.

## Why Agnostic?

Traditional runners are locked to specific data formats and outputs. The agnostic runner decouples:

1. **Data sources** (CSV, Kafka, APIs, databases)
2. **Engine configuration** (production, research, experimental)
3. **Output sinks** (JSON, Kafka, databases, webhooks)

This means you define the flow once in a configuration file and reuse it across environments, datasets, and platforms.

## Quick Start

### 1. List available adapters

```bash
python -m neraium_core.agnostic_runner list-adapters
```

### 2. Generate a configuration

```bash
python -m neraium_core.agnostic_runner generate-config \
  --template csv-to-json \
  --output config.yaml
```

### 3. Run

```bash
python -m neraium_core.agnostic_runner run --config config.yaml
```

## Configuration

All configurations follow a simple YAML or JSON structure:

```yaml
data_source:
  type: csv                          # Data source type
  config:
    path: data.csv
    timestamp_col: timestamp
    unit_id_col: unit_id
    sensor_prefix: sensor_

output_sink:
  type: json                         # Output destination type
  config:
    path: results.json

engine:
  mode: production                   # Engine operating mode
  enable_trajectory_memory: true
  enable_advisory_layers: true
  # ... other component toggles
```

## Supported Adapters

### Data Sources

| Adapter | Use Case | Config |
|---------|----------|--------|
| **csv** | Batch processing | CSV file path, column mappings |
| **kafka** | Real-time streaming | Topic, brokers, consumer group |
| **api** | Polling external sources | URL, poll interval, headers |

### Output Sinks

| Adapter | Use Case | Config |
|---------|----------|--------|
| **json** | Single batch result | Output file path |
| **jsonl** | Streaming results | Output file path (one JSON per line) |
| **kafka** | Event streaming | Topic, brokers, partitioning |
| **database** | Long-term storage | Connection string, table name |
| **webhook** | Trigger integrations | URL, retry policy, batching |

## Example Use Cases

### Batch Processing: CSV → JSON

```yaml
data_source:
  type: csv
  config:
    path: historical_data.csv

output_sink:
  type: json
  config:
    path: results.json

engine: production
```

**Run:**
```bash
python -m neraium_core.agnostic_runner run --config csv-to-json.yaml
```

### Real-Time Streaming: Kafka → Kafka

```yaml
data_source:
  type: kafka
  config:
    brokers: [kafka1:9092, kafka2:9092]
    topic: sensor-data
    group_id: neraium-runner

output_sink:
  type: kafka
  config:
    brokers: [kafka1:9092, kafka2:9092]
    topic: neraium-results

engine: production
```

### API Polling: API → Database

```yaml
data_source:
  type: api
  config:
    url: http://localhost:8000/api/frames
    poll_interval_ms: 1000

output_sink:
  type: database
  config:
    connection_string: postgresql://user:pass@localhost/neraium
    table_name: results

engine: research_assistive
```

### Event Streaming: CSV → Webhook

```yaml
data_source:
  type: csv
  config:
    path: data.csv

output_sink:
  type: webhook
  config:
    url: https://your-api.example.com/webhooks/neraium
    batch_size: 5
    retry_count: 3

engine: production
```

## Engine Modes

| Mode | Use | Components |
|------|-----|-----------|
| **production** | Deployment, standard use | Core + trajectory + advisory |
| **research_assistive** | Analysis, optimization | All production + law extraction + transfer |
| **experimental** | R&D, novel methods | All components + experimental layers |
| **minimal** | Speed, minimal overhead | Core only |

## CLI Commands

### run

Execute with a configuration file.

```bash
python -m neraium_core.agnostic_runner run \
  --config config.yaml \
  --run-id my-run-123 \
  --error-handler log \
  --output-metrics metrics.json
```

**Options:**
- `--config` (required): Configuration file (YAML or JSON)
- `--run-id`: Unique run identifier (auto-generated if not provided)
- `--error-handler`: How to handle frame errors (log, raise, skip)
- `--output-metrics`: Write run metrics to JSON file

### list-adapters

Show all available data sources and output sinks.

```bash
python -m neraium_core.agnostic_runner list-adapters
```

### generate-config

Create a template configuration.

```bash
python -m neraium_core.agnostic_runner generate-config \
  --template csv-to-json \
  --output my-config.yaml
```

**Templates:**
- `csv-to-json`: Simple batch processing
- `api-to-kafka`: Real-time streaming
- `full-featured`: All options and explanations

## Python API

Use the agnostic runner programmatically:

```python
from neraium_core.agnostic_runner import AgnosticRunner, EngineConfig
from neraium_core.agnostic_runner.adapters import CsvDataSource, JsonFileSink

# Create adapters
source = CsvDataSource({"path": "data.csv"})
sink = JsonFileSink({"path": "results.json"})

# Configure engine
engine_config = EngineConfig.production()

# Create and run
runner = AgnosticRunner(
    data_source=source,
    output_sink=sink,
    engine_config=engine_config,
    error_handler="log",
)

metrics = runner.run()

print(f"Processed {metrics.frame_count} frames in {metrics.elapsed_seconds:.2f}s")
print(f"Throughput: {metrics.frames_per_second:.2f} frames/sec")
```

## Configuration Files

### YAML Format (Recommended)

```yaml
data_source:
  type: csv
  config:
    path: data.csv

output_sink:
  type: json
  config:
    path: results.json

engine:
  mode: production
  enable_trajectory_memory: true
  enable_advisory_layers: true
```

### JSON Format

```json
{
  "data_source": {
    "type": "csv",
    "config": {
      "path": "data.csv"
    }
  },
  "output_sink": {
    "type": "json",
    "config": {
      "path": "results.json"
    }
  },
  "engine": "production"
}
```

## Frame Format

All adapters work with a canonical frame format:

```python
{
    "timestamp": float,        # Unix timestamp
    "unit_id": str,            # Equipment/site identifier
    "sensors": {               # Sensor readings
        "temp": 25.0,
        "pressure": 101.5,
        ...
    },
    "metadata": {}             # Optional: any extra fields
}
```

## Output Format

Each result contains:

```python
{
    "timestamp": float,
    "unit_id": str,
    "sensors": {...},
    "output": {                # Engine output
        "state": "STABLE",
        "risk_level": "LOW",
        "structural_drift_score": 0.12,
        ...
    }
}
```

## Error Handling

Three strategies for frame processing errors:

1. **log** (default): Log error and continue
2. **skip**: Silently skip errors
3. **raise**: Stop on first error

```bash
python -m neraium_core.agnostic_runner run \
  --config config.yaml \
  --error-handler skip
```

## Performance

### Throughput

Typical performance on modern hardware:

| Configuration | Frames/sec |
|---------------|-----------|
| Minimal engine | 100-200 |
| Production | 50-100 |
| Research | 20-50 |

### Optimization Tips

1. **Batch operations**: Use `batch_size` for database and webhook sinks
2. **Minimize components**: Use `minimal` mode if features aren't needed
3. **Sample data**: Use `max_records` for Kafka, `max_polls` for APIs
4. **JSONL output**: Use JSONL for large result sets (streams instead of buffering)

## Examples

See `neraium_core/agnostic_runner/examples/` for complete examples:

- `csv-to-json.yaml` — Batch CSV processing
- `api-to-kafka.yaml` — Real-time API polling
- `kafka-to-database.yaml` — Kafka to SQL database
- `csv-to-webhook.yaml` — Webhook integration
- `full-featured.json` — All options explained

```bash
# View examples
ls neraium_core/agnostic_runner/examples/

# Generate from template
python -m neraium_core.agnostic_runner generate-config \
  --template csv-to-json \
  --output my-config.yaml
```

## Extending the Runner

### Custom Data Source

```python
from neraium_core.agnostic_runner.adapters import DataSourceAdapter, Frame

class MyDataSource(DataSourceAdapter):
    def validate(self) -> bool:
        # Check if source is accessible
        return True
    
    def read_frames(self):
        # Yield Frame objects
        yield Frame(
            timestamp=1.0,
            unit_id="unit1",
            sensors={"temp": 25.0}
        )

# Register it
from neraium_core.agnostic_runner.adapters.registry import register_adapter

register_adapter("source", "my_source", MyDataSource)
```

### Custom Output Sink

```python
from neraium_core.agnostic_runner.adapters import OutputSink, Result

class MySink(OutputSink):
    def write_result(self, result: Result) -> None:
        # Write result somewhere
        pass
    
    def finalize(self):
        # Cleanup and return summary
        return {"status": "done"}

register_adapter("sink", "my_sink", MySink)
```

## Troubleshooting

### "Unknown adapter" Error

```bash
python -m neraium_core.agnostic_runner list-adapters
```

Verify your adapter type is in the list.

### CSV Parsing Errors

- Check column names match configuration
- Verify sensor columns have the correct prefix
- Ensure timestamp column contains numeric values

### Kafka Connection Issues

- Verify broker addresses and ports
- Check topic exists
- Confirm network connectivity

### Database Errors

- Verify connection string format
- Ensure database server is running
- Check user permissions

## See Also

- [Examples](neraium_core/agnostic_runner/examples/README.md)
- [API Reference](neraium_core/agnostic_runner/)
- [Configuration Guide](neraium_core/agnostic_runner/examples/README.md)
- [Main README](README.md)
