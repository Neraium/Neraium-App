# Neraium SII — Real-Time System Intelligence Platform

## Product positioning
This is a **System Intelligence Product**, not a dashboard. Every screen must
answer four questions, in this order:

1. **What is happening**
2. **Why it is happening**
3. **What to do**
4. **What happens if ignored**

The primary UI element is the **system decision output** (a sentence, in
plain language). Numbers, charts, and raw metrics are evidence — they live
in a closed-by-default drawer, not at the top of any screen.

> **The 5-second test**: a non-technical operator scanning any screen must
> understand what is wrong and what to do without scrolling.

## Source of truth
- Engine: `neraium_core.sii_engine_adapter.SIIEngineAdapter` (only).
- Repo: `Neraium/neraium-core@02222f32` main (post SII cleanup).
- Validation truth: `SII_TRUTH_SHEET.md` — FD004, 248 systems, 97.58% coverage,
  175.5-cycle mean lead time. Surfaced as Validation Mode (toggle, not default).

## SII canonical contract (from `SIIEngineAdapter.ingest()`)
| Field | Type | Source |
|---|---|---|
| regime | enum {WARMUP, STABLE, TRANSITION, UNSTABLE, LOCK_IN} | adapter |
| urgency | enum {NOMINAL, WATCH, ALERT, CRITICAL} | adapter |
| instability_score, structural_drift, drift_velocity, transition_pressure, confidence, gradient_norm, recovery_alignment | float | adapter |
| detection_context.lead_time_cycles | int | adapter |

Threshold ladder: STABLE ≤ 0.30 < TRANSITION ≤ 0.65 < UNSTABLE ≤ 0.85 < LOCK_IN.

## Architecture
```
/app/neraium_core/                        # canonical SII engine package
/app/SII_TRUTH_SHEET.md                   # locked validation
/app/backend/
├── server.py                             # thin shell, mounts routers, audit auto-flush
├── services/
│   ├── sii_state.py                      # wraps SIIEngineAdapter; per-system unified state
│   ├── synthetic_systems.py              # multi-var coupled generator (industrial/environmental/generic)
│   ├── decision_synth.py                 # variance-ratio attribution + WHAT/WHY/DO/IF_IGNORED
│   ├── playback.py                       # asyncio orchestrator
│   └── serialise.py
└── routers/
    ├── systems.py   playback.py   validation.py   audit.py   ws.py
```

```
/app/frontend/src/
├── App.js                                # 3-view shell: decisions / audit trail / validation
└── components/
    ├── Header.js                         # brand + INTELLIGIZING indicator + speed + START/STOP
    ├── SystemGrid.js  (DECISION FEED)    # fleet headline + per-system decision rows (no charts)
    ├── SystemDetail.js (DECISION DETAIL) # giant decision sentence + NOW/URGENCY/ACTION strip
    │                                     # + WHY + propagation chips + IF IGNORED
    │                                     # + RECOVERY / DEGRADATION / FAILURE
    │                                     # + collapsed Evidence drawer (charts/metrics)
    ├── InstabilityChart.js               # only renders inside Evidence drawer
    ├── AuditView.js
    └── ValidationView.js                 # FD004 truth sheet visualisation
```

## CHANGELOG

### 2026-04-25 — Decision-first rewrite (SystemGrid + SystemDetail)
- Removed the dashboard hierarchy (cards-of-metrics, hero charts).
- New `SystemGrid` is a **decision feed**: a fleet headline sentence on top, then one
  decision row per system. Each row leads with a sentence; drivers are tiny chips;
  action and consequence are explicit lines.
- New `SystemDetail` opens with the **decision headline in 2xl–3xl type**, then a
  NOW/URGENCY/ACTION 3-column strip, WHY (with propagation chips), IF IGNORED, ACK/
  OVERRIDE, then three FUTURE PATHS (subtitled "If you act now / If you wait / If
  you do nothing"). Charts + metrics moved to a closed-by-default Evidence drawer.
- Header: tab "Systems" → "Decisions"; "Audit Log" → "Audit Trail"; LIVE counter
  reframed as "INTELLIGIZING · N systems".

### 2026-04-25 — Full product rebuild against cleaned SII core
(see git history)

## Backlog
- **P2**: Centralise Mongo client (`services/db.py`) — duplicated in `server.py` + `routers/audit.py`.
- **P2**: Audit DOM cap + load-more.
- **P2**: WS-push history deltas instead of 1s polling on SystemDetail.
- **P3**: Centred grid layout for sub-3 system rows.
- **P3**: External "connect-your-telemetry" guide for `POST /api/systems/register`.

## Testing
- `/app/backend/tests/backend_test.py` — 16/16 (iteration_11.json).
- Decision-first rewrite verified visually with full-page screenshots: fleet feed,
  alerted system detail, evidence drawer expanded.
