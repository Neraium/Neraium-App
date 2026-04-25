# Structural instability pipeline: end-to-end map

## Entry → output

| Step | Entry | File:Function | Output / next |
|------|--------|---------------|----------------|
| 1 | REST/batch/CSV | `service.py`: `ingest_payload` / `ingest_batch` / `ingest_csv` | `normalize_rest_payload` → frame |
| 2 | Frame | `service.py`: `_decorate_result(engine.process_frame(frame))` | result dict (enriched) |
| 3 | Frame | **`alignment.py`: `StructuralEngine.process_frame(frame)`** | **Single source of structural result** |
| 4 | Result | `decision_layer.py`: `decision_output(composite_score, components, forecast)` | phase, risk_level, signal_emitted, operator_message, interpreted_state, etc. |
| 5 | Result | `causal.py`: `generate_hypotheses` → `score_hypotheses` → `run_counterfactual_checks` → `generate_validation_plan` → `rank_actions` | `causal_analysis` block (hypotheses, top_hypothesis, counterfactual, validation plan, recommended sequence) |
| 6 | Result | `service.py`: `_decorate_result` | Adds risk_level, action_state, operator_message, trend, confidence, interpretation, structural_analysis_metadata |

**Conclusion:** The only execution path for structural analytics is `alignment.py` → `StructuralEngine.process_frame`. Causal reasoning is integrated in that path via `neraium_core/causal.py`; there is no parallel pipeline.

---

## Demo / Presentation Code Location

- Demo and presentation code is kept under `examples/` (for example, `examples/demo/` and `examples/fd004/`).
- Production/pilot execution remains confined to `neraium_core/` engine + service + API wiring.

---

## Current data flow inside `process_frame`

```
frame
  → _vector_from_frame → stored in self.frames
  → baseline_window = _get_baseline_window()
  → recent_window = _get_recent_window()
  → [GUARD] if either None → return default result

  → normalize_window(baseline_window)  → z_baseline, baseline_mean, baseline_std
  → normalize_window(recent_window)    → z_recent, recent_mean, recent_std
  → valid_mask, valid_signal_count (from stds)
  → early_warning_metrics(recent_window)
  → build_regime_signature / assign_regime / update_regime_library
  → analytics = { early_warning, relational_metrics_skipped, regime_signature }
  → components = canonicalize_components({ drift:0, regime_drift:0, early_warning })

  → [BRANCH] if valid_signal_count >= 2:
       → correlation matrices, structural_drift, regime_drift
       → graph, directional, causal, subsystem, spectral, entropy
       → raw_components → components
       → result updated (drift_score, system_health, state, regime_*, etc.)
       → analytics updated (correlation_geometry, graph, directional, causal, ...)

  → composite = composite_instability_score_normalized(components)   ← scoring.py
  → score_history.append(composite)
  → forecast = { trend, time_to_instability, ar1_* }
  → decision = decision_output(composite_score, components, forecast)  ← decision_layer.py
  → result.update(decision), result["latest_instability"] = composite
  → result["experimental_analytics"] = analytics
  → return result
```

---

## Integration points for changes

### 1. Data quality gating (before normalization)

- **Where:** In `alignment.py`, immediately after we have `baseline_window` and `recent_window`, **before** the first `normalize_window` call.
- **What:** Call a data-quality function that takes `(baseline_window, recent_window, sensor_names)` and returns a small report (e.g. `gate_passed`, `missingness_rate`, `valid_signal_count`, `statuses`).
- **Files:** 
  - **Created:** `neraium_core/data_quality.py` (already added) - single function e.g. `compute_data_quality(...)` returning a report dataclass.
  - **Modified:** `alignment.py` - add import; after `if baseline_window is None or recent_window is None` block, call data quality; attach report to `result` (e.g. `result["data_quality"]`); optionally skip or limit downstream analytics when `gate_passed` is False (current choice: still run, only add the report and a flag so UI/tests see it).
- **No new parallel path:** Same `process_frame`; one extra call and result keys.

### 2. Normalized scoring (replacing existing composite score)

