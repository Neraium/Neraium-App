# Neraium SII — System Intelligence Product

## Locked product behaviour
The application is locked around ONE behaviour: detect instability and explain it.
Every screen must answer, in this order:

1. **What is happening**
2. **Why it is happening**
3. **What to do**
4. **What happens if ignored**

The 5-second test: a non-technical operator must understand what is wrong and what
to do without scrolling.

## Mandatory layout — System Status Panel
TOP OF SCREEN, in this order:

1. **STATE** — STABLE / TRANSITION / UNSTABLE / LOCK_IN
2. **WHAT IS HAPPENING** — plain language sentence
3. **PRIMARY DRIVER** — variable name + variance ratio
4. **URGENCY** — time sensitivity
5. **ACTION** — what to do
6. **CONSEQUENCE** — if ignored

SECONDARY (below the panel): future paths, trajectory chart, supporting variables.

NEVER allowed: dashboards, placeholder charts, passive metric tiles, anything
requiring interpretation, dataset-specific language ("bearings", "grow rooms"),
charts as the lead element of any screen.

## Generic data model
- "systems" (not bearings/units)
- "variables" / "signals"
- Templates: industrial / environmental / generic — variable names neutral
  (`vibration_g`, `var_alpha`, etc.)

## Source of truth
- `neraium_core.sii_engine_adapter.SIIEngineAdapter` — only.
- Repo: `Neraium/neraium-core@02222f32` (post SII cleanup).

## Architecture
```
/app/neraium_core/                              # canonical SII engine
/app/SII_TRUTH_SHEET.md                         # locked validation
/app/backend/
├── server.py                                   # thin shell
├── services/
│   ├── sii_state.py                            # wraps SIIEngineAdapter
│   ├── synthetic_systems.py                    # multi-var coupled generator
│   ├── decision_synth.py                       # variance-ratio attribution → WHAT/WHY/DO/IF_IGNORED
│   ├── playback.py                             # asyncio orchestrator
│   └── serialise.py
└── routers/
    ├── systems.py   playback.py   audit.py   ws.py

/app/frontend/src/components/
├── Header.js                                   # brand + INTELLIGIZING + speed + START/STOP
├── SystemGrid.js                               # decision feed (one System Status Panel per row)
├── SystemDetail.js                             # full System Status Panel + trajectory + paths
├── InstabilityChart.js                         # secondary, always visible (not collapsed)
└── AuditView.js                                # state transition log
```

## CHANGELOG

### 2026-04-25 — Validation Mode removed
- Deleted `routers/validation.py`, `ValidationView.js`, `Validation` API
  client, header tab, and the FD004 backend test class. The Validation
  Mode (FD004 truth sheet) is no longer surfaced in the product.

### 2026-04-25 — Plain-language judgment + browser tab title
- Added `_pretty_var()` translation in `services/decision_synth.py`. Raw
  variable names (`torque_nm`, `vibration_g`, `co2_ppm`, `vpd_kpa`,
  `airflow_cmh`, `var_alpha`, …) are translated to operator-readable text
  (`torque`, `vibration`, `CO₂ level`, `vapor pressure`, `airflow`,
  `primary signal`, …) before insertion into WHAT / ACTION / CONSEQUENCE /
  WHY / future-paths text.
- Unknown variables fall back to humanised `snake_case → words` with unit
  suffixes stripped — never raw.
- Raw variable names remain visible only in the propagation chip row and
  the Variables panel, where they belong.
- `App.js` writes a real-time browser tab title:
  `(N) sys-X URGENCY · M nominal — Neraium SII`
  (or `○ N nominal — Neraium SII` when calm). Title uses system_id +
  regime/urgency only, never raw variables.
- Backend tests: 16/16 pass.

### 2026-04-25 — System Status Panel lock-in
- Removed "Evidence drawer" pattern. Trajectory + variables are now always
  visible below the status panel as **secondary** content.
- SystemDetail rewritten as a single bordered `data-testid="status-panel"`
  containing all 6 mandatory fields with explicit testids: `field-state`,
  `field-what`, `field-driver`, `field-urgency`, `field-action`,
  `field-consequence`.
- SystemGrid rows mirror the 6-field structure in compact form: STATE chip,
  sentence + DRIVER chips, DO line, IF IGNORED line, URGENCY time on the right.
- Removed "Evidence" toggle. The chart is no longer hidden — it sits below
  the panel because the panel itself answers the operator's question.

### 2026-04-25 — Decision-first rewrite
(see git history)

## Testing
- `/app/backend/tests/backend_test.py` — 16/16 (iteration_11.json).
- Fields verified via Playwright: all six testids present in System Status
  Panel; rows in feed render all six fields compactly.

## Backlog
- **P2**: Centralise Mongo client (`services/db.py`).
- **P2**: Audit DOM cap + load-more.
- **P2**: WS-push history deltas instead of 1s polling on SystemDetail.
- **P3**: Centred grid for sparse fleets; "connect-your-telemetry" guide for
  `POST /api/systems/register`.
