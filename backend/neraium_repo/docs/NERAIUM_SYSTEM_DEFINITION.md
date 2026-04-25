# Neraium System Definition (Operational)

_Last updated: April 18, 2026._

## 0) Purpose and scope

Neraium is a read-only decision system for complex infrastructure. It ingests telemetry, detects when system behavior departs from its own relational baseline, tracks how that change is evolving, and emits operator-facing decision guidance with traceable rationale.

This document is an operational definition for engineering alignment, technical partners, pilot design, and diligence review.

### Maturity labels used in this document

- **Current behavior (implemented):** Present in the current runtime and code paths.
- **Target behavior (validation contract):** Explicit performance or quality target used as engineering acceptance criteria.
- **Intended operational design / proposed contract:** Planned integration or operating model not yet fully production-hardened.

---

## 1) System definition

### 1.1 What Neraium is

Neraium is a structural decision layer that evaluates **relationships among signals over time** (not just per-sensor threshold crossings), then maps those structural findings into interpretable risk and action guidance.

### 1.2 What Neraium is not

- Not an actuator or control system.
- Not a replacement for plant SCADA, historian, or existing alerting stack.
- Not a guarantee of exact failure timestamp.
- Not a black-box classifier requiring hidden model scores to operate.

### 1.3 Layered architecture (operational view)

1. **Structural detection layer**
   - Computes structural drift and instability from baseline-vs-recent relational geometry.
2. **Temporal interpretation layer**
   - Tracks persistence, trajectory, and transitions so one-frame spikes do not dominate decisions.
3. **Decision policy layer**
   - Assigns severity/stage, applies suppression policy, and emits action guidance.
4. **Explanation and evidence layer**
   - Exposes compact decision traces for auditability.

---

## 2) DETECTION-TO-DECISION PIPELINE

The following walkthrough uses an FD004-style turbofan degradation trajectory.

### Input

**Current behavior (implemented):**
- A time-ordered multivariate frame (e.g., engine sensor snapshot) is ingested with unit/asset identity.
- Neraium processes streaming-like updates frame-by-frame.

Example input concept (simplified):
- `unit_id=FD004_unit_021`
- `timestamp=t`
- sensors (temperatures, pressures, vibration, flow-related channels)

### Structural layer

**Current behavior (implemented):**
- The engine compares recent relational structure against baseline structure.
- It computes structural signals such as drift/instability and related state fields.
- It surfaces structured outputs including state, drift score, and structural context fields.

Operationally: instead of asking "is sensor 7 high?", this layer asks "are the sensor relationships that define this engine’s normal operating manifold separating from baseline?"

### Temporal layer

**Current behavior (implemented):**
- Decision logic maintains temporal context: trajectory, confidence deltas, persistence at severity levels, and transition events.
- Transient scoring and gating reduce one-off disturbances.
- Pattern memory/outcome influence can adjust suppression and action confidence.

Operationally: a single deviation can be treated as transient; repeated and directional deviations are promoted toward stronger decisions.

### Stage assignment

**Current behavior (implemented):**
- Severity is classified with hysteresis and persistence context.
- Stage/degradation interpretation is derived from temporal + structural evidence.
- Policy enforcement ensures consistency (e.g., justified `HIGH` is not suppressed).

### Decision output

**Current behavior (implemented):**
- Decision output includes severity, suppression status, action horizon/action recommendation fields, and decision trace.
- Operator-facing guidance remains advisory and read-only.

### Explanation

**Current behavior (implemented):**
- Each decision includes a compact trace with:
  - `primary_factor`
  - `secondary_factors`
  - `confidence_rationale`

This gives a concise answer to: **what drove this decision, what reinforced it, and why confidence is at this level.**

---

## 3) PERFORMANCE CONTRACTS

These are engineering north-star contracts. Where thresholds are not finalized, they are stated as validation criteria.

