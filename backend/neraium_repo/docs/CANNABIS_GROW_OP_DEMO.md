# Cannabis Grow Operation Demo — Neraium

Neraium monitors multivariate environmental telemetry across a grow zone and detects structural instability before it causes crop damage. This demo replays a realistic heat stress event across 130 frames of 15-minute data.

---

## Sensors Monitored

| Sensor | Key | Unit | Nominal Range |
|---|---|---|---|
| Canopy Temperature | `temperature_f` | °F | 68–82 |
| Relative Humidity | `humidity_rh` | % | 45–70 |
| CO₂ Concentration | `co2_ppm` | ppm | 800–1600 |
| Vapor Pressure Deficit | `vpd_kpa` | kPa | 0.6–1.4 |
| Reservoir pH | `ph` | pH | 5.5–6.5 |
| Electrical Conductivity | `ec_ms` | mS/cm | 1.0–2.2 |
| Light Intensity (PPFD) | `ppfd_umol` | µmol/m²/s | 400–750 |
| Irrigation Volume | `irrigation_ml` | mL/event | 100–350 |

---

## Demo Phases

### Phase 1 — `stable_veg` (40 frames, ~10 hours)
Week 4 vegetative stage. All 8 sensors within nominal range. Neraium builds a structural baseline fingerprint of the healthy grow environment.

### Phase 2 — `drift_onset` (40 frames, ~10 hours)
HVAC unit begins underperforming. Temperature creeps upward, humidity drops, VPD climbs outside the safe band. Neraium detects multi-sensor structural divergence from baseline — **early warning before any single sensor crosses a threshold alarm**.

### Phase 3 — `heat_stress` (30 frames, ~7.5 hours)
Full structural instability. Canopy at 89–92°F. VPD 3.0+ kPa. Stomata close, irrigation uptake collapses, CO₂ depletion accelerates, pH swings out of range. Neraium flags a **multi-sensor structural collapse** and issues an intervention recommendation.

### Phase 4 — `intervention_recovery` (12 frames, ~3 hours)
Operator acts on Neraium's alert. HVAC reset, CO₂ supplementation increased, pH corrected. All sensors return to baseline nominal range. Neraium confirms structural recovery.

---

## Quick Start

### 1. Start the API
```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Run the full demo
```bash
python tools/seed_grow_op_demo.py
```

### 3. Run a specific phase only
```bash
# Baseline only
python tools/seed_grow_op_demo.py --phase stable_veg

# Show the drift detection
python tools/seed_grow_op_demo.py --phase drift_onset

# Trigger full alert
python tools/seed_grow_op_demo.py --phase heat_stress

# Show recovery
python tools/seed_grow_op_demo.py --phase intervention_recovery
```

### 4. Run against a deployed instance
```bash
python tools/seed_grow_op_demo.py --base-url https://your-deployment.up.railway.app
```

### 5. View results
- Dashboard: http://localhost:8000/app?customer_id=grow-op-demo
- Output bundle: `outputs/grow_op_demo_result.json`

---

## What Neraium Detects

Neraium does **not** use single-sensor threshold alarms. It detects structural breakdown in the **relationships between sensors** — the geometry of the multi-dimensional state space.

In this demo:
- Phase 1: Stable manifold geometry → no alert
- Phase 2: Manifold begins diverging from baseline → early structural warning
- Phase 3: Full geometric collapse across 8 sensors simultaneously → intervention alert
- Phase 4: Manifold converging back toward baseline → recovery confirmed

This catches the HVAC failure in Phase 2 — **before** temperature alone crosses any alarm threshold — because the structural relationship between temperature, humidity, and VPD has already broken down.

---

## Scenario File

`examples/demo/cannabis_grow_op_scenario.json`

The scenario JSON contains all sensor values for all 122 frames across 4 phases. It can be edited to represent different grow stages (flowering, late flower, etc.) or different failure modes (pH drift, nutrient lockout, light stress).

---

## Adapting for Other Grow Scenarios

| Scenario | Change |
|---|---|
| Flowering stage | Adjust targets: temp 65–78°F, RH 40–50%, VPD 1.0–1.5 kPa |
| Nutrient lockout | Drive `ec_ms` and `ph` drift while keeping climate stable |
| Mold risk | Drive humidity above 70% with temp dropping |
| Light stress | Drive `ppfd_umol` above 900 with VPD elevation |
| CO₂ system failure | Drop `co2_ppm` while other sensors remain stable |
