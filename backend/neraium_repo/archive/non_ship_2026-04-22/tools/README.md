# Tools Directory Guide

`tools/` contains task-specific operational scripts. Use this index before adding new scripts.

## Categories

### Demo runners

- `run_canonical_demo.py`
- `run_operator_workflow_demo.py`
- `run_realtime_demo.py`
- `run_raw_telemetry_demo.py`
- `run_proof_package.py`

### Evaluation / validation

- `run_evaluation.py`
- `run_validation.py`
- `evaluate_pipeline.py`
- `evaluate_onset_calibration.py`
- `evaluate_temporal_perturbations.py`
- `evaluate_temporal_alignment_impact.py`

### Benchmark generation

- `generate_synthetic_bench.py`
- `generate_synthetic_temporal_bench.py`
- `run_synthetic_bench.py`
- `benchmark_incremental.py`

### Diagnostics / plotting

- `plot_temporal_diagnostics.py`
- `plot_state_space.py`
- `plot_state_graph.py`
- `plot_geometry_diagnostics.py`
- `plot_signal_degradation.py`
- `debug_representation.py`
- `debug_temporal_representation.py`

### Data adapters / conversion

- `convert_raw_telemetry_to_structural_csv.py`
- `run_raw_data.py`
- `inspect_raw_telemetry_features.py`
- `replay_fixtures.py`

## Script placement convention

- Put new runnable scripts in `tools/` unless they are tightly scoped to an example (`examples/`) or package module (`neraium_core/`).
- Keep each script focused on one workflow.
- Prefer composable helper functions over monolithic script blocks to make migration into library code easier.
