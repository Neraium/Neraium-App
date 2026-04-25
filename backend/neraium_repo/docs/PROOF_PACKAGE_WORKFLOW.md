# Neraium proof package workflow

## Purpose
The proof package is a deterministic, founder-safe workflow that compares Neraium’s structural instability signal against a simple threshold-style baseline across canonical scenarios.

It is designed for investor decks, live demos, and pilot conversations where product trust matters more than benchmark complexity.

## Existing evidence audit (what existed vs what was missing)
### Already in repository
- Canonical investor single-story demo (`tools/run_investor_proof_demo.py`) with deterministic artifacts.
- Canonical founder-safe demo wrapper (`tools/run_canonical_demo.py`).
- FD004 validation artifacts and evaluation workflows.

### Missing before this package
- Multi-scenario canonical comparison in one run.
- Explicit, transparent threshold baseline timeline alongside Neraium outputs.
- Scenario-by-scenario machine + human artifacts in one predictable structure.
- Unified top-level summary index for founder/investor one-glance use.
- Regression tests enforcing stable/noisy/messy handling expectations.

## Run command
```bash
python tools/run_proof_package.py
```

Optional:
```bash
python tools/run_proof_package.py --output-dir reports/proof_package
```

## Scenarios included
1. **Stable baseline**
   - Normal operation only.
   - Expected: no threshold trigger, no Neraium warning.
2. **Gradual drift**
   - Relational structure drifts gradually.
   - Expected: Neraium warning appears before threshold trigger.
3. **Abrupt spike**
   - Short-lived transient disturbance.
   - Expected: no permanent escalation.
4. **Progressive critical**
   - Compounding degradation toward critical limits.
   - Expected: Neraium warning leads threshold by clear cycles.
5. **Missing / messy data**
   - Missing values and out-of-order timestamp injected deterministically.
   - Expected: explicit quality/uncertainty states.

## Artifact layout
Under `reports/proof_package/` (or selected output dir):
- Per scenario:
  - `timeline.csv`
  - `summary.json`
  - `report.md`
- Top level:
  - `proof_summary_index.json`
  - `proof_summary_index.md`
  - `founder_investor_one_glance.md`

## Interpretation guidance
- `neraium_warning_cycle` uses a deterministic composite-instability rule (2-cycle confirmation).
- `threshold_first_trigger_cycle` comes from per-signal hard limits (`pressure`, `flow`, `vibration`, `temperature`).
- `lead_cycles_neraium_vs_threshold = threshold_cycle - neraium_cycle`.
  - Positive => Neraium earlier.
  - Zero => same-time.
  - Negative => threshold earlier.

## Claims and non-claims
### Claims
- In canonical drift/degradation scenarios, structural instability appears before hard threshold crossing.
- Risk progression remains interpretable and artifacts are repeatable.
- Data quality limitations are surfaced explicitly in messy-data conditions.

### Non-claims
- Not a universal benchmark or guaranteed lead time for every deployment.
- Not an automated actuation/control policy.
- Not a replacement for operator judgment.

Neraium remains read-only, non-actuating, and human-in-the-loop.
