# Tetrahedral State Model (Read-Only Layer)

This document describes the additive tetrahedral state payload integrated into `StructuralEngine`.

## Purpose

The tetrahedral state is an **output-only interpretive layer**. It does not change:

- alerting
- policy state
- scoring
- thresholds
- decision behavior

It maps existing runtime metrics to a deterministic four-axis simplex-like representation.

## Inputs

Primary inputs come from existing alignment metrics:

- `structural_drift_score`
- `relational_instability_score`
- `transition_pressure`
- `temporal_consistency_score` (converted to `temporal_inconsistency = 1 - temporal_consistency_score`)

Optional enrichment fields:

- `regime_drift`
- reversibility `locked_in_index`
- geometry `curvature`

## Output payload

`tetrahedral_state` includes:

- `weights` (normalized, deterministic)
- `position` (3D Cartesian projection from fixed tetrahedral vertices)
- `nearest_vertex`
- `nearest_face`
- `edge_alignment`
- `speed`
- `curvature`
- `state_label`
- `movement_summary`

Optional pass-through enrichments:

- `regime_drift`
- `reversibility`

## Integration points

In `StructuralEngine.process_frame` the payload is computed once multivariate analytics are available, then attached to:

- `result["tetrahedral_state"]`
- `result["experimental_analytics"]["tetrahedral_state"]`

A short in-memory history buffer tracks recent tetrahedral positions for speed/curvature estimates.
