# Decision Layer: Real Example Outputs

Three concrete scenarios with raw SII output → decision object.

## Scenario 1: STABLE (Normal Operation)

### Raw SII Output
```python
{
    "timestamp": 1704067200.0,
    "asset_id": "pump_standard_001",
    "state": "STABLE",
    "structural_drift_score": 0.12,
    "relational_instability_score": 0.05,
    "system_phase": "stable",
    "policy_alert": False,
    "policy_watch": False,
    "shock_activity": 0.0,
    "subsystem_instability": 0.02,
    "sensor_relationships": ["temp", "pressure", "vibration"],
    "regime_name": "nominal",
    "regime_distance": 0.1,
    "attribution": {
        "top_drivers": [],
        "driver_scores": {}
    },
    "drift_history": [0.10, 0.11, 0.12],
    "data_quality": {
        "missing_sensor_count": 0,
        "valid_signal_count": 3
    }
}
```

### Decision Object (Output)
```python
{
    "finding_confidence": 0.35,      # Low; drift is minimal
    "action_confidence": 0.10,       # Very low; no action needed
    "transient_score": 0.05,         # Not transient; just normal operation
    "suppress": True,                # Hide from operators (routine)
    "severity": "LOW",               # Normal
    "summary": "ℹ️ System stable",
    "findings": [],                  # No findings
    "causal_chain": None,            # No causality to explain
    "pattern_match": None,           # No historical pattern match
    "recommended_action": None,      # No action
    "recommended_target": None,
    "reasons": [
        "No strong signals; baseline behavior"
    ]
}
```

---

## Scenario 2: TRANSIENT (Spike That Self-Resolves)

### Raw SII Output
```python
{
    "timestamp": 1704067330.0,       # ~2 minutes later
    "asset_id": "pump_standard_001",
    "state": "WATCH",
    "structural_drift_score": 0.52,  # Jump from 0.12 → 0.52
    "relational_instability_score": 0.35,
    "system_phase": "transitional",
    "policy_alert": False,
    "policy_watch": True,
    "shock_activity": 0.8,           # High shock activity
    "subsystem_instability": 0.28,
    "sensor_relationships": ["temp", "pressure", "vibration"],
    "regime_name": "nominal",        # Still nominal regime
    "regime_distance": 0.15,
    "attribution": {
        "top_drivers": ["vibration"],
        "driver_scores": {"vibration": 0.72}
    },
    "drift_history": [0.10, 0.11, 0.12, 0.45, 0.52],
    "drift_trend": 0.105,            # Positive trend
    "data_quality": {
        "missing_sensor_count": 0,
        "valid_signal_count": 3
    }
}
```

### Decision Object (Output)
```python
{
    "finding_confidence": 0.68,      # Medium; something changed but unclear
    "action_confidence": 0.25,       # Very low; don't recommend action
    "transient_score": 0.78,         # High; likely self-resolving
    "suppress": True,                # SUPPRESS (transient + low action conf)
    "severity": "MODERATE",          # Elevated but not critical
    "summary": "[SUPPRESSED] Structural alignment degraded (score 0.52) (transient/low confidence)",
    "findings": [
        {
            "category": "structural_drift",
            "description": "Structural alignment degraded (score 0.52)",
            "confidence": 0.71,
            "magnitude": 0.21,
            "reversible": True,       # Can recover
            "affected_signals": ["vibration"]
        }
    ],
    "causal_chain": {
        "steps": [
            {
                "trigger": "External shock detected",
                "effect": "Signal relationships disrupted",
                "strength": 0.64,
                "involved_signals": ["vibration"]
            }
        ],
        "root_cause": "external_shock",
        "confidence": 0.75
    },
    "pattern_match": None,           # No prior pattern of this
    "recommended_action": None,      # Not recommended due to transience
    "recommended_target": None,
    "reasons": [
        "Likely transient event (may self-resolve)",
        "Finding is low-confidence",
        "Suppressed from operator view (low priority)"
    ]
}
```

**Outcome (next frame):** Drift drops back to 0.15 → system returns to STABLE → operator never sees the alert.

---

## Scenario 3: REAL DEGRADATION (Sustained, Actionable)

### Raw SII Output (Frame 1 of degradation)
```python
{
    "timestamp": 1704068400.0,       # ~20 minutes later
    "asset_id": "pump_A0_001",       # Note: A0 equipment
    "state": "WATCH",
    "structural_drift_score": 0.58,
    "relational_instability_score": 0.48,
    "system_phase": "degrading",     # ← Key signal
    "policy_alert": False,
    "policy_watch": True,
    "shock_activity": 0.15,          # Low shock (not transient)
    "subsystem_instability": 0.42,
    "sensor_relationships": ["temp", "pressure", "vibration"],
    "regime_name": "nominal",
    "regime_distance": 0.22,
    "attribution": {
        "top_drivers": ["pressure", "vibration"],
        "driver_scores": {
            "pressure": 0.85,
            "vibration": 0.78
        }
    },
    "drift_history": [0.12, 0.15, 0.18, 0.28, 0.40, 0.50, 0.58],
    "drift_trend": 0.076,            # Consistent upward trend
    "data_quality": {
        "missing_sensor_count": 0,
        "valid_signal_count": 3
    }
}
```

