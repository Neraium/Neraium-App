# Neraium SII — Real-Time System Intelligence Platform

## Original problem statement (post-rebuild, 2026-04-25)
Build a generalised system intelligence product on top of the cleaned `Neraium/neraium-core@02222f32` (post SII cleanup pass). The product must:
- Use **`neraium_core.sii_engine_adapter.SIIEngineAdapter` as the only source of truth** for regime/urgency/instability_score/structural_drift/drift_velocity/transition_pressure/confidence
- Work for **any multi-variable system** — generic terminology ("systems", not bearings or grow rooms), pluggable templates (industrial / environmental / generic)
- Default experience: live systems running, one drifts, SII detects instability before obvious signs, escalation visible (STABLE → TRANSITION → UNSTABLE), operator sees WHAT/WHY/DO/IF_IGNORED
- Validation Mode toggle showing the locked FD004 truth sheet (97.58% coverage / 175.5 cycle mean lead time / 2.4% miss rate) — proof of performance, not the default experience
- Strict rules: no legacy Tesla/operator UI, no placeholder metrics, no market/trading code, no dataset-specific language in core UI

## Architecture
```
/app/                                 # repo root (Neraium/neraium-core@main)
├── neraium_core/                     # canonical SII engine package
│   ├── sii_engine_adapter.py         # SINGLE source of truth — DO NOT REIMPLEMENT
│   └── sii_engine_unified.py
├── SII_TRUTH_SHEET.md                # locked validation results
├── SII_ENGINE_INTEGRATION_GUIDE.md
└── backend/
    ├── server.py                     # thin shell, sys.path includes /app, mounts routers, audit auto-flush
    ├── services/
    │   ├── sii_state.py              # wraps SIIEngineAdapter; per-system unified state history
    │   ├── synthetic_systems.py      # multi-var coupled generator (industrial/environmental/generic)
    │   ├── decision_synth.py         # data-driven WHAT/WHY/DO/IF_IGNORED with variance-ratio attribution
    │   ├── playback.py               # asyncio orchestrator
    │   └── serialise.py
    └── routers/
        ├── systems.py                # /api/systems[/{id}/state|history|decision|ingest]; /systems/register
        ├── playback.py               # /api/playback/{templates,status,start,stop,speed}
        ├── validation.py             # /api/validation/fd004 (locked truth sheet)
        ├── audit.py                  # /api/audit (auto-emits regime/urgency transitions)
        └── ws.py                     # /api/ws/stream snapshot push
```

```
/app/frontend/src/
├── App.js                            # view shell: grid → detail | audit | validation
├── api.js                            # axios client (Playback, Systems, Audit, Validation)
├── sii.js                            # REGIME_COLOR / URGENCY_COLOR / URGENCY_RANK
└── components/
    ├── Header.js                     # brand + LIVE indicator + speed S/N/F + START/STOP + view tabs
    ├── SystemGrid.js                 # cards sorted by urgency, instability bar w/ threshold ticks
    ├── SystemDetail.js               # hero + decision panel + chart + future paths + variables
    ├── DecisionPanel.js              # 4-cell strip (WHAT/WHY/DO/IF_IGNORED) + driver chips
    ├── InstabilityChart.js           # trajectory with SII threshold reference lines
    ├── FuturePaths.js                # recovery / degradation / failure
    ├── AuditView.js                  # transition log
    └── ValidationView.js             # FD004 truth-sheet visualisation
```

## SII canonical contract (from `SIIEngineAdapter.ingest()`)
| Field | Type | Source |
|---|---|---|
| regime | enum {WARMUP, STABLE, TRANSITION, UNSTABLE, LOCK_IN} | adapter |
| urgency | enum {NOMINAL, WATCH, ALERT, CRITICAL} | adapter |
| instability_score | float [0,1] | adapter |
| structural_drift | float [0,1] | adapter |
| drift_velocity | float | adapter |
| transition_pressure | float [0,1] | adapter |
| confidence | float [0,1] | adapter |
| gradient_norm, recovery_alignment | float | adapter |

Threshold ladder: STABLE ≤ 0.30 < TRANSITION ≤ 0.65 < UNSTABLE ≤ 0.85 < LOCK_IN.

## CHANGELOG

### 2026-04-25 — full product rebuild against cleaned SII core
- Discarded entire pre-cleanup codebase (Tesla/operator UI, market modules, dataset-specific code).
- Verified `/app` is on `Neraium/neraium-core@02222f32 main`; `SII_TRUTH_SHEET.md` and `neraium_core/sii_engine_unified.py` confirmed.
- New backend: 5 services (`sii_state`, `synthetic_systems`, `decision_synth`, `playback`, `serialise`) + 5 routers.
- New frontend: built from scratch (no recovered files), dark technical SII console, three views (Systems / Audit / Validation), live WS snapshots, polling fallback.
- Validation: 16/16 backend tests + full Playwright happy path = **100% / 100%** (iteration_11.json).

## Backlog (Roadmap)
- **P2**: Centralise Mongo client (single shared `services/db.py`) — currently duplicated in `server.py` + `routers/audit.py`.
- **P2**: Cap audit log DOM rows (200 max) with infinite scroll / "load more".
- **P2**: SystemDetail history polling every 1s is heavy — switch to WS-driven delta updates.
- **P3**: When fewer than 3 systems are registered, lay out cards centered to avoid orphan-row look.
- **P3**: External integration template — `POST /api/systems/register` already exists; add a documented "ingest your own variables" guide for connecting real telemetry sources.

## Testing
- `/app/backend/tests/backend_test.py` — 16 tests (root, templates, playback lifecycle, systems CRUD, audit auto+manual+invalid, FD004 truth, WS subscribe).
- `/app/test_reports/iteration_11.json` — 100% pass, no critical issues.