| Layer / behavior | Contract type | Contract definition |
|---|---|---|
| Structural detection responsiveness | Target behavior (validation contract) | Material structural departures should register before late-stage hard-limit alarms in replay scenarios where relational drift precedes hard failure indicators. |
| Temporal consistency | Target behavior (validation contract) | Adjacent-frame decisions should remain directionally coherent unless evidence changes materially; oscillation without evidence change is a defect. |
| Stage stability | Target behavior (validation contract) | Stage/severity progression should avoid implausible jumps (for example direct calm-to-critical without supporting evidence), except in true shock conditions. |
| Decision coherence | Current behavior (implemented) + target behavior | Coherence rules enforce non-contradictory outputs (e.g., severe findings must align with urgency semantics; suppression and action fields must be logically consistent). |
| Alert repetition / suppression | Current behavior (implemented) + target behavior | Repetitive low-value alerts should be suppressed; sustained risk should re-emit with persistence-aware logic. |
| Explanation quality / trace completeness | Current behavior (implemented) + target behavior | Every emitted decision should carry a complete trace object with primary, secondary, and confidence rationale fields; missing trace is a validation failure. |
| Action timing consistency | Target behavior (validation contract) | Action urgency/horizon should track severity and trajectory consistently across similar trajectories. |

**Note:** Numeric thresholds (e.g., minimum lead time, allowed flip rate, latency SLOs) should be maintained in release-gate validation documents and run-level QA artifacts.

---

## 4) FAILURE MODES OF THE DECISION SYSTEM

Neraium is designed to degrade gracefully under weak or conflicting evidence.

### 4.1 Insufficient data

**Current behavior (implemented):**
- Warmup/insufficient-history conditions are represented explicitly in outputs.
- Confidence and recommendation strength remain constrained when evidence depth is low.

### 4.2 Conflicting evidence

**Current behavior (implemented):**
- If severity and transient/consistency evidence conflict, policy and coherence layers arbitrate and normalize outputs.
- Contradictory field combinations are corrected by coherence enforcement.

### 4.3 Unstable trajectory / weak pattern match

**Current behavior (implemented):**
- Weak pattern support reduces confidence influence.
- Unstable trajectories can maintain elevated monitoring while avoiding false precision in recommended action.

### 4.4 Runtime degradation / latency pressure

**Intended operational design:**
- Under compute or latency pressure, degrade by reducing non-critical analytical enrichments before compromising core structural detection and decision coherence.
- Preserve deterministic core outputs first; defer expensive optional layers.

### 4.5 Prediction-outcome divergence / drift

**Intended adaptation strategy:**
- Track divergence between expected progression and observed outcomes in replay/shadow and pilot feedback loops.
- Use this divergence as retraining/recalibration input, not as silent online model drift.

### 4.6 Safety rule

**Current behavior (implemented):**
- A justified `HIGH` severity decision is not suppressed by transient/noise gating.

Design objective: when uncertain, Neraium should emit bounded confidence and explicit uncertainty—not false certainty.

---

## 5) INTEGRATION SURFACE

Neraium is an interpretation/decision layer that inserts between telemetry and operational response workflows.

### 5.1 Ownership boundaries

- **Sensors:** owned by customer/operator systems.
- **Actuators/control logic:** owned by existing control systems and procedures.
- **Neraium ownership:** interpretation, temporal judgment, decision guidance, and evidence trace.

### 5.2 High-level interface contract

1. **Inbound telemetry/event stream**
   - Time-ordered multivariate measurements.
2. **Optional metadata/context**
   - Asset ID, subsystem tags, operating mode labels, maintenance annotations.
3. **Decision output**
   - Structured severity/risk/state/action guidance payload.
4. **Explanation output**
   - Decision trace object for operator interpretation and audit.
5. **Action signal surface**
   - Operator-facing recommendations and integration-friendly triggers (advisory, not direct actuation).

Neraium does not require replacement of upstream data systems or downstream maintenance/operations systems.

---

## 6) CALIBRATION & ADAPTATION

Neraium should improve over time without destabilizing operator trust.

### 6.1 Online adaptation

