# Integration Layer: Decision → UI State

Complete documentation of the decision-to-UI transformation architecture.

## Architecture Overview

```
Gate Decision Engine (backend)
           ↓
    [GateDecision]  +  [Telemetry Records]
           ↓
    Integration Layer
    (decision_to_ui.py / decisionToUI.ts)
           ↓
    [DecisionUIState]
           ↓
    UI Components
    (StatusHeader, ActionPanel, Tetrahedron, etc)
           ↓
    Decision System Interface
```

The integration layer is the **single source of truth** for mapping backend decision output to UI rendering state. No UI component should derive its own state from raw decision data—all transformation happens here.

---

## Core Principles

1. **No Metric Exposure** — Raw feature values never reach UI components
2. **No Internal Variables** — Only decision output and interpreted labels
3. **Single Transformation Pass** — Decision → UI State happens once per frame
4. **Type Safety** — TypeScript/Python types enforce contracts
5. **Testability** — Pure functions with deterministic output
6. **Decision-Centric** — Everything derives from gate decision + telemetry

---

## Data Flow

### Input: Gate Decision

From `AletheiasGate.evaluate()`:

```python
{
    "decision": "ADMIT" | "SUPPRESS" | "VOID",
    "confidence_label": "LOW" | "MEDIUM" | "HIGH",
    "confidence_value": 0.0-1.0,
    "explanation": "Human-readable explanation",
    "refusal_reason": "If SUPPRESS/VOID, why?",
    "doctrine_version": "v1.2",
    "transition": {
        "type": "STABLE" | "TRANSITION" | "REORGANIZATION",
        "delta_drift": float,
        "delta_stability": float,
        "delta_coherence": float,
    },
    "pattern_match": {
        "tier": "weak" | "moderate" | "strong",
        "outcome_type": "failure-progressing" | "recovery" | "neutral",
        "influence_summary": "string"
    }
}
```

### Input: Telemetry Records

Historical system state (most recent last):

```python
[
    {
        "timestamp": "ISO 8601",
        "structural_drift_score": 0.0-1.0,
        "relational_stability_score": 0.0-1.0,
        "coherence_score": 0.0-1.0,
        "persistence_minutes": int,
        "corroborating_signal_count": int,
        "delta_drift": float,
        "delta_stability": float,
        "event_admitted": bool,
    },
    # ... more records ...
]
```

### Output: DecisionUIState

Complete state ready for rendering (no further transformation needed):

```typescript
{
    statusHeader: {
        degradationStage: "baseline" | "early_shift" | "emerging" | "persistent" | "accelerated" | "failure_approach",
        severity: "LOW" | "MODERATE" | "ELEVATED" | "HIGH",
        trajectory: "Stable" | "Degrading" | "Uncertain",
        confidence: "LOW" | "MEDIUM" | "HIGH",
    },
    actionPanel: {
        horizon: "now" | "soon" | "watchlist",
        primaryAction: "string",
        urgencyLevel: 1-5,
    },
    tetrahedron: {
        currentPosition: { x: 0-1, y: 0-1, z: 0-1 },
        severityScalar: 0.0-1.0,
        trailPoints: [
            { position: Point3D, timestamp: string, frameIdx: int },
            // ... up to 20 points
        ],
        velocity: [float, float, float],
        nearestVertex: "STRUCTURAL" | "RELATIONAL" | "TEMPORAL" | "AUTHORITY",
    },
    decisionTrace: {
        primaryFactor: "string",
        secondaryFactors: ["string", "string"],
        confidenceRationale: "string",
        patternInsight?: {
            tier: "moderate" | "strong",
            outcomeType: "string",
            influenceSummary: "string",
        },
    },
    timeline: {
        stages: [
            { stage: DegradationStage, label: string, isCurrent: bool },
            // ... all 6 stages
        ],
        currentIndex: int,
    },
    driftChart: {
        dataPoints: [
            { timestamp: string, driftScore: 0-1, frameIdx: int },
            // ... up to 24 points
        ],
        detectionThreshold: 0.2,
        currentFrameIdx: int,
    },
    timestamp: string,
}
```

---

## Transformation Functions

### 1. Status Header

**Input**: Gate decision + records  
**Output**: `StatusHeader` with degradation stage, severity, trajectory, confidence

**Logic**:

