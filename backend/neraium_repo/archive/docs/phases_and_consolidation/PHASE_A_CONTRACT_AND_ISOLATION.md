# Phase A: Canonical Frame Contract & Markets Isolation Blueprint

**Status**: Contract proposal for Phase A hardening  
**Date**: 2026-04-13  
**Objective**: Stabilize core engine contract before unifying surface (Phase B)

---

## PART 1: CANONICAL INTERNAL FRAME CONTRACT

### Executive Summary

The Neraium core engine processes data through a normalized **internal frame** format. This document defines the single, binding contract that all code must respect:

1. **All ingress aliasing happens at adapters only** (not in StructuralEngine)
2. **One internal frame format after ingestion** (no variants downstream)
3. **One field naming standard** (no unit_id/asset_id ambiguity)
4. **One optional/required contract** (clear cardinality everywhere)

---

### Part 1A: The Canonical Internal Frame Model

After ingestion, all data flowing through StructuralEngine must conform to this shape:

```python
CanonicalInternalFrame = {
    # === IDENTITY (Required - all four fields must be present)
    "timestamp": str,                    # ISO-8601 format, non-empty
    "asset_id": str,                     # Primary equipment identifier, non-empty
    "site_id": str,                      # Operational location, non-empty (no None)
    "customer_id": str | None,           # Optional: billing/tenant context
    
    # === SIGNALS (Required - must be present, dict may be empty for some scenarios)
    "sensor_values": dict[str, float | None],  # Sensor readings, keys are canonical names
    
    # === METADATA (Optional - created at build_frame, consumed only by validation)
    "sensor_quality": dict[str, str],    # Quality flags per sensor (default: empty dict)
    "sensor_order": list[str],           # Order of sensors for incremental alignment (default: [])
    
    # === STATE (Optional - attached at build_frame, not modified by engine)
    "state": str,                        # Last computed state (STABLE|WATCH|ALERT) (default: "STABLE")
    "anomaly": bool,                     # Anomaly detected (default: False)
    "aligned": list,                     # Alignment tracking data (default: [])
    
    # === ENGINE INTERNAL (Not part of contract; added at runtime by StructuralEngine)
    "_vector": np.ndarray,               # Feature vector (created internally)
}
```

**Contract Enforcement**:
1. All four identity fields must be present and non-empty after ingestion
2. `sensor_values` must be present (may be empty dict in some edge cases, but key must exist)
3. `site_id` must never be `None` (default to "default-site" at ingestion if missing)
4. Timestamp must be ISO-8601 string after ingestion (no mixed int/str)
5. No other fields allowed at StructuralEngine entry point

---

### Part 1B: Field Definitions and Semantics

#### Identity Fields (REQUIRED)

| Field | Type | Semantics | Default Strategy |
|-------|------|-----------|------------------|
| `timestamp` | `str` (ISO-8601) | When the measurement occurred, UTC | Required at ingress; parse + normalize |
| `asset_id` | `str` | Unique identifier for the equipment being monitored | Required at ingress; no aliases downstream |
| `site_id` | `str` | Operational location/facility where asset resides | Required at ingress; default to "default-site" if missing |
| `customer_id` | `str` or `None` | Billing/tenant context (optional) | Optional; may be None |

**Rules**:
- `asset_id` is the canonical equipment identifier
  - External aliases (unit_id, machine_id, device_id, equipment) are mapped to `asset_id` **at ingress only**
  - StructuralEngine never sees the aliases
  - ProductionEngine API accepts `unit_id`, but maps it to `asset_id` before passing to engine
  
- `site_id` injection is a valid ingestion-time strategy, not a runtime wrapper
  - ProductionEngine **may** inject "production" if no site is provided
  - But the result must be fully-formed frames with site_id set, not wrapped frames
  
- `customer_id` is optional and carries through for audit/tenant tracking

---

#### Signal Fields (REQUIRED)

| Field | Type | Semantics | Constraints |
|-------|------|-----------|-------------|
| `sensor_values` | `dict[str, float \| None]` | Raw or pre-processed sensor readings | Keys are canonical sensor names (see below) |

