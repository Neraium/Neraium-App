# Neraium Core Release Gates

This document defines **ship / no-ship policy** for the frozen Neraium Core production boundary.

## Why this exists

Neraium Core is frozen as bounded production intelligence. Releases must be blocked when replay validation shows unsafe or uncertain behavior.

## Canonical artifacts

Inspect these artifacts after every validation run:

1. `reports/validation/core_validation_report.json` (canonical release-readiness artifact)
2. `reports/validation/release_gate_report.json` (explicit gate decisions)
3. `reports/validation/real_world_validation_report.json` (full replay + evidence output)

## Release gate thresholds

Current policy (`validation/release_gates.py`) enforces:

- minimum decision accuracy: `>= 0.70`
- maximum harm rate: `<= 0.20`
- minimum calibration quality: `>= 0.65`
- maximum false-confidence rate: `<= 0.10`
- maximum drift-warning rate: `<= 0.25`
- minimum replay records: `>= 50`
- minimum domain coverage: `>= 1`
- minimum asset coverage: `>= 3`
- optional intervention-memory contribution floor (disabled by default unless explicitly set)

Regression guards against prior report:

- decision accuracy drop limit: `0.03`
- harm-rate increase limit: `0.02`
- calibration drop limit: `0.03`
- drift-warning increase limit: `0.05`

## What blocks release

Release is blocked when any gate fails, including:

- poor performance gates (accuracy/harm/calibration/false-confidence/drift)
- low-data or low-coverage gates
- regression blockers against prior canonical report

`release_recommendation` is:

- `ship` only if all gates pass
- `no-ship` if any gate fails

## Borderline interpretation

If performance gates are close to threshold and dataset gates fail, treat it as **uncertainty-driven block** (insufficient evidence), not as guaranteed model degradation.

Cohort breakdowns in `core_validation_report.json` must be reviewed to determine if failure is broad or isolated (domain/asset/sparse/drifted/intervention cohorts).

## Boundary rule

Release gates must only evaluate frozen production-core outputs. Advisory/experimental layers are out of scope and must not affect release decision logic.
