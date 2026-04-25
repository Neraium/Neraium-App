# Neraium Service Layer API (Production-Oriented v1)

This document defines the production service layer around the validated Neraium engine using **advisory operational recommendation semantics**.

## Canonical Output Contract

All service methods emit or persist one stable canonical envelope.

### Required fields

- `schema_version`: contract version string (`2026-03-28`)
- `timestamp`: frame timestamp
- `cycle`: per-run monotonic cycle index
- `attribution`
  - `top_drivers`: list of `{driver, score}`
  - `group_contributions`: optional grouped contributions
- `regime_memory`: regime-memory payload from engine
- `risk_assessment`
  - `risk_level`
  - `trend`
  - `latest_instability`
- `causal_analysis`: engine causal output
- `operational_recommendation`
  - `status.available`
  - `status.advisory` (always `true`)
  - `status.reason`
  - `recommended_action`
  - `recommended_target`
  - `priority`
  - `recommendation_confidence`
  - `urgency`
  - `rationale`
  - `supporting_evidence`
  - `operator_note`
- `confidence`: normalized [0,1] confidence view
- `explanation_text`: operator-facing explanation
- `events`: product-facing event flags

### Optional fields

- `session`: `{run_id, customer_id}`
- `aliases`: isolated compatibility aliases (`legacy_decision`, optional legacy `decision`, `explanation`, `regime_memory_state`)

## Operator boundary

Neraium recommendations are advisory outputs intended to support, not replace, qualified operator judgment and site-specific procedures.

## Service Interface

Implemented on `StructuralMonitoringService`:

- `ingest_frame(payload, *, run_id=None, customer_id=None)`
- `ingest_batch(payloads, *, run_id=None, customer_id=None)`
- `get_current_state(*, run_id=None, customer_id=None)`
- `get_recent_history(limit=100, *, run_id=None, customer_id=None)`
- `get_latest_recommendation(*, run_id=None, customer_id=None)`
- `get_latest_decision(*, run_id=None, customer_id=None)` (deprecated compatibility alias)
- `get_latest_explanation(*, run_id=None, customer_id=None)`
- `get_memory_matches(*, run_id=None, customer_id=None, site_id=None, asset_id=None, limit=20)`
- `get_pattern_history(*, customer_id=None, family_label=None, limit=100)`
- `get_novel_events(*, customer_id=None, run_id=None, limit=100)`

## Event Semantics

Events are derived from existing engine outputs:

- `early_instability_detected`: instability rises while risk not yet high
- `risk_escalated`: risk level increases vs previous cycle
- `recommendation_available`: advisory recommendation is available
- `inspection_recommended`: high risk or inspect/diagnose recommendation cues
- `deterioration_detected`: rising trend or instability jump
- `known_pattern_recalled`: nearest structural memory match found
- `novel_pattern_detected`: current pattern below conservative similarity/overlap thresholds
- `cross_asset_pattern_match`: nearest recalled match came from a different asset
- `recurring_degradation_pattern`: high-confidence recurring medium/high-risk degradation pattern

## Structural memory signature (deterministic)

The first-pass structural memory signature is compact and explainable:

- top attribution drivers (top 3 names)
- attribution concentration (`max_driver_abs_score / sum_abs_scores`)
- regime key (from regime memory labels/state)
- risk level + trend
- instability bucket (`latest_instability` normalized and clipped)
- decision state + action + derived action target token
- dominant hypothesis (from causal analysis dominant hypothesis/driver)
- confidence bucket

## Similarity and novelty

Similarity score is fully deterministic and interpretable:

- **categorical match score** across regime/risk/decision/hypothesis fields
- **driver overlap score** (Jaccard overlap of top drivers)
- **numeric closeness score** across concentration/instability/confidence buckets
- weighted total: `0.5 * categorical + 0.3 * driver_overlap + 0.2 * numeric`

Novelty is conservative:

- novel when either total similarity `< 0.72` **or** driver overlap `< 0.45`
- if no prior memory exists, mark novel with reason `no_prior_structural_memory`
- novelty reason always returned for traceability

## HTTP API Layer (FastAPI)

### Endpoints

- `POST /ingest/frame`
- `GET /state`
- `GET /history`
- `GET /recommendation`
- `GET /recommendations/latest`
- `GET /decision` (deprecated compatibility alias)
- `GET /explanation`
- `GET /events/latest`
- `POST /assistant/summary`
- `POST /assistant/explain`
- `POST /assistant/handoff`
- `POST /assistant/report`
- `POST /assistant/report/export?format=txt|md`

### Example recommendation block

```json
{
  "operational_recommendation": {
    "status": {
      "available": true,
      "advisory": true,
      "reason": "recommendation_available"
    },
    "recommended_action": "inspect_cooling_loop",
    "recommended_target": "cooling_loop",
    "priority": 1,
    "recommendation_confidence": 0.74,
    "urgency": "medium",
    "rationale": "Recommendation available from converging structural evidence.",
    "supporting_evidence": [{"driver": "temperature", "score": 0.82}],
    "operator_note": "Recommendations are advisory outputs intended to support, not replace, qualified operator judgment and site-specific procedures."
  }
}
```


### Assistant endpoint notes

Assistant responses are grounded presentation outputs over canonical fields and recent history. They explicitly separate:

- observed evidence
- inferred pattern context
- recommended advisory action

`POST /assistant/explain` accepts `mode` values:

- `why_recommended`
- `what_changed`
- `pattern_similarity`


### Contractor report generation

`POST /assistant/report` builds deterministic, sectioned report text from existing canonical output only.

Supported `mode` values:

- `client_report`
- `technician_summary`
- `inspection_brief`
- `handoff_note`

Request body:

```json
{
  "customer_id": "customer-a",
  "run_id": "run-operator-demo",
  "mode": "client_report",
  "history_limit": 20
}
```

Response body:

```json
{
  "mode": "client_report",
  "report_text": "Client Report\n...",
  "sections": {
    "Overview": "...",
    "Current System State": "..."
  }
}
```

`POST /assistant/report/export?format=txt|md` returns the same `report_text` as a downloadable text/markdown attachment.
