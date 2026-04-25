# Raw Industrial Data Ingestion

Neraium now has a canonical raw-data ingestion bridge that converts messy raw telemetry into runtime-ready structural frames.

## Supported raw input shapes

- **Tabular time-series** (`.csv` or `.json` rows): each row is a timestep, schema-discovered into metadata vs sensor columns.
- **Directory timestep files** (`.json`/`.csv`): each file can contain a single timestep row, schema-discovered just like tabular input.
- **Directory signal blocks** (`.csv`/`.txt`/`.npy`/`.npz`/`.json` arrays): each file is treated as a timestep/window block and converted to a feature vector through waveform preprocessing.

## What the ingestion layer reports

For every run, diagnostics include:

- `detected_input_type`
- `timestep_count`
- `sensor_count`
- `preprocessing_mode`
- `has_valid_signals`
- `sensor_columns`
- `metadata_columns`
- `warnings`

## Validation mode (small sample)

Run a small subset before longer processing:

```bash
python tools/run_raw_data.py \
  --input /path/to/raw/input \
  --output reports/raw_validation.json \
  --preprocessing-mode auto \
  --validation-sample-size 25
```

## Full processing on raw input

```bash
python tools/run_raw_data.py \
  --input /path/to/raw/input \
  --output reports/raw_full.json \
  --preprocessing-mode auto
```

Both commands execute through `StructuralMonitoringService.ingest_raw_industrial_data`, so this is the real runtime path (not a standalone demo converter).