### Decision Object (Output)
```python
{
    "finding_confidence": 0.82,      # High confidence
    "action_confidence": 0.68,       # Medium-high; we know what to do
    "transient_score": 0.18,         # Low; NOT transient
    "suppress": False,               # SURFACE (high confidence + sustained)
    "severity": "HIGH",              # (Note: not CRITICAL yet)
    "summary": "⚡ HIGH: Structural misalignment — Action needed soon",
    "findings": [
        {
            "category": "structural_drift",
            "description": "Structural alignment degraded (score 0.58)",
            "confidence": 0.89,
            "magnitude": 0.29,
            "reversible": True,
            "affected_signals": ["pressure", "vibration"]
        },
        {
            "category": "coordination_failure",
            "description": "Signal relationships became unstable (instability 0.48)",
            "confidence": 0.81,
            "magnitude": 0.24,
            "reversible": False,     # Harder to reverse
            "affected_signals": ["pressure", "vibration", "temperature"]
        },
        {
            "category": "trend_deterioration",
            "description": "System deteriorating: drift increased 0.08 this frame",
            "confidence": 0.72,
            "magnitude": 0.16,
            "reversible": False,
            "affected_signals": ["pressure", "vibration"]
        }
    ],
    "causal_chain": {
        "steps": [
            {
                "trigger": "Baseline-to-recent structural misalignment",
                "effect": "Correlation matrices diverged",
                "strength": 0.58,
                "involved_signals": ["pressure", "vibration"]
            },
            {
                "trigger": "Correlation breakdown",
                "effect": "Relational instability metrics elevated",
                "strength": 0.34,
                "involved_signals": ["pressure", "vibration", "temperature"]
            },
            {
                "trigger": "Sustained structural misalignment",
                "effect": "System phase transitioned to degrading",
                "strength": 0.80,
                "involved_signals": ["pressure", "vibration"]
            }
        ],
        "root_cause": "structural_misalignment",
        "confidence": 0.70
    },
    "pattern_match": {
        "pattern_id": "asset_pump_A0_001:historical_run_42",
        "similarity": 0.79,
        "prior_outcome": "escalated_to_failure",
        "time_to_outcome_hours": 12.0,
        "confidence": 0.79
    },
    "recommended_action": "schedule_inspection",
    "recommended_target": "pressure",
    "reasons": [
        "Finding is high-confidence",
        "Causal chain is well-supported",
        "Unlikely to be transient",
        "Pattern match suggests escalation risk (12h window)"
    ]
}
```

**Interpretation:**
- ✅ **SURFACE:** High finding confidence + not transient
- ✅ **RECOMMEND:** Schedule inspection on pressure subsystem
- ⚠️ **PATTERN WARNING:** Similar to prior failure pattern; 12-hour window

---

## Comparison Table

| Metric | Stable | Transient Spike | Real Degradation |
|--------|--------|-----------------|------------------|
| Drift Score | 0.12 | 0.52 | 0.58 |
| Phase | stable | transitional | **degrading** ← Key |
| Shock Activity | 0.0 | **0.8** ← High | 0.15 |
| Drift Trend | +0.00 | +0.105 | **+0.076** ← Sustained |
| Finding Confidence | 0.35 | 0.68 | **0.82** |
| Transient Score | 0.05 | **0.78** | 0.18 |
| Suppress? | ✅ Yes | ✅ Yes | ❌ No |
| Recommend Action? | No | No | ✅ Yes |
| Pattern Match? | None | None | ✅ Yes, warns escalation |

---

## Key Distinctions

### Why Transient Spike Was Suppressed
1. **High shock_activity (0.8)** → External disturbance, not equipment failure
2. **Drift trend is positive** but shock is the driver
3. **Regime didn't shift** (still nominal)
4. **Transient score > 0.75** + severity only MODERATE → Suppressed
5. **Result:** Operator never sees the alert

### Why Real Degradation Was Surfaced
1. **Phase = degrading** (not transitional) → Sustained change
2. **Drift trend consistent (0.076)** → Not a spike, gradual decline
3. **Shock activity low (0.15)** → Not external; internal degradation
4. **Multiple correlated signals** (pressure, vibration) → Systemic, not noise
5. **Finding confidence = 0.82** → High confidence in the change
6. **Pattern match warns** → Similar to prior failure case
7. **Result:** Operator sees alert + recommendation + historical context

---

## Severity Mapping

Current decision layer uses:
- `LOW` → No action (suppress)
- `MODERATE` → Monitor, suppress if transient
- `HIGH` → Recommend action, don't suppress
- `CRITICAL` → Force surface, escalate ← **NAMING ISSUE: Should be ELEVATED per existing system**

---

## Edge Cases

### Case A: High Drift But Sustained Transient (False Positive Prevention)
```
Drift = 0.65 (high)
Phase = transitional (not degrading)
Shock = 0.85 (very high)
Trend = +0.02 (rising but from transient)
→ Severity = HIGH (drift-driven)
→ Transient Score = 0.80 (shock-driven)
→ Suppress = TRUE (high transience overrides severity for non-CRITICAL)
```

### Case B: Low Drift But Degrading Phase (Early Warning)
```
Drift = 0.35 (medium)
Phase = degrading (key signal)
Shock = 0.05 (clean)
Relational = 0.45 (elevated)
→ Severity = MODERATE
→ Finding Confidence = 0.72
→ Transient Score = 0.15
→ Suppress = FALSE (degrading phase + low transience)
→ Recommendation = "monitor_closely" (not urgent, but watch)
```

---

## Caveats & Limitations

1. **Causal chains are not true causality** — They follow rules, not inference. "Drift caused instability" is pattern-matching, not causal.

2. **Pattern matching requires teaching** — You must manually record outcomes. No self-learning.

3. **All thresholds are deterministic** — Severity, transience, suppression: all hardcoded. Tuning requires code changes.

4. **No future prediction** — Decisions are made frame-by-frame. No multi-frame lookahead.

5. **No uncertainty quantification** — Confidence scores are heuristic, not Bayesian credible intervals.

6. **Recommendations are advisory only** — No control authority. Operators must act.
