# Neraium

**See structural instability before systems fail.**

Neraium is a real-time Structural Intelligence Platform that analyzes multivariable telemetry to identify instability, drift, and degradation before conventional alarms or threshold-based monitoring detect a problem.

Rather than monitoring individual sensors independently, Neraium evaluates the relationships between variables to understand how an entire system is behaving. This allows operators to identify emerging problems earlier, understand what is changing, determine why it is happening, and take action before failures occur.

---

## What Neraium Does

Neraium continuously analyzes telemetry to:

- Detect structural instability
- Identify abnormal system behavior
- Explain the underlying drivers of change
- Prioritize operator actions
- Monitor system health in real time
- Reduce downtime through earlier detection

Unlike traditional monitoring systems that rely on individual sensor thresholds, Neraium evaluates how an entire system evolves over time.

---

## Current Product

### Neraium Grow

Neraium Grow is a read-only intelligence platform for controlled-environment agriculture.

It analyzes telemetry across:

- Climate
- HVAC
- Irrigation
- Fertigation
- Lighting
- CO2
- Airflow
- Water systems
- Power systems

The same intelligence engine scales across multiple operational levels:

- Plant
- Zone
- Room
- Subsystem
- Facility
- Portfolio

---

## Platform Architecture

### Backend

- Python
- FastAPI
- MongoDB
- Motor
- Pydantic

### Intelligence Engine

The Structural Intelligence Engine, or SII, provides:

- Structural drift detection
- Stability analysis
- Transition detection
- Instability scoring
- Lead-time estimation
- Cross-variable relationship analysis

### Frontend

- Real-time operational dashboard
- Live telemetry visualization
- Operator decision interface
- Interactive system diagnostics
- Demonstration environments

---

## API

### Ingest Telemetry

```http
POST /api/ingest/{api_key}
```

Registers telemetry, updates the structural model, and returns the current system state.

### Demo

```http
GET /api/demo/pronostia
```

Runs the PRONOSTIA bearing degradation demonstration.

---

## Getting Started

Clone the repository:

```bash
git clone https://github.com/Neraium/Neraium-App.git
cd Neraium-App
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

### Windows

```bash
.venv\Scripts\activate
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e .
```

Run the API:

```bash
uvicorn backend.server:app --reload
```

Open the local API at:

```text
http://localhost:8000
```

---

## Docker

Build the container:

```bash
docker build -t neraium .
```

Run the container:

```bash
docker run --rm -p 8000:8000 neraium
```

---

## Current Capabilities

- Real-time telemetry ingestion
- Structural instability detection
- Drift analysis
- State transition modeling
- Live API
- Customer API key management
- Interactive demonstrations
- Historical playback
- Operator diagnostics

---

## Vision

Neraium is building a general-purpose Structural Intelligence Platform capable of monitoring any telemetry-driven system.

The same intelligence engine is designed to support industries including:

- Agriculture
- Manufacturing
- Industrial equipment
- Energy
- Water infrastructure
- Building automation
- Process control
- Predictive maintenance

Rather than creating separate analytics for every industry, Neraium applies a common structural intelligence model to understand how complex systems behave, detect instability early, and help operators make better decisions.

---

## License

This repository is provided for demonstration and evaluation purposes unless otherwise specified.
