# Datacenter Cooling System Demo Guide

## Overview

This demo showcases the **3-layer dashboard** applied to a realistic datacenter CRAC (Computer Room Air Conditioner) unit degradation scenario. It tells the story of a cooling system's decline from baseline operation through failure approach, demonstrating how Neraium detects problems *before* they become critical.

## The Scenario

**CRAC-Unit-North-01** experiences gradual mechanical degradation over 48+ hours:

### Stage 1: **Baseline** (Normal Operation)
- 🟢 All metrics nominal
- Fan speed optimal
- Discharge temperature stable at 18°C
- System operating within design parameters
- **Action**: Continue routine monitoring

### Stage 2: **Early Drift** (Subtle Efficiency Loss)
- 🟡 Cooling efficiency degrading
- Fan operating hours increased 12%
- Discharge temperature rising: 18°C → 21°C
- Airflow-temperature correlation beginning to weaken
- **Pattern**: Filter loading or bearing wear
- **Action**: Schedule inspection within 48 hours

### Stage 3: **Structural Shift** (Correlation Breakdown)
- 🟠 Structural relationships breaking down
- Discharge temp now 26°C despite higher fan speed
- Coolant loop pressure fluctuating
- 3+ corroborating signals detected
- **Pattern Match**: Compressor degradation (strong confidence)
- **Action**: IMMEDIATE maintenance required

### Stage 4: **Pre-instability** (Rapid Decompensation)
- 🔴 System approaching failure
- Discharge temperature critical: 32°C
- Coolant pressure at 85% of safe limit
- Vibration sensors flagging bearing distress
- 6 simultaneous warning conditions
- **Estimated Impact**: 2-4 hours before thermal runaway
- **Action**: CRITICAL - Activate redundant cooling NOW

## The Key Insight

Traditional monitoring would show **alerts after thresholds are crossed**. Neraium shows **how the system is evolving toward failure**, giving operators 8-16 hours of lead time to take preventive action instead of reactive firefighting.

## How to Run

### Option 1: Browser (Quickest)

```bash
cd frontend
npm install  # (if not already done)
npm run dev
```

Then open: **http://localhost:3000**

The demo auto-advances through all 4 stages (~60 seconds total), then stops.

### Option 2: Full Stack Setup

```bash
# Terminal 1: Start frontend
cd frontend
npm run dev

# Terminal 2: Start backend (if applicable)
cd backend
python app.py  # or your backend command
```

### Option 3: Docker (Production-like)

```bash
docker-compose up
# View at http://localhost:3000
```

## What to Look For

As the demo progresses, observe:

### **Layer 1: System Overview**
- How the metric counts change (healthy → drifting → unstable)
- The colored dots shifting from green → yellow → orange → red

### **Layer 2: System State & Trajectory**
- The **state progression timeline** lighting up each stage as it's reached
- The **drift curve** rising gradually, then steeply
- **Contributing factors** becoming more numerous and severe

### **Layer 3: Action Recommendations**
- How the **horizon** changes: Watchlist → Soon → Now → Critical
- **Primary actions** evolving from "continue monitoring" to "activate redundant cooling"
- Supporting evidence accumulating (2 factors → 3 → 4 → 6)

## Demo Architecture

### Components Used:
- **SystemOverview**: Fleet-level health metrics (5 key counts)
- **SystemStateTrajectory**: Per-system evolution with timeline + drift curve
- **ActionRecommendations**: Urgency-based action items with confidence/evidence
- **CoolingSystemDemo**: Wrapper that auto-advances through scenarios

### Data Files:
- `frontend/lib/coolingSystemDemo.ts` — 4 realistic cooling system states
- `frontend/components/CoolingSystemDemo.tsx` — Demo auto-player with narrative
- `frontend/app/page.tsx` — Currently renders the main 3-layer dashboard

## Customizing the Demo

### To change auto-advance timing:
Edit `frontend/lib/coolingSystemDemo.ts`:
```typescript
export const COOLING_DEMO_SCENARIOS = [
  {
    name: '...',
    state: ...,
    durationMs: 45000,  // ← Change this (milliseconds)
                        // 45000ms = 45 seconds per stage
                        // 4 stages × 45s = 3 minutes total
    narrative: '...',
  },
]
```

For example:
- `30000` (30s per stage) = 2 minute demo
- `45000` (45s per stage) = 3 minute demo (current)
- `60000` (60s per stage) = 4 minute demo

### To add more stages:
1. Add a new scenario to `coolingSystemDemo.ts`
2. Add it to `COOLING_DEMO_SCENARIOS` array
3. The demo will auto-advance through it

### To customize metrics:
Edit `CoolingSystemDemo.tsx` in the `systemHealthMetrics` useMemo:
```typescript
const systemHealthMetrics = useMemo(() => ({
  healthy: ...,      // Total green systems
  drifting: ...,     // Total yellow systems
  unstable: ...,     // Total red systems
  earlyWarnings: ..., // Active warnings
  enteringInstability: ..., // Systems at risk
}), [scenarioIndex])
```

## Real-World Applications

This cooling system demo directly maps to:

| Scenario | Real Failure Mode | Lead Time | Action Required |
|----------|------------------|-----------|-----------------|
| **Baseline** | None | — | Monitor |
| **Early Drift** | Filter clogging, fan bearing wear | 12-24h | Preventive service |
| **Structural Shift** | Compressor mechanical failure | 8-12h | Schedule replacement |
| **Pre-instability** | Thermal runaway imminent | 2-4h | Activate backup, isolate unit |

## Expected Behavior

1. **0:00-0:45** → Baseline (green, stable, "continue monitoring")
2. **0:45-1:30** → Early Drift (yellow, uncertain, "schedule inspection within 48h")
3. **1:30-2:15** → Structural Shift (orange, degrading, "immediate maintenance required")
4. **2:15-3:00** → Pre-instability (red, degrading, "CRITICAL: activate redundant cooling NOW")
5. **3:00** → Demo stops, shows final state

You can watch the entire lifecycle of system degradation over 3 minutes, giving you plenty of time to observe each transition.

Progress bar at the bottom shows overall demo progress, and the stage indicator shows which of the 4 stages you're currently viewing.

## Troubleshooting

### Page shows 404 or blank
- Make sure you're in the `frontend` directory
- Run `npm install` if dependencies aren't installed
- Check that `npm run dev` shows "Ready in X.Xs"

### Scenarios don't auto-advance
- Check browser console for errors (F12)
- Make sure JavaScript is enabled
- Try clearing browser cache and reloading

### Styling looks off
- This is a dark-mode UI by design
- Try zooming to 100% (Ctrl+0 or Cmd+0)
- Works best in Chrome, Firefox, Safari (latest versions)

## Next Steps

After the demo:
1. **Modify a scenario** to reflect your infrastructure
2. **Connect real data** via the backend API
3. **Integrate with your DCIM/monitoring stack**
4. **Set custom thresholds** for your equipment

---

**Questions?** Check the main README.md or ARCHITECTURE.md files.