```
degradationStage = map(drift_score, persistence_minutes)
  baseline        (drift < 0.25)
  early_shift     (0.25 ≤ drift < 0.40)
  emerging        (0.40 ≤ drift < 0.55)
  persistent      (0.55 ≤ drift < 0.70 AND persistence < 120 min)
  accelerated     (0.70 ≤ drift < 0.85)
  failure_approach (drift ≥ 0.85)

severity = map(confidence_label, drift, stability)
  HIGH          (confidence_label="HIGH" AND max(drift, 1-stability) ≥ 0.6)
  ELEVATED      (confidence_label="HIGH" OR max(drift, 1-stability) ≥ 0.5)
  MODERATE      (confidence_label="MEDIUM" OR max(drift, 1-stability) ≥ 0.3)
  LOW           (otherwise)

trajectory = map(delta_drift, delta_stability)
  DEGRADING     (delta_drift > 0.08 OR delta_stability < -0.08)
  UNCERTAIN     (abs(delta_drift) > 0.03 OR abs(delta_stability) > 0.03)
  STABLE        (otherwise)
```

### 2. Action Panel

**Input**: Gate decision + severity  
**Output**: `ActionPanel` with horizon and urgency

**Logic**:

```
horizon, urgency = map(decision, severity)
  (NOW, 5)        (decision="ADMIT" AND severity IN {HIGH, ELEVATED})
  (SOON, 3)       (decision="ADMIT")
  (WATCHLIST, 1)  (otherwise)
```

### 3. Tetrahedron State

**Input**: Gate decision + latest record  
**Output**: `TetrahedronState` with position, trail, velocity

**Position Mapping** (0-1 space → tetrahedron interior):

```
x = severity_score
  0.8 if confidence="HIGH"
  0.5 if confidence="MEDIUM"
  0.2 otherwise

y = confidence_score
  0.85 if confidence="HIGH"
  0.5 if confidence="MEDIUM"
  0.2 otherwise

z = trajectory_rate
  min(1.0, abs(delta_drift) * 2.0 + persistence_minutes / 300.0)
```

**Trail**: Last 20 records converted to 3D positions  
**Velocity**: Magnitude of recent changes  
**Nearest Vertex**: Which structural dimension is dominant

### 4. Decision Trace

**Input**: Gate decision + records  
**Output**: `DecisionTrace` with primary/secondary factors

**Primary Factor Priority**:
1. If persistence > 60 min: "High severity persisted X minutes"
2. Elif drift ≥ 0.6: "Structural drift reached X%"
3. Elif stability < 0.4: "Relational stability dropped to X%"
4. Else: explanation from gate decision

**Secondary Factors** (up to 2):
- Corroborating signals
- Significant drift changes

**Pattern Insight**: Only shown if tier ∈ {moderate, strong}

### 5. System Timeline

**Input**: Records  
**Output**: `SystemTimeline` with all 6 stages

All degradation stages shown with current stage highlighted.

### 6. Drift Chart

**Input**: Last 24 records  
**Output**: `DriftChart` with time-series data

Simple time-series of structural_drift_score over last 24 cycles.

---

## Tetrahedron Vertex Mapping

The four vertices of the tetrahedron represent structural dimensions:

```
STRUCTURAL (1, 1, 1)
  - Represents: System coherence & integrity
  - Components: drift_score, coherence_score
  - Color: CYAN

RELATIONAL (1, -1, -1)
  - Represents: Stability & relationship strength
  - Components: stability_score, snr_score
  - Color: GREEN

TEMPORAL (-1, -1, 1)
  - Represents: Persistence & degradation rate
  - Components: persistence_minutes, delta_drift
  - Color: AMBER

AUTHORITY (-1, 1, -1)
  - Represents: Gate decision & confidence
  - Components: confidence_label, decision
  - Color: BLUE
```

System state as point inside tetrahedron:
- **Center** (0.5, 0.5, 0.5) = stable, uncertain system
- **Toward vertices** = system emphasizing that dimension
- **Edge/corner** = extreme state in that dimension

---

## Color Mapping

**Severity → Display Color**:

| Severity | Scalar | Hex Color | Status |
|----------|--------|-----------|--------|
| LOW | 0.2 | #22c55e | GREEN |
| MODERATE | 0.5 | #eab308 | YELLOW |
| ELEVATED | 0.75 | #f97316 | ORANGE |
| HIGH | 0.95 | #ef4444 | RED |

Applied to:
- Tetrahedron state point
- Trail visualization
- Status header background
- Action panel accent

---

## Usage Examples

### Python (Backend)

```python
from ui.decision_to_ui import transform_decision_to_ui_state

# Receive decision from gate
gate_decision = gate.evaluate(gate_input)

# Get telemetry records
records = load_recent_records(limit=100)

# Transform
ui_state = transform_decision_to_ui_state(gate_decision, records)

# Render (Gradio, etc)
render_status_header(ui_state.status_header)
render_action_panel(ui_state.action_panel)
# ... etc
```

### TypeScript (Frontend)