**Current behavior (implemented):**
- Temporal state, persistence, and pattern-memory influence update frame-to-frame within a run.
- This updates decision context but does not silently rewrite core policy contracts.

### 6.2 Offline retraining / recalibration

**Intended operational design:**
- Offline replay and corpus-based validation drive calibrated updates (thresholds, transition heuristics, pattern outcomes).
- Updates are promoted via engineering-reviewed release gates.

### 6.3 Operator feedback incorporation

**Intended operational design / proposed contract:**
- Capture structured override feedback categories:
  - false alarm
  - missed detection
  - timing too early
  - timing too late
- Use feedback as labeled evidence for recalibration queues rather than immediate autonomous policy rewrite.

### 6.4 Engineering-reviewed updates

**Current behavior (implemented) + intended process formalization:**
- Code/config changes are versioned and validated before release.
- Proposed update classes:
  - stage-transition tuning
  - new failure mode incorporation
  - pattern-outcome enrichment
  - suppression policy refinements

Operating principle: adaptation must increase predictive utility **without** reducing interpretability or consistency.

---

## 7) COMPUTATIONAL BUDGET

Neraium is designed for operational deployment, not just offline analysis.

### 7.1 Budget philosophy

**Target behavior (architectural budget model):**
- Keep the core path lightweight and deterministic.
- Prioritize bounded latency for structural detection + decision emission.
- Treat advanced enrichments as optional where needed.

### 7.2 Budget by functional block

| Block | Budget intent |
|---|---|
| Structural analysis | Primary compute budget; optimized for per-frame incremental operation. |
| Temporal reasoning | Low incremental overhead (stateful updates, persistence tracking). |
| Stage/severity assignment | Deterministic policy logic; minimal additional compute. |
| Decision generation | Lightweight recommendation and coherence enforcement. |
| Evidence trace generation | Compact string/field construction; low overhead. |
| Visualization/UI updates | External to core engine contract; should not block core decision emission path. |

### 7.3 Latency statement

- **Current behavior (implemented in project docs):** low-latency per-frame processing is a design objective and is reported in project readiness artifacts.
- **Target behavior:** maintain sub-second and practically real-time decision cadence under expected pilot load.
- Any specific hard latency number should be treated as environment-specific until validated on target deployment hardware and workload.

---

## 8) EVIDENCE TRACE FORMAT

Neraium uses a fixed compact decision-trace schema to keep explanations testable and auditable.

### 8.1 Contract

```json
{
  "decision_trace": {
    "primary_factor": "...",
    "secondary_factors": ["...", "..."],
    "confidence_rationale": "..."
  }
}
```

### 8.2 Why this format exists

- `primary_factor`: forces explicit prioritization of the top driver.
- `secondary_factors`: records reinforcing context without unbounded verbosity.
- `confidence_rationale`: states why confidence is high/medium/low in plain operational language.

### 8.3 Operational value

- Improves operator trust by exposing structured reasons instead of opaque scores.
- Supports audit trails and post-incident review.
- Enables deterministic test checks for explanation completeness and quality.

---

## 9) DEPLOYMENT TOPOLOGY

### Intended deployment topology (intended operational design)

1. **Edge / site-local inference**
   - Ingest telemetry and run core structural + decision inference close to the data source for low-latency guidance.
2. **Regional / fleet aggregation**
   - Aggregate decision events, trace logs, and outcomes across assets/sites for fleet-level pattern visibility.
3. **Central model/release layer**
   - Run offline replay validation, curate failure-mode libraries, and publish reviewed updates.

### Why this split

- Keeps real-time decisions close to operations.
- Keeps adaptation/retraining controlled and reviewable.
- Supports multi-asset learning without coupling online inference stability to experimental updates.

---

## 10) Operational positioning summary

Neraium is decision infrastructure for physical systems where behavior changes before failures become obvious. It provides:

- structural detection of system self-divergence,
- temporal interpretation of how that divergence is evolving,
- coherent advisory action guidance,
- auditable explanation traces,
- and explicit boundaries for safety and integration.

It remains read-only and human-in-the-loop by design.