**Sensor Naming**:
- Canonical names are lowercase, underscores, no spaces: `temp_bearing_a`, `vibration_rms`, `pressure_main`
- All aliases (Temperature, Temp, TEMPERATURE, temp:bearing:a) normalized to canonical form **at ingestion**
- StructuralEngine receives only canonical names
- No downstream code performs sensor name mapping

**Handling `None` values**: Allowed in sensor_values for sparse/missing data. Engine handles gracefully.

---

#### Metadata Fields (OPTIONAL)

| Field | Type | Owner | Semantics |
|-------|------|-------|-----------|
| `sensor_quality` | `dict[str, str]` | Built at `build_frame()` | Quality assessment per sensor (unused by engine, reserved for validation) |
| `sensor_order` | `list[str]` | Built at `build_frame()` | Canonical order of sensors for incremental alignment tracking |

**Note**: These fields are created by `build_frame()` but **never consumed by StructuralEngine**. They exist for validation/logging only. Should be removed if unused in Phase B.

---

#### State/Output Fields (OPTIONAL)

| Field | Type | Semantics | Set By |
|-------|------|-----------|--------|
| `state` | `str` (STABLE\|WATCH\|ALERT) | Last computed engine state | StructuralEngine |
| `anomaly` | `bool` | Anomaly detected in latest window | StructuralEngine |
| `aligned` | `list` | Alignment history (unused) | `build_frame()` |

---

### Part 1C: Drift Score Consolidation

**Current State**: Five overlapping drift field names  
**Target State**: One canonical drift output with clear semantics

#### Output Contract (what StructuralEngine emits):

```python
{
    "structural_drift_score": float,            # Raw drift [0, 1], no smoothing
    "structural_drift_score_smoothed": float,   # EMA-smoothed drift [0, 1]
    # Deprecated aliases (to be removed in Phase B):
    # "drift_smooth": <same as structural_drift_score_smoothed>
    # "latest_drift": <should not exist; use structural_drift_score>
    # "latest_drift_smoothed": <should not exist; use structural_drift_score_smoothed>
    
    "relational_stability_score": float,        # Stability [0, 1] (NOT instability)
    "system_health": int,                       # Health [0, 100]
    # Note: Shadow mode tests expect "relational_instability_score" (opposite polarity)
    #       This will be fixed as part of contract enforcement
}
```

#### Semantic Rules:

1. **structural_drift_score**: Unnormalized, computed fresh from current window
2. **structural_drift_score_smoothed**: EMA-filtered version of above
3. **relational_stability_score**: Measure of stability (higher is better) NOT instability
4. Remove aliases: `drift_smooth`, `latest_drift`, `latest_drift_smoothed`

---

### Part 1D: Ingestion Adapter Responsibility

All adapters (ProductionEngine, loaders, raw telemetry adapter, etc.) must:

1. **Accept any external field naming** (unit_id, machine, equipment, etc.)
2. **Map to canonical form** before passing to StructuralEngine:
   - Any equipment ID → `asset_id`
   - Any timestamp variant → ISO-8601 `timestamp`
   - Any sensor names → canonical `sensor_values` dict
   - Any site reference → `site_id` (or default)
3. **Validate that all four identity fields are present** after normalization
4. **Never pass partial frames** to StructuralEngine
5. **Document the mapping** (comments, not implicit)

Example normalization (from integration.py):

```python
# GOOD: Explicit mapping with aliases resolved
canonical_frame = {
    "timestamp": parse_timestamp(row["time"]),  # time, event_time, ts → ISO-8601
    "asset_id": row.get("asset") or row.get("machine_id") or row.get("unit"),  # explicit fallback
    "site_id": row.get("site", "default-site"),  # explicit default
    "customer_id": row.get("account"),
    "sensor_values": {
        "temp": float(row["temperature"]),      # temperature → temp (canonical)
        "vibration": float(row["vib_rms"]),     # vib_rms → vibration (canonical)
    },
}
```

