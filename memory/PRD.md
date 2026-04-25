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

### 2026-04-25 — Language polish + visual hierarchy
- Fixed duplicate-word bug ("System system operating…") by introducing
  `_subject(template)` which returns a clean noun phrase ("Mechanical
  system" / "Environmental system" / "System") so `<subject> operating…`
  is always grammatical.
- Added `what_secondary` (clarifier line under WHAT), `risk` (None /
  Increasing / Active / Realised — only surfaced when ≠ STABLE), and
  `card_summary` (per-row short context: "Mechanical system stable",
  "Environmental system transitioning", …) to the decision payload.
- STABLE action language tightened to "No intervention required\nSystem
  stable and operating within expected behavior".
- `SystemGrid` headline rewritten to match the locked layout:
  `SYSTEM STATE: <STATE>` huge → primary line → secondary clarifier →
  vertical labelled list (RISK if any → ACTION → CONSEQUENCE).
- `SystemGrid` rows demoted to `opacity-80` and now show the short
  `card_summary` instead of repeating the full WHAT sentence.
- `SystemDetail` mirrors the headline structure: dominant
  `SYSTEM STATE: <STATE>` heading → WHAT primary + secondary →
  vertical labelled list of RISK / ACTION / CONSEQUENCE.
- Card chip ↔ summary now stay in lockstep — the row state derives
  from `decision.state` (same engine snapshot as the words) instead
  of the systems-list `latest.regime`.

### 2026-04-25 — Single state vocabulary + dominant judgment
- **State vocabulary collapsed to ONE axis**: only STABLE / TRANSITION /
  UNSTABLE / LOCK_IN appear in operator-facing UI. Internal urgency
  (NOMINAL/WATCH/ALERT/CRITICAL) is no longer surfaced anywhere — not
  on cards, not in headlines, not in tab title, not in audit log.
- `decision_synth.py` rewritten as state-driven: WHAT / ACTION /
  CONSEQUENCE / WHY are gated by the regime so wording is always
  state-aligned (no "drift" language in STABLE; no "stable" language
  in TRANSITION/UNSTABLE/LOCK_IN). Adds `consequence_short` (locked
  per spec) and `driver_phrases[]` (semantic — "Vibration intensifying",
  "Flow imbalance increasing", …) so the UI never renders raw chips.
- `SystemDetail` now leads with `SYSTEM STATE: <regime>` at
  text-4xl→6xl as the largest element on the page. WHAT, ACTION,
  CONSEQUENCE follow.
- `SystemGrid` rows always render CONSEQUENCE (locked per state) and
  use semantic driver pills instead of raw `var × ratio`. Raw values
  remain only as tooltips and inside the Variables panel.
- Added `state-pulse-{transition,unstable,lockin}` halo CSS so the
  operator's eye is drawn to systems that have left STABLE.
- `AuditView` shows a translated headline as the primary line; numeric
  metrics are de-emphasised. Backend `audit_headline()` writes the
  headline server-side; manual ACK/OVERRIDE/NOTE entries get one too.
- Audit auto-flush no longer emits internal `urgency` transitions.
- Tab title uses regime: `(N) sys-X TRANSITION · M stable — Neraium SII`.
- Removed dead `DecisionPanel.js`. Backend tests realigned to the new
  contract; 15/15 pass.

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
