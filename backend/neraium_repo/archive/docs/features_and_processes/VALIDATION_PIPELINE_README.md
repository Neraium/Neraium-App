# Local Validation Pipeline

Automated validation pipeline for processing local datasets (FD001, FD004, IMS, igrow) and generating comprehensive evidence packages with metrics and visualizations.

## Overview

The validation pipeline provides a single repeatable command to:
- Process local result datasets
- Compute benchmark metrics (unit counts, lead times, percentiles)
- Generate representative plots (best, median, worst cases)
- Produce a summary report with key findings

## Quick Start

### Basic Usage (Auto-Detection)

```bash
python scripts/run_full_validation.py
```

The script automatically discovers CSV files in common locations:
- Current directory
- `./data/`
- `~/data/`
- `~/Downloads/`

### Custom Paths

Specify explicit paths to your datasets:

```bash
python scripts/run_full_validation.py \
  --fd001-path ~/data/FD001_results.csv \
  --fd004-path ./FD004_ims_policy_results.csv \
  --ims-path ./IMS_production_results_final.csv \
  --igrow-path ~/data/igrow_results.csv \
  --output-dir ./results \
  --drift-threshold 0.5
```

### Dry Run

Preview what would be processed without running:

```bash
python scripts/run_full_validation.py --dry-run
```

### Process Specific Datasets

Only process selected datasets:

```bash
python scripts/run_full_validation.py --datasets fd001 fd004
```

## Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--fd001-path` | Path | auto-discover | Path to FD001 results CSV |
| `--fd004-path` | Path | auto-discover | Path to FD004 results CSV |
| `--ims-path` | Path | auto-discover | Path to IMS results CSV |
| `--igrow-path` | Path | auto-discover | Path to igrow results CSV |
| `--output-dir` | Path | `validation_output` | Output directory for results |
| `--drift-threshold` | Float | `0.5` | Structural drift score threshold for early signal |
| `--datasets` | List | all | Datasets to process (e.g., `fd001 fd004`) |
| `--dry-run` | Flag | `False` | Show what would be processed |

## Output Structure

```
validation_output/
├── fd001/
│   ├── stats.csv                      # Summary statistics
│   ├── lead_time_summary.csv          # Per-unit lead times
│   └── plots/
│       ├── fd001_best_case.png        # Best case plot
│       ├── fd001_median_case.png      # Median case plot
│       └── fd001_worst_case.png       # Worst case plot
├── fd004/
│   ├── stats.csv
│   ├── lead_time_summary.csv
│   └── plots/
├── ims/
│   ├── stats.csv
│   ├── lead_time_summary.csv
│   └── plots/
├── igrow/
│   ├── stats.csv
│   ├── lead_time_summary.csv
│   └── plots/
└── validation_report.md               # Comprehensive report
```

## Output Files

### stats.csv

Summary statistics for each dataset:

| Column | Description |
|--------|-------------|
| `dataset` | Dataset name |
| `unit_count` | Number of units in dataset |
| `mean_lead_time` | Average lead time across all units |
| `median_lead_time` | Median lead time |
| `pct_units_gt_50_cycles` | % of units with >50 cycles lead time |
| `pct_units_gt_100_cycles` | % of units with >100 cycles lead time |
| `best_case_unit` | Unit ID with shortest lead time |
| `best_case_lead_time` | Lead time of best case unit |
| `worst_case_unit` | Unit ID with longest lead time |
| `worst_case_lead_time` | Lead time of worst case unit |
| `median_case_unit` | Unit ID at 50th percentile |
| `median_case_lead_time` | Lead time of median case unit |
| `total_records` | Total data records processed |

### lead_time_summary.csv

Per-unit breakdown with case classifications:

| Column | Description |
|--------|-------------|
| `unit` | Unit identifier |
| `lead_time` | Lead time in cycles |
| `total_cycles` | Total cycles in dataset |
| `is_best_case` | Boolean: unit is best case |
| `is_median_case` | Boolean: unit is median case |
| `is_worst_case` | Boolean: unit is worst case |

### Plots (PNG)

Three plots per dataset showing:
- **Structural Drift Score**: Primary degradation indicator (blue line)
- **Relational Instability Score**: Secondary indicator (orange line)
- **Early Signal Threshold**: Drift threshold line (red dashed)
- **Failure Point**: End-of-life marker (dark red dotted)
- **End of Run**: Data end marker (gray dotted)

#### Best Case
Unit with shortest lead time (fastest degradation detection).

#### Median Case
Unit at 50th percentile of lead time distribution (typical behavior).

#### Worst Case
Unit with longest lead time (slowest degradation, most tolerance).