---

### Part 1E: StructuralEngine Contract (What it assumes)

StructuralEngine assumes every frame it receives:

1. **Has all four identity fields present and valid**
   ```python
   assert frame["timestamp"]  # non-empty string
   assert frame["asset_id"]   # non-empty string
   assert frame["site_id"]    # non-empty string (may be "default-site")
   ```

2. **Has sensor_values as a dict**
   ```python
   assert isinstance(frame["sensor_values"], dict)
   # May be empty, but key must exist
   ```

3. **All sensor keys are canonical names** (lowercase, underscores)
   ```python
   # Downstream code does NOT do name mapping:
   for sensor_name, value in frame["sensor_values"].items():
       # sensor_name is already canonical (temp, vibration, etc.)
       # No "Temperature" → "temp" conversion happens here
   ```

4. **Timestamp is ISO-8601 string**
   ```python
   ts = datetime.fromisoformat(frame["timestamp"])  # Must work
   ```

5. **No adapter-specific aliases present**
   ```python
   # These should NEVER appear in frames passed to engine:
   assert "unit_id" not in frame  # (only adapter API uses this)
   assert "machine_id" not in frame
   assert "Temperature" not in frame.get("sensor_values", {})
   ```

---

### Part 1F: ProductionEngine Wrapper Contract

ProductionEngine (`production.py`) is a **valid adapter** that wraps StructuralEngine. It:

1. **Accepts user-facing InputFrame with `unit_id`**
   ```python
   class InputFrame:
       timestamp: float
       unit_id: str
       sensors: dict[str, float]
   ```

2. **Normalizes to internal frame**
   ```python
   internal_frame = {
       "timestamp": str(timestamp),  # Convert float to ISO-8601
       "asset_id": frame.unit_id,    # Explicit mapping: unit_id → asset_id
       "site_id": "production",       # Inject site_id
       "sensor_values": frame.sensors,
   }
   ```

3. **Passes internal frame to StructuralEngine** (now both have the same contract)

4. **Output contract is the same as StructuralEngine output**
   ```python
   return EngineResult(
       state=engine_output["state"],
       drift_score=engine_output["structural_drift_score"],
       ...
   )
   ```

---

## PART 2: MARKETS CODE ISOLATION & REMOVAL

### Executive Summary

Markets module is **completely isolated** with zero infrastructure dependencies. Safe for removal in single operation.

- ~2,904 lines of code across markets module, sports adapter, and 10 test files
- ZERO external imports from non-markets code
- ZERO production impact
- One broken API module that will cause test failures

**Recommendation**: Delete markets module entirely in this phase.

---

### Part 2A: What to Delete

#### Entire Directories

```
/home/user/neraium-core/neraium_core/markets/              (~1,976 lines)
/home/user/neraium-core/tests/markets/                     (~836 lines)
```

#### Individual Files

```
/home/user/neraium-core/neraium_core/sports_betting_adapter.py  (~21 lines)
/home/user/neraium-core/tests/test_market_betting_adapters.py   (~71 lines)
```

#### Supporting Data

```
/home/user/neraium-core/data/sample_market_data.csv       (if markets-specific)
```

**Total Impact**: ~2,904 lines deleted, zero production breakage

---

### Part 2B: What to Keep (Conditional)

**IF you want to preserve ingress contract tests:**

Keep:
- `/home/user/neraium-core/neraium_core/stock_market_adapter.py`
- `/home/user/neraium-core/neraium_core/live_runner.py` (root helper)
- `/home/user/neraium-core/tests/test_engine_ingress_contract.py`
- `/home/user/neraium-core/live_runner.py` (root-level mock demo)

But **exclude from CI** (mark with `@pytest.mark.skip` or move to separate test suite).

---

### Part 2C: Critical Issues Found

#### 1. Broken API Module (MUST FIX BEFORE DELETING)

File: `/home/user/neraium-core/neraium_core/markets/app/api.py`

