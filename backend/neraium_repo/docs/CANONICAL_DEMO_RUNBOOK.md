# Neraium canonical investor demo runbook

This is the founder-safe demo path designed for zero improvisation.

## 1) One-command startup

```bash
python run_demo.py
```

UI + API run from one process.

## 2) One-command canonical demo execution

In a second terminal:

```bash
python tools/run_canonical_demo.py --base-url http://127.0.0.1:7860 --customer-id customer-a --max-frames 240
```

This command always generates deterministic backup proof artifacts and, when API replay is reachable, also runs live replay checks.

Outputs:
- `reports/demo_proof/investor_demo_report.json`
- `reports/demo_proof/investor_demo_report.md`
- `reports/demo_proof/investor_demo_timeline.csv`
- `reports/demo_proof/canonical_demo_session.json`

## 3) Canonical live story (speak track)

1. **Normal system state** — stable relationship geometry.
2. **Early structural drift detected** — relationships shift before threshold alarms.
3. **Instability rising** — trend and risk move into actionable range.
4. **Risk becomes actionable** — operator gets explicit recommendation.
5. **Operator-guided next step** — read-only advisory output, human executes procedure.

## 4) Proof artifact to show on screen

Use `reports/demo_proof/investor_demo_timeline.csv` with any spreadsheet/chart tool and plot:
- `cycle` (x-axis)
- `structural_drift_score`
- `composite_instability`
- overlay markers for first MEDIUM risk and threshold detection index from `investor_demo_report.json`

This is the fastest way to show “Neraium saw instability earlier than threshold-style detection.”

## 5) Troubleshooting

### Replay start fails (503 / runtime unavailable)
- Cause: API running in fallback/degraded mode.
- Action: restart runtime with full `neraium_core` modules.
- Backup mode: use generated `reports/demo_proof/*` artifacts immediately.

### Replay starts but shows no results
- Cause: insufficient frame count or interrupted ingest.
- Action: rerun with `--max-frames 240` or higher, then refresh run detail.

### Dashboard appears empty after refresh
- Action: open `/dashboard`, select active run, then open run analysis.
- Verify `/health` endpoint returns `200`.

## 6) Live investor demo checklist

- [ ] Confirm read-only / non-actuating framing in opening line.
- [ ] Run canonical command and verify `Mode:` output.
- [ ] Open dashboard and run detail for replay run.
- [ ] Narrate five-step story in order.
- [ ] Show proof artifact + lead-vs-threshold statement.
- [ ] Close with what Neraium is **not** claiming (not autonomous control, not guaranteed failure timestamp).

## 7) Backup demo mode

If live ingest or replay fails:
1. Open `reports/demo_proof/investor_demo_report.md`.
2. Show `investor_demo_timeline.csv` chart.
3. Use `canonical_demo_session.json` checklist and proof block.

This preserves a deterministic, investor-grade walkthrough even without live API conditions.
