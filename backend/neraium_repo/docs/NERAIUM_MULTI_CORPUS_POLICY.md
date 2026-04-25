# Neraium Core Multi-Corpus Release Policy

## Purpose
Neraium Core release validation now evaluates candidate builds across multiple corpus regimes, not a single snapshot. This strengthens release confidence under noise, adversarial conditions, and out-of-distribution transfer.

## Corpus classes
Each canonical snapshot includes:
- `corpus_type`: `baseline_clean`, `noisy_realistic`, `adversarial`, `transfer_cross_domain`
- `expected_difficulty`: qualitative difficulty label
- `coverage_tags`: interpretable scenario tags

## Release policy across corpora
Per-corpus gates are computed with corpus-specific thresholds in `validation/release_policy.py`.

Class-level policy:
- `baseline_clean`: required, zero failures tolerated
- `noisy_realistic`: required, zero failures tolerated
- `adversarial`: bounded degradation tolerated (`max_failure_ratio=0.34`), catastrophic safety/calibration failures block
- `transfer_cross_domain`: required, catastrophic transfer failures block

Overall release decision:
- fail if any required corpus class is missing or blocked
- fail if blocking corpus classes exist
- output includes per-corpus pass/fail, blocking classes, and failing corpora

## Adversarial/OOD design
Adversarial snapshots (deterministic, interpretable):
1. Misleading stability
2. Lookalike divergence
3. Intervention reversal
4. False recovery
5. Sparse misleading data
6. Conflicting signals

Transfer snapshots:
- cross-domain small-scale systems
- cross-domain large-scale/noisy systems

## Failure interpretation
Failed gates map to failure modes:
- `minimum_decision_accuracy` -> `trajectory_misclassification`
- `maximum_harm_rate` -> `intervention_ranking_error`
- calibration gates -> `calibration_failure`
- domain/asset coverage failures -> `attribution_error`
- any transfer corpus failures additionally -> `transfer_failure`

Release reports aggregate failure frequency and top recurring failure modes.

## Workflow changes
`tools/run_release_candidate.py` now supports:
- `--corpus-id <id>` (single)
- `--corpus-set <comma-separated ids/types>` (multi)

Example:
```bash
python tools/run_release_candidate.py --corpus-set baseline_clean,adversarial,noisy_realistic,transfer_cross_domain
```

Outputs:
- per-corpus run artifacts under `release_candidate_runs/<corpus_id>/`
- aggregate multi-corpus report (`multi_corpus_release_report.json`)
- status: `RELEASE_PASS` or `RELEASE_FAIL`

## Trend tracking
`validation/history/trends.py` now emits:
- `trend_summary.json` (legacy)
- `multi_corpus_trend_summary.json` with per-corpus accuracy/harm/pass-fail and cross-corpus stability statistics

## Current limitations
- corpus size remains intentionally small for reproducible CI
- adversarial/OOD diversity is scenario-based, not sourced from real production drift logs
- thresholds are policy defaults and should be tuned with larger historical validation archives

## Next step
Expand with real-world anonymized telemetry slices per domain/system type, then calibrate class-specific thresholds using empirical release outcomes and post-release incident feedback.