### validation_report.md

Comprehensive markdown report with:
- Processing status summary
- Overall benchmark metrics table
- Per-dataset detailed statistics
- Plot descriptions
- Methodology notes

## Metrics Explained

### Lead Time

Lead time is calculated as the number of cycles from when the structural drift score first exceeds the configured threshold until the end of the dataset.

If the drift score never exceeds the threshold, lead time equals the total number of cycles.

```
lead_time = last_cycle - first_exceeded_cycle + 1
```

where `first_exceeded_cycle` is when `structural_drift_score >= drift_threshold`.

### Percentiles

- `>50 cycles`: % of units where lead time exceeds 50 cycles
- `>100 cycles`: % of units where lead time exceeds 100 cycles

These indicate distribution of early warning capability.

## Data Format Requirements

The pipeline auto-detects and normalizes several data formats:

### FD Datasets (FD001, FD004)

Required columns:
- `unit`: Unit identifier (int)
- `cycle`: Cycle number (int)

Recommended columns:
- `structural_drift_score`: Drift score (0-1)
- `failure_cycle`: Cycle at failure (int)
- `lead_time_hours` or `alert_lead`: Pre-computed lead time

### IMS Dataset

Required columns:
- `t` or `time`: Time step (int)
- `file_name` or equivalent unit identifier

Recommended columns:
- `drift_smooth`: Smoothed drift score
- `state`: System state (STABLE, DEGRADED, etc.)

### Generic Datasets

Minimal requirements:
- `unit`: Unit identifier
- `cycle` or `time`: Time dimension
- Any column with "drift" in the name

Missing columns are auto-generated or set to defaults.

## Configuration

Create a `validation_config.json` in the repo root for persistent defaults:

```json
{
  "fd001_path": "/path/to/FD001_results.csv",
  "fd004_path": "./FD004_ims_policy_results.csv",
  "ims_path": "./IMS_production_results_final.csv",
  "output_dir": "./validation_output",
  "drift_threshold": 0.5
}
```

Then run without arguments:

```bash
python scripts/run_full_validation.py
```

(Note: Config file support can be added if needed.)

## Testing

Run the test suite:

```bash
pytest tests/test_local_validation_pipeline.py -v
```

Tests cover:
- Path discovery and configuration
- Data loading for multiple formats
- Metric computation
- Plot generation
- Report generation
- Error handling for missing datasets

## Troubleshooting

### "Dataset not found"

The script couldn't auto-discover your CSV file. Specify it explicitly:

```bash
python scripts/run_full_validation.py --fd004-path /absolute/path/to/FD004_results.csv
```

### "Missing required columns"

Your CSV doesn't have the expected columns. Check:
1. Column names are correct (case-sensitive)
2. Dataset type is correctly inferred
3. Consider using `--dry-run` to see what was discovered

### Plots not generated

This usually means the dataset is missing `structural_drift_score` or equivalent column. The pipeline will skip plot generation and continue.

### Report is empty

No datasets were successfully processed. Run with `--dry-run` to see discovery status.

## Architecture

The pipeline is organized into modules:

- **config.py**: CLI arguments, auto-discovery, configuration
- **loaders.py**: Dataset loading and normalization for different formats
- **metrics.py**: Lead time and benchmark metric computation
- **plots.py**: Matplotlib-based visualization generation
- **report.py**: Markdown report generation

No core engine dependencies; purely uses pandas, numpy, and matplotlib.

## Production Use

The pipeline is designed for batch processing and automation:

- **Deterministic**: Same inputs always produce same outputs
- **Robust**: Missing datasets are skipped; partial success is acceptable
- **Clear output**: All files are human-readable CSVs and PNGs
- **Logging**: Status messages indicate processing flow

Schedule with cron:

```bash
0 2 * * * cd /path/to/neraium-core && python scripts/run_full_validation.py >> validation_logs/$(date +\%Y\%m\%d).log 2>&1
```

## Adding New Datasets

To add support for a new dataset type:

1. Create a loader class in `loaders.py` inheriting from `DatasetLoader`
2. Implement the `load()` method to normalize columns
3. Update `load_dataset()` to route to your loader
4. Update `discover_local_paths()` patterns if needed

Example:

```python
class MyDatasetLoader(DatasetLoader):
    @staticmethod
    def load(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        # Normalize columns
        if "my_drift_col" in df.columns:
            df["structural_drift_score"] = df["my_drift_col"]
        return df
```

Then in `load_dataset()`:

```python
elif dataset_type == "my_dataset":
    return MyDatasetLoader.load(path)
```

## License

This pipeline is part of neraium-core. See LICENSE for details.