```typescript
import { transformDecisionToUIState } from '@/lib/decisionToUI'
import EnhancedTetrahedronViz from '@/components/EnhancedTetrahedronViz'

const uiState = transformDecisionToUIState(gateDecision, records)

return (
  <>
    <StatusHeader {...uiState.statusHeader} />
    <ActionPanel {...uiState.actionPanel} />
    <EnhancedTetrahedronViz tetrahedronState={uiState.tetrahedron} />
    <DecisionTrace {...uiState.decisionTrace} />
    {/* ... etc */}
  </>
)
```

---

## Testing Strategy

### Unit Tests (TypeScript)

Located in `/frontend/lib/__tests__/decisionToUI.test.ts`:

- ✓ High severity decision → correct status + action
- ✓ Low severity decision → WATCHLIST horizon
- ✓ Trajectory detection (degrading vs stable vs uncertain)
- ✓ Trail generation limits (≤20 points)
- ✓ Tetrahedron position bounds (0-1 in each axis)
- ✓ Severity scalar mapping
- ✓ Nearest vertex identification
- ✓ Drift chart limits (≤24 points)
- ✓ Timeline stage generation
- ✓ Pattern insight filtering

Run tests:
```bash
cd frontend
npm test -- decisionToUI.test.ts
```

### Integration Tests

Test full pipeline:
1. Create sample decision + records
2. Transform to UI state
3. Verify all fields populated correctly
4. Verify no metric values exposed
5. Verify visualization renders without error

### Demo Component

`/frontend/components/DecisionSystemDemo.tsx` provides:
- Sample decision + records
- Transformation display
- Debug info panel
- Live tetrahedron visualization

Run:
```bash
cd frontend
npm run dev
# Navigate to demo page
```

---

## Invariants (Must Always Hold)

1. **No Raw Metrics** — UI components never see `structural_drift_score`, `relational_stability_score`, etc.
2. **Decision Determines Action** — Action horizon comes exclusively from decision output
3. **Trail ≤ 20 Points** — Memory efficient, prevents visual clutter
4. **Chart ≤ 24 Points** — Reasonable time window for visualization
5. **All Position Scalars ∈ [0, 1]** — Valid tetrahedron coordinates
6. **Current Point Always Last Trail Point** — Consistency between tetrahedron and trail
7. **Pattern Insight Only if Moderate+** — Filter weak signals at transformation layer
8. **Severity Guides Color** — No contradictions between status and display color

---

## Adding New Transformations

To add a new derived field:

1. Add to `DecisionUIState` TypeScript/Python type
2. Implement extraction function (pure, deterministic)
3. Add unit test for edge cases
4. Document in this file
5. Verify no metric leakage
6. Update components using new field

Example:

```typescript
// 1. Add to type
interface DecisionUIState {
  // ... existing fields ...
  newField: NewType
}

// 2. Implement function
function extractNewField(decision: any, records: any[]): NewType {
  // Pure, deterministic logic
  return computed_value
}

// 3. Test
test('new field extraction', () => {
  const result = extractNewField(sampleDecision, sampleRecords)
  expect(result).toBe(expectedValue)
})

// 4. Use in main transform
export function transformDecisionToUIState(...) {
  // ...
  const newField = extractNewField(gateDecision, records)
  return DecisionUIState({ newField, ... })
}
```

---

## Performance Considerations

- **Transform cost**: O(n) where n = number of records (usually ≤100)
- **Tetrahedron render**: O(1) - fixed geometry + trail
- **Trail generation**: O(20) - constant limit
- **Memory**: < 100KB per UI state (all types are lightweight)

Typical transform time: < 5ms on modern hardware

---

## Future Enhancements

1. **Streaming Mode** — Incremental trail updates without full retransform
2. **Predictive Projections** — Extend trail with predicted trajectory
3. **Multi-System Overlay** — Compare multiple system tetrahedra
4. **Historical Playback** — Replay decision sequences with animation
5. **Confidence Intervals** — Uncertainty visualization in trail
6. **Domain-Specific Coloring** — Industry/scenario-specific color schemes

---

## Related Files

- **Backend Integration**: `/ui/decision_to_ui.py`
- **Frontend Integration**: `/frontend/lib/decisionToUI.ts`
- **Tetrahedron Viz**: `/frontend/components/EnhancedTetrahedronViz.tsx`
- **Demo**: `/frontend/components/DecisionSystemDemo.tsx`
- **Tests**: `/frontend/lib/__tests__/decisionToUI.test.ts`
- **Gate Decision Engine**: `/neraium_core/gate/engine.py`
- **Telemetry Schema**: `/ui/core_integration.py`
