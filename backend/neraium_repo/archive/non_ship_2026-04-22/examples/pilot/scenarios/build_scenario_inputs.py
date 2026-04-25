#!/usr/bin/env python3
"""
Generate deterministic pilot JSON inputs (payload sequences).

Writes:
  regime_shift_inputs.json
  structural_instability_inputs.json

Run from repo root:
  python examples/pilot/scenarios/build_scenario_inputs.py
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

N_STEPS = 120
START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _payload(t: int, site_id: str, asset_id: str, sensors: dict[str, float]) -> dict:
    ts = (START + timedelta(seconds=t)).isoformat()
    return {
        "timestamp": ts,
        "site_id": site_id,
        "asset_id": asset_id,
        "sensor_values": {k: round(float(v), 6) for k, v in sensors.items()},
    }


def _smoothstep01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x * x * (3.0 - 2.0 * x)


def regime_shift_series(t: int, n: int = N_STEPS) -> dict[str, float]:
    """
    Two internally coherent regimes on one smooth smoothstep blend. **No wobble** on the
    blend weight: oscillating ``w`` spiked ``directional_divergence`` and forced
    COHERENCE/COUPLING instead of **REGIME_SHIFT_OBSERVED** in ``_interpret_state``.

    Regime B is kept **close** to A so ``relational_drift`` sits in ~1.15–1.35 for several
    consecutive steps (composite ``latest_instability`` stays **< 2.0** - no ALERT).

    Input JSON sets ``interpreted_smoothing: {"consecutive_required": 1}`` so a single raw
    REGIME_SHIFT tick can appear in pilot ``interpreted_state`` (see ``run_pilot._load_pilot_input``).
    """
    ft = float(t)
    u = ft / max(n - 1, 1)

    lift = 1.23 * (u**1.085)

    # Mid-run cross-fade (narrower than 52-step variant - wide fades raised coupling / composite)
    w = _smoothstep01((ft - 34.0) / 36.0)

    # --- Regime A (baseline)
    drv_a = math.sin(0.047 * ft) + 0.085 * math.sin(0.0155 * ft)
    base_a = 10.0 + 0.30 * drv_a + 0.50 * lift
    s1a = base_a
    s2a = 0.992 * base_a + 0.078
    s3a = 1.005 * base_a - 0.045
    s4a = 0.998 * base_a + 0.055

    # --- Regime B: closer to A (reduces directional spikes vs a stronger rescale)
    drv_b = 0.68 * math.sin(0.0595 * ft + 0.86) + 0.19 + 0.078 * math.sin(0.014 * ft)
    base_b = 10.0 + 0.32 * drv_b + 0.52 * lift
    s1b = base_b
    s2b = 0.944 * base_b + 0.094 + 0.008 * math.sin(0.046 * ft)
    s3b = 0.989 * base_b + 0.072 + 0.007 * math.sin(0.044 * ft + 0.26)
    s4b = 0.968 * base_b + 0.096 + 0.007 * math.sin(0.047 * ft + 0.55)

    s1 = (1.0 - w) * s1a + w * s1b
    s2 = (1.0 - w) * s2a + w * s2b
    s3 = (1.0 - w) * s3a + w * s3b
    s4 = (1.0 - w) * s4a + w * s4b
    return {"s1": s1, "s2": s2, "s3": s3, "s4": s4}


def structural_instability_series(t: int, n: int = N_STEPS, rng: np.random.Generator | None = None) -> dict[str, float]:
    """
    Early tight coupling; later growing variance and diverging structure (no missing data).
    """
    if rng is None:
        rng = np.random.default_rng(20260320)

    t_break = 28
    if t < t_break:
        base = 10.0 + 0.012 * (t / max(t_break - 1, 1))
        phase = t / 4.8
        eps = 0.018
        s1 = base + 0.06 * math.sin(phase) + float(rng.normal(0.0, eps))
        s2 = base + 0.10 + 0.05 * math.sin(phase + 0.3) + float(rng.normal(0.0, eps))
        s3 = base + 0.05 + 0.055 * math.sin(phase + 0.7) + float(rng.normal(0.0, eps))
        s4 = base + 0.08 + 0.048 * math.sin(phase + 1.0) + float(rng.normal(0.0, eps * 1.1))
        return {"s1": s1, "s2": s2, "s3": s3, "s4": s4}

    u = (t - t_break) / max(n - t_break - 1, 1)
    # Variance ramps up; channels follow different dynamics (relationship breakdown)
    sig = 0.025 + (u**1.65) * 1.15
    s1 = 10.2 + 0.22 * u + float(rng.normal(0.0, sig))
    s2 = 9.7 - 0.28 * u + 0.35 * math.sin(t / 2.8) + float(rng.normal(0.0, sig * 1.08))
    s3 = 10.0 + 0.55 * math.sin(t / 5.5) * (0.25 + u) + float(rng.normal(0.0, sig * 1.18))
    s4 = 10.1 - 0.18 * u * math.cos(t / 3.2) + float(rng.normal(0.0, sig * 1.25))
    return {"s1": s1, "s2": s2, "s3": s3, "s4": s4}


def main() -> None:
    here = Path(__file__).resolve().parent

    regime_payloads = [
        _payload(t, "pilot-regime-shift", "asset-rs-1", regime_shift_series(t))
        for t in range(N_STEPS)
    ]
    rng_si = np.random.default_rng(20260320)
    si_payloads = [
        _payload(t, "pilot-structural-instability", "asset-si-1", structural_instability_series(t, rng=rng_si))
        for t in range(N_STEPS)
    ]

    regime_doc = {
        "scenario": "regime_shift",
        "description": (
            "Smooth blend between two internally coherent relational regimes with a mid-run "
            "blend wobble so relational drift revisits REGIME_SHIFT_OBSERVED without ALERT-level "
            "composite scores. No missing data."
        ),
        "timesteps": N_STEPS,
        # Raw REGIME_SHIFT is often a single step; use 1 so smoothed output can reflect it
        # without requiring duplicate engine ticks (see run_pilot._load_pilot_input).
        "interpreted_smoothing": {"consecutive_required": 1},
        "payloads": regime_payloads,
    }
    si_doc = {
        "scenario": "structural_instability",
        "description": "Rising cross-sensor variance and diverging dynamics after an initial calm phase; no missing data.",
        "timesteps": N_STEPS,
        "payloads": si_payloads,
    }

    (here / "regime_shift_inputs.json").write_text(
        json.dumps(regime_doc, indent=2),
        encoding="utf-8",
    )
    (here / "structural_instability_inputs.json").write_text(
        json.dumps(si_doc, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {here / 'regime_shift_inputs.json'}")
    print(f"Wrote {here / 'structural_instability_inputs.json'}")


if __name__ == "__main__":
    main()
