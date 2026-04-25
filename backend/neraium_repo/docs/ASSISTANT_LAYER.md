# Assistant interaction layer (thin, grounded, non-autonomous)

The assistant layer is a presentation + interaction adapter on top of the existing Neraium canonical output contract.

It **does not** change core engine behavior.

## What it does

- Builds a compact LLM-facing context payload from existing structured output only.
- Returns deterministic operator-facing response formats for:
  - `summary`
  - `why_recommended`
  - `what_changed`
  - `pattern_similarity`
  - `handoff`
- Returns deterministic contractor-facing report formats via `POST /assistant/report`:
  - `client_report`
  - `technician_summary`
  - `inspection_brief`
  - `handoff_note`
- Preserves advisory-safe language and includes explicit grounding sections:
  - `Observed`
  - `Inferred`
  - `Recommended`

## Allowed sources

Assistant responses can cite only data already present in product output/history:

- `risk_assessment`
- `operational_recommendation`
- `explanation_text`
- `events`
- `memory_recall`
- recent service history timeline

## Not allowed

- No threshold retuning.
- No autonomous decisions.
- No replacement of canonical output with free text.
- No unsupported causal claims.
- No giant agent framework.

## API endpoints

- `POST /assistant/summary`
- `POST /assistant/explain` (`mode` in `why_recommended`, `what_changed`, `pattern_similarity`)
- `POST /assistant/handoff`
- `POST /assistant/report`
- `POST /assistant/report/export?format=txt|md`

Example request:

```json
{
  "customer_id": "customer-a",
  "run_id": "run-operator-demo",
  "mode": "why_recommended",
  "history_limit": 20
}
```

Example response shape:

```json
{
  "mode": "summary",
  "text": "Current situation summary\nObserved: ...\nInferred: ...\nRecommended: ...",
  "grounding": {
    "observed": ["Observed: ..."],
    "inferred": ["Inferred: ..."],
    "recommended": ["Recommended: ..."]
  },
  "context": {
    "current_state": {},
    "risk": {},
    "recommendation": {},
    "explanation": "...",
    "events": [],
    "memory_recall": {},
    "recent_changes": {},
    "recent_timeline": []
  }
}
```

## Local run

```bash
uvicorn apps.api.main:app --reload --port 8000
```

Open operator workflow page:

- `http://127.0.0.1:8000/operator`

The page now includes assistant summary, explanation mode panel, and handoff note sections backed by the new endpoints.


## Report mode quick reference

All report modes are grounded directly in canonical fields only (`risk_assessment`, `operational_recommendation`, `explanation_text`, `events`, `memory_recall`, recent history).

- `client_report`: client-ready narrative with full sections and confidence/operator note.
- `technician_summary`: concise state + what changed + key drivers + next step.
- `inspection_brief`: inspection-oriented target/reason/checklist/risk context.
- `handoff_note`: handoff structure aligned to the same sectioned report format.

Example request:

```json
{
  "customer_id": "customer-a",
  "run_id": "run-operator-demo",
  "mode": "client_report",
  "history_limit": 20
}
```

Example response shape:

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