**Issue**: This file is a patching script, not an actual Flask/FastAPI app. It:
- Does NOT define `create_app()` function
- References external code: `apps/api/routers/ingest.py` (doesn't exist in repo)
- Is imported by tests that expect a working app factory

**Impact**: If you try to run markets tests before deleting, you'll get ImportError.

**Action**: Just delete the whole markets directory (it's all bad).

---

### Part 2D: Deletion Checklist

Before deleting, verify:

- [ ] No production code imports from `neraium_core.markets`
- [ ] No CI configuration references markets tests
- [ ] No documentation references markets API as official interface
- [ ] stock_market_adapter tests are archived separately if keeping them

---

## PART 3: ENFORCEMENT RULES FOR PHASE A

### Schema Consistency Checks

By end of Phase A, the codebase must satisfy:

1. **No unit_id in frames after ingestion**
   - ProductionEngine → internal frame conversion is the **only** place unit_id appears
   - StructuralEngine never sees unit_id
   - Tests that construct frames use `asset_id`, not `unit_id`

2. **All timestamps are ISO-8601 strings**
   - No mixed int/str in frame["timestamp"]
   - ProductionEngine converts float timestamp to string before passing to engine

3. **All sensor names are canonical**
   - "Temperature" → "temp"
   - "vib_rms" → "vibration"
   - Mapping happens **once**, at ingestion adapter
   - StructuralEngine does not do name mapping

4. **site_id is never None**
   - Adapters provide default ("default-site") if missing
   - ProductionEngine injects "production" as valid default
   - No frames have None site_id downstream

5. **Five drift aliases are documented**
   - Comment in `_default_result_payload()` explains relationship
   - OR deprecated aliases removed entirely

6. **Loaders output fully-formed frames**
   - FD004/IMS loaders produce dicts with all four identity fields
   - Not partial records that require post-processing

---

## PART 4: IMPLEMENTATION SEQUENCE

### Step 1: Delete Markets Code
- Remove `/neraium_core/markets/`
- Remove `/tests/markets/`
- Remove sports adapter and related tests
- Update CI config to remove market test references

### Step 2: Enforce Frame Contract in StructuralEngine
- Add explicit assertions at engine entry point (alignment.py:1700+)
- Verify all four identity fields present
- Verify sensor_values is dict
- Verify timestamp is ISO-8601 string

### Step 3: Fix ProductionEngine Mapping
- Add comment documenting unit_id → asset_id transformation
- Ensure timestamp is converted to ISO-8601 string
- Verify site_id is injected consistently

### Step 4: Fix Shadow Mode Polarity Mismatch
- Either:
  - Change engine to output `relational_instability_score` (opposite of stability), OR
  - Update shadow mode schema to expect `relational_stability_score`
- Add comment explaining the choice

### Step 5: Clean Up Drift Fields
- Remove aliases: `drift_smooth`, `latest_drift`, `latest_drift_smoothed`
- Keep `structural_drift_score` and `structural_drift_score_smoothed`
- Add docstring explaining why both exist

### Step 6: Consolidate Loaders
- Update FD004/IMS/generic loaders to output fully-formed frames
- Include all four identity fields
- Remove post-processing in consuming code

---

## PART 5: SUCCESS CRITERIA FOR PHASE A

✓ Frame contract is explicit and enforced at StructuralEngine entry point
✓ ProductionEngine explicitly documents unit_id → asset_id mapping
✓ No frames have None site_id
✓ All timestamps are ISO-8601 strings (no mixed int/str)
✓ Loaders output frames with all identity fields
✓ Drift field aliases removed or documented
✓ Shadow mode polarity mismatch is resolved
✓ Markets code is removed
✓ All validation tests pass without schema drift failures

---

## Next: Phase B - Unify Product Surface

Once Phase A is complete and the contract is stable, Phase B will:

1. Create one canonical entrypoint (`Engine.ingest(frame)`)
2. Define unified runtime path (replay → live ingestion → evidence)
3. Create one official validation command
4. Rewrite production docs with only measured claims