- **Where:** In `alignment.py`, the line that does `composite = composite_instability_score(components)`. In `scoring.py`, the implementation of the composite score.
- **What:** Replace or extend `composite_instability_score` so that:
  - Component values are robustly normalized (e.g. winsorize, then scale to a bounded range).
  - Composite = weighted sum of normalized values (and optionally confidence-weighted); same or similar interface so `decision_output(composite_score, ...)` and `result["latest_instability"]` stay valid.
- **Files:**
  - **Modified:** `scoring.py` - add robust normalization (e.g. per-component winsorization + scaling), and a function (or signature) that returns the normalized composite (e.g. `composite_instability_score(..., use_normalization=True)` or a dedicated `composite_instability_score_normalized` used by alignment).
  - **Modified:** `alignment.py` - call the new normalized composite instead of the raw one (one-line change at composite calculation).
- **No new module:** Logic lives in existing `scoring.py`; alignment only changes the call site.

### 3. (Future) Decision hysteresis, regime lifecycle, explanation engine

- **decision_layer / decision_engine:** Call site is `alignment.py` where `decision_output(...)` is called. Modify `decision_layer.py` in place or swap to a new function in the same file that takes the same inputs plus optional hysteresis state.
- **regime_lifecycle:** Call sites are `assign_regime`, `update_regime_library` and regime_baselines update in `alignment.py`; persistence in `regime_store.py`. Prefer modifying `regime.py` and `alignment.py` rather than a separate “lifecycle” module that duplicates logic.
- **explanation_engine:** Can be a small function in `decision_layer.py` (or same module) that builds operator_message from state/components; no new execution path, just refactor of how `operator_message` is produced.

---

## Summary: modify vs create

| Change | Create | Modify |
|--------|--------|--------|
| Data quality gating | `neraium_core/data_quality.py` (one function + report) | `alignment.py`: 1 call before normalization, add `result["data_quality"]` |
| Normalized scoring | - | `scoring.py`: add normalization + normalized composite; `alignment.py`: use it for `composite` |
| (Future) Hysteresis | - | `decision_layer.py` (+ optional state in `StructuralEngine`) |
| (Future) Regime lifecycle | - | `regime.py`, `alignment.py`, `regime_store.py` |
| (Future) Explanation | - | `decision_layer.py` (or same module) |

---

## Constraints respected

- No duplicate logic: data quality is one place; scoring stays in `scoring.py`.
- Prefer modifying existing pipeline: data quality and normalized score are single insertions in `process_frame` and one change in `scoring.py`.
- Every new piece wired into main path: data quality runs on every frame that has windows; normalized score is the only composite used for decision and `latest_instability`.
- No dead code: no parallel “legacy” path; optional `gate_passed` only controls what we attach (and optionally whether we run heavy analytics when gate fails).

---

## Pre-pilot decision resolver upgrade (SII runtime)

`SIIEngine.process_frame()` now includes a deterministic decision-compression stage after the intelligence blocks are assembled:

1. Build/emit canonical blocks:
   - `attribution`
   - `regime_memory`
   - `risk_assessment`
   - `operator_guidance`
   - `causal_analysis`
2. Resolve top-level `decision` via `neraium_core/decision_resolver.py::resolve_best_action(...)`.
3. Emit structured fallback decisions during warmup/insufficient evidence instead of omitting the block.

Decision selection hierarchy:
1. `causal_analysis.best_next_action` (when confidence is usable)
2. first ranked `causal_analysis.recommended_sequence` action
3. `operator_guidance.recommended_actions[0]`
4. conservative attribution-localized inspection action
5. fallback (`decision.status.available = false`)

Hardening note:
- Canonical causal imports must use `neraium_core.causal`.
- `neraium_core.casual` remains only as a deprecated compatibility shim.
- Decision fallback is explicit and deterministic for warmup/insufficient-evidence cases.
- Canonical output blocks (`causal_analysis`, `decision`, `attribution`, `risk_assessment`, `operator_guidance`, `regime_memory`) are always emitted.
