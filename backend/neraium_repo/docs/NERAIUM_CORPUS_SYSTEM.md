# Neraium Core Corpus Snapshot & Release-Candidate System

## Overview
A **corpus snapshot** is an immutable, versioned definition of the validation dataset and ingestion configuration used for replay validation.

This system ensures every validation decision answers:
- What corpus was used?
- When was it run?
- Did it pass release gates?

## Directory layout
- `validation/corpus/registry.json`: canonical corpus registry.
- `validation/corpus/snapshots/*.json`: immutable snapshot definitions.
- `validation/corpus/snapshots/data/*`: local dataset files for snapshots.
- `reports/validation/history/`: per-run artifacts + `index.json` + trends output.
- `validation/history/trends.py`: trend analysis utility.

## Snapshot schema
Each snapshot includes:
- `corpus_id`
- `description`
- `created_at`
- `schema_version`
- `source_datasets`
- `metadata_summary`
  - `domain_coverage`
  - `system_types`
  - `number_of_trajectories`
  - `intervention_coverage`
- `ingestion_parameters`
- `quality_requirements`
  - `min_dataset_size`
  - `min_intervention_coverage`
  - `min_domain_diversity`
- `data_files`
  - file `path`
  - `format`
  - `sha256`

## Running validation with a corpus snapshot
```bash
python tools/run_validation.py --corpus-id corpus_v1 --write-history
```

`run_metadata` is embedded in `core_validation_report.json` and `release_gate_report.json` with:
- `corpus_id`
- `run_id`
- `timestamp`
- `code_version` (git commit hash when available)
- `config_hash`
- `canonical_run`

## Non-canonical fallback
Raw input mode is still supported:
```bash
python tools/run_validation.py --input path/to/data.json --format json
```

These runs are tagged `corpus_id=non_canonical` and annotated with `non_canonical_reason=raw_input_mode`.

## Release-candidate workflow
Use:
```bash
python tools/run_release_candidate.py --corpus-id corpus_v1
```

This executes replay + release gate evaluation and prints:
- `RELEASE_PASS` or `RELEASE_FAIL`
- blocking reasons
- summary metrics

## Scheduling
Use cron-compatible runner:
```bash
CORPUS_IDS="corpus_v1" tools/schedule_release_evaluation.sh
```

It runs selected corpora and updates:
- history artifacts under `reports/validation/history/`
- trend output at `reports/validation/history/trend_summary.json`

## Regression baselines
Baselines are selected per `corpus_id`:
1. explicitly marked baseline run (`--mark-baseline`), else
2. latest passing run for that corpus.

Regression comparison always uses baseline from the same corpus.

## History & trends
`reports/validation/history/index.json` stores each run with:
- corpus/run IDs and timestamp
- release result
- summary metrics
- artifact paths

`validation/history/trends.py` computes:
- accuracy trend
- harm-rate trend
- calibration trend
- release-gate pass rate
- regression frequency

## Corpus quality enforcement
Canonical runs are blocked before validation when quality fails:
- dataset size below threshold
- intervention coverage below threshold
- domain diversity below threshold

Blocked runs are reported as `insufficient_corpus_quality` and do not ship.

## Limitations
- Snapshot creation is currently manual JSON authoring.
- Quality metadata quality depends on source dataset annotation completeness.
- Local file-based history is simple and reproducible but not multi-user transactional.

## Next scale step (optional)
Add a signed snapshot promotion workflow (staging -> production corpus registry) and remote artifact store with immutable object versions.
