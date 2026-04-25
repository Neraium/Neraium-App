# Neraium Grow

Neraium Grow is the default product in this repository. It is a read-only, vendor-neutral intelligence layer for cultivation operations that scales from single-plant risk to portfolio-wide operational intelligence.

Neraium shows where the grow is drifting, why, and where inefficiencies are spreading before yield is impacted.

Markets remains in the repo under `neraium_core.markets` as a legacy, non-default module.

## Supported scopes

- Plant
- Zone
- Room
- Subsystem
- Facility
- Portfolio

The same structural analytics engine powers every scope, but the product presents the results differently:

- Plant: measured plant state when direct plant telemetry exists, otherwise inferred plant-risk view from local microclimate and zone context
- Zone: microclimate consistency, irrigation response, airflow balance, and peer-zone divergence
- Room: hero operational decision view with drift, driver, biological risk, threshold contrast, and time-to-impact
- Subsystem: root-cause and upstream/downstream effect view for HVAC, dehumidification, irrigation, fertigation, lighting, CO2, water, and power
- Facility: ranking and intervention prioritization across rooms, zones, plants, and subsystems
- Portfolio: multi-site comparison, recurring inefficiency patterns, and readiness across facilities

## What the product answers at every scope

1. What state is it in?
2. What is drifting?
3. What is driving it?
4. What should I do?

Primary states:

- `STABLE`
- `DRIFTING`
- `AT_RISK`
- `DEGRADING`

Biological risk states:

- `LOW_BIOLOGICAL_RISK`
- `ELEVATED_BIOLOGICAL_RISK`
- `YIELD_RISK_EMERGING`
- `QUALITY_RISK_EMERGING`

## Inefficiency, not just alarms

Neraium Grow does more than say risk is elevated. It explicitly reports:

- Energy inefficiency
- Climate inefficiency
- Process inefficiency
- Biological inefficiency

Threshold alarms look at individual points. Neraium Grow looks at structural behavior, peer comparison, baseline comparison, and cross-system response. It can surface hidden drift before any hard threshold is crossed, including the message:

`No individual sensor exceeded thresholds at this point`

## Telemetry

Grow supports identity/context fields for:

- `timestamp`
- `facility_id`
- `site_id`
- `building_id`
- `room_id`
- `zone_id`
- `plant_id`
- `asset_id`
- `asset_type`
- `subsystem_id`
- `controller_id`
- `crop_type`
- `strain_or_crop_type`
- `growth_stage`
- `batch_id`

It also supports telemetry from climate, HVAC/refrigeration/dehumidification, irrigation/fertigation/drainage, lighting, CO2, airflow/pressure, power, biological proxies, and operator workflow events.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python run_demo.py
```

Open [http://localhost:8000](http://localhost:8000).

## Docker

```bash
docker build -t neraium-grow .
docker run --rm -p 8000:8000 neraium-grow
```

## Demo

The built-in demo supports:

- Plant clusters
- Zones
- Rooms
- Subsystems
- Facility comparison
- Multi-site portfolio comparison

Run the demo:

```bash
python run_demo.py
```

Then use the scope selector in the default UI to move between Plant, Zone, Room, Subsystem, Facility, and Portfolio views.

## Key docs

- [docs/GROW_OVERVIEW.md](/Users/Owner/Documents/neraium-core/docs/GROW_OVERVIEW.md)
- [docs/GROW_SCOPES.md](/Users/Owner/Documents/neraium-core/docs/GROW_SCOPES.md)
- [docs/GROW_COMPARE.md](/Users/Owner/Documents/neraium-core/docs/GROW_COMPARE.md)
- [docs/GROW_OPERATOR_GUIDE.md](/Users/Owner/Documents/neraium-core/docs/GROW_OPERATOR_GUIDE.md)
- [docs/GROW_DECISION_MODEL.md](/Users/Owner/Documents/neraium-core/docs/GROW_DECISION_MODEL.md)
- [docs/GROW_DEMO.md](/Users/Owner/Documents/neraium-core/docs/GROW_DEMO.md)

## Legacy retained

- `neraium_core.markets`
- `run_live_stock_market.py`
- `tests/markets/`
