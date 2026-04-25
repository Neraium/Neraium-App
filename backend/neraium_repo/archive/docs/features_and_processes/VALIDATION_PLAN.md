# Neraium Upgrade - Validation Plan

This document lists scenarios that should be tested to validate the production-readiness upgrade and what success looks like for each.

---

## 1. Nominal Operation

**Scenario**  
Stable, coherent multi-sensor stream; no structural change.

**What to test**
- Run `process_frame` for many frames with 2+ sensors in a stable regime.
- Check output shape and presence of new fields.

**Success**
- `interpreted_state` is `NOMINAL_STRUCTURE`.
- Output includes `causal_attribution` (with `top_drivers`, `driver_scores`), `data_quality_summary`, `active_sensor_count`, `missing_sensor_count`, `baseline_mode`, `regime_memory_state`, `confidence_score`.
- `structural_drift_score` and `latest_instability` remain non-negative and in expected range.

---

## 2. Regime Shift

**Scenario**  
Structural geometry changes (e.g. phase/scale change) but relationships remain internally consistent; no strong directional/spectral breakdown.

**What to test**
- Feed a clean transition from one stable regime to another (e.g. different mean/variance or phase, same correlation structure).
- Inspect `interpreted_state` over the transition and after.

**Success**
- After warmup, we see `REGIME_SHIFT_OBSERVED` or `NOMINAL_STRUCTURE` (or `COHERENCE_UNDER_CONSTRAINT` in borderline cases), but not persistent `STRUCTURAL_INSTABILITY_OBSERVED` or `COUPLING_INSTABILITY_OBSERVED` for a clean transition.
- Regime assignment and `regime_memory_state` reflect the current regime.

---

## 3. Coupling Instability

**Scenario**  
Directional/spectral (interaction) breakdown: e.g. one sensor becomes uncorrelated or strongly noisy while others stay coherent.

**What to test**
- After a stable baseline, make one channel noisy or decorrelated for a sustained period.
- Collect `interpreted_state` over the last N frames.

**Success**
- `COUPLING_INSTABILITY_OBSERVED` (or `STRUCTURAL_INSTABILITY_OBSERVED`) appears in the tail of the run.
- Coupling instability is reported when directional/spectral evidence is elevated and sustained (per the lower sustained bar for coupling).

---

## 4. Structural Instability

**Scenario**  
Relational drift plus entropy/regime drift with sustained, multi-indicator evidence (e.g. multiple sensors decorrelating and entropy rising).

**What to test**
- After a stable baseline, introduce persistent decorrelation and/or noise across sensors so that drift, regime drift, and entropy all contribute.
- Run for enough frames to build “sustained” history.

**Success**
- `STRUCTURAL_INSTABILITY_OBSERVED` (or `COUPLING_INSTABILITY_OBSERVED`) appears in the tail.
- Composite score and component breakdown reflect elevated drift, entropy, and regime drift where applicable.

---

## 5. Missing Data / Dropout

**Scenario**  
Some sensors have missing values (NaN) or partial dropout in the recent window.

**What to test**
- Run with 2+ sensors; from a certain frame onward, set a subset of sensor values to NaN or drop a sensor intermittently.
- Check that the engine still returns a result and that quality/confidence reflect degradation.

**Success**
- `process_frame` returns a full result (no unhandled exception).
- `data_quality_summary` shows reduced `valid_signal_count` and/or higher `missingness_rate` and/or `stale_sensor_count`/`missing_sensor_count` as appropriate.
- When the gate fails but degraded path is allowed: output is still meaningful; confidence is lower (e.g. `confidence_score` and/or categorical `confidence` reflect degraded evidence).
- When too much data is missing (e.g. above degraded threshold), output may be minimal but remains valid (e.g. default/zero scores and explicit quality status).

---

## 6. Stale Sensor Behavior

**Scenario**  
One or more sensors are mostly NaN or flat in the recent window (stale/flatlined).

**What to test**
- Run with 2+ sensors; make one sensor mostly NaN or constant in the recent window.
- Inspect `data_quality_summary`, `active_sensor_count`, `missing_sensor_count`, and any stale/flatlined lists.

**Success**
- Stale or flatlined sensors are reflected in `data_quality_summary` (e.g. `stale_sensor_count`, `flatlined_sensor_count`, or equivalent).
- `active_sensor_count` and `missing_sensor_count` are consistent with the number of usable vs missing/stale sensors.
- Engine does not crash; confidence and scores reflect reduced data quality where applicable.

---

## 7. Adaptive Baseline

**Scenario**  
Long run of nominal, stable operation followed by a small, slow change that should not be classified as instability.

**What to test**
- Run many frames in a stable regime so that the rolling baseline can activate; then introduce a small, slow drift (e.g. slight scale change) that stays within nominal behavior.
- Check `baseline_mode` and drift scores over time.

**Success**
- After sufficient nominal history, `baseline_mode` can become `"rolling"` (implementation-dependent).
- Drift does not spike inappropriately when the change is slow and nominal; baseline adapts instead of treating the change as full instability.

---

## 8. Causal Attribution Presence

**Scenario**  
Multi-sensor frames with enough valid signals to compute correlation and causal proxies.

**What to test**
- Run with 2+ sensors for enough frames to compute correlation and Granger-style matrix.
- Inspect `causal_attribution` and `dominant_driver`.

**Success**
- `causal_attribution` is present with `top_drivers` (list) and `driver_scores` (dict).
- `dominant_driver` is either a sensor name (when there are top drivers) or `None`.
- For a single-sensor or invalid-signal case, `causal_attribution` is present with empty `top_drivers` and empty `driver_scores` (or equivalent).

---

## 9. Classification Stability and Confidence

**Scenario**  
Stable run so that recent interpreted states are consistent; then optionally a period of instability.

**What to test**
- Run nominal stream; check `confidence_score` and `classification_stability` (if present).
- After instability appears, confirm confidence can decrease when data quality or classification stability drops.

**Success**
- `confidence_score` is in [0, 1].
- When present, `classification_stability` is in [0, 1].
- Under good data and stable classification, confidence is relatively high; under missing data or unstable classification, confidence is lower.

---

## 10. Backward Compatibility

**Scenario**  
Existing consumers of `process_frame` and decision output.

**What to test**
- Run existing test suites (decision_layer, multinode persistence, single-sensor stream, scoring, API product basics if available).
- Ensure no removed keys or changed semantics for existing fields.

**Success**
- All existing tests pass.
- No existing interpreted states removed.
- Existing top-level keys (`interpreted_state`, `structural_drift_score`, `regime_drift`, `state`, `confidence`, etc.) retain meaning; new keys are additive only.

---

## Running the Validation

- **Automated**: Run `tests/test_upgrade_scenarios.py` and the full test suite (e.g. `pytest tests/ -v`).
- **Manual / integration**: Use the scenarios above with real or synthetic data and verify success criteria for your deployment (e.g. API, dashboards, alerts).

Success for the upgrade is: all automated tests pass, and for each scenario above the corresponding success criteria hold in your environment.
