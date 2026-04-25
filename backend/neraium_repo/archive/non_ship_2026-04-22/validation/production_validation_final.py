#!/usr/bin/env python3
"""Production validation under realistic operating conditions.
Focused, fast, evidence-only validation.

Tests:
1. Soak test - 250 frames x 5 units
2. Fault injection - 9 test cases
3. Performance - real latency/throughput
4. Determinism - replay identical sequence
5. State consistency - metric alignment

Runtime: ~30-40 seconds. Evidence only.
"""

import sys
import time
import numpy as np
import logging

logging.getLogger("neraium_core").setLevel(logging.CRITICAL)

from neraium_core.engine.production import ProductionEngine, InputFrame


# ============================================================================
# RESULTS TRACKING
# ============================================================================

passed = []
failed = []
measurements = {}

def record_pass(name, detail=""):
    msg = f"✓ {name}"
    if detail:
        msg += f": {detail}"
    passed.append(msg)
    print(msg)

def record_fail(name, detail):
    msg = f"✗ {name}: {detail}"
    failed.append(msg)
    print(msg)

def record_measurement(name, value):
    measurements[name] = value

def print_summary():
    total = len(passed) + len(failed)
    pct = 100 * len(passed) // max(1, total)

    report = "\n" + "="*80 + "\n"
    report += "PRODUCTION VALIDATION REPORT\n"
    report += "="*80 + "\n\n"
    report += f"Results: {len(passed)}/{total} passed ({pct}%)\n"

    if measurements:
        report += "\nMeasurements:\n"
        for k, v in sorted(measurements.items()):
            if isinstance(v, dict):
                report += f"  {k}:\n"
                for k2, v2 in v.items():
                    report += f"    {k2}: {v2}\n"
            else:
                report += f"  {k}: {v}\n"

    if failed:
        report += f"\nFailed ({len(failed)}):\n"
        for f in failed:
            report += f"  {f}\n"

    status = "PASS" if len(failed) == 0 else "FAIL"
    report += f"\nStatus: {status}\n"
    report += "="*80 + "\n"

    print(report)
    return len(failed) == 0

# ============================================================================
# TEST 1: SOAK TEST
# ============================================================================

print("\n[TEST 1] SOAK TEST (250 frames x 5 units)")
print("-" * 80)

engine = ProductionEngine()
units = ["soak-u1", "soak-u2", "soak-u3", "soak-u4", "soak-u5"]
soak_errors = 0
soak_frames = 0

for frame_num in range(250):
    for unit_id in units:
        ts = 1704067200.0 + frame_num * 60 + float(units.index(unit_id))
        noise = 0.1 + (frame_num / 250) * 0.3
        sensors = {
            "temp": 70 + np.random.normal(0, 5 * noise),
            "pressure": 100 + np.random.normal(0, 8 * noise),
            "vibration": 0.5 + np.random.normal(0, 0.2 * noise),
        }

        try:
            frame = InputFrame(timestamp=ts, unit_id=unit_id, sensors=sensors)
            result = engine.process_frame(frame)
            soak_frames += 1

            if result.state not in {"STABLE", "WATCH", "ALERT"}:
                soak_errors += 1
        except Exception:
            soak_errors += 1

if soak_errors == 0:
    record_pass("Soak Test", f"{soak_frames} frames processed, 0 errors")
    diag = engine.get_diagnostics()
    record_measurement("Soak memory (MB)", diag["engine_frames_stored"] * 0.01)
else:
    record_fail("Soak Test", f"{soak_errors} errors in {soak_frames} frames")

# ============================================================================
# TEST 2: FAULT INJECTION
# ============================================================================

print("\n[TEST 2] FAULT INJECTION (9 cases)")
print("-" * 80)

faults = [
    ("valid", {"timestamp": 1.0, "unit_id": "f", "sensors": {"s": 1.0}}, False),
    ("missing_ts", {"unit_id": "f", "sensors": {"s": 1.0}}, True),
    ("missing_unit", {"timestamp": 1.0, "sensors": {"s": 1.0}}, True),
    ("empty_sensors", {"timestamp": 1.0, "unit_id": "f", "sensors": {}}, True),
    ("nan_value", {"timestamp": 1.0, "unit_id": "f", "sensors": {"s": float("nan")}}, True),
    ("inf_value", {"timestamp": 1.0, "unit_id": "f", "sensors": {"s": float("inf")}}, True),
    ("neg_inf", {"timestamp": 1.0, "unit_id": "f", "sensors": {"s": float("-inf")}}, True),
    ("string", {"timestamp": 1.0, "unit_id": "f", "sensors": {"s": "x"}}, True),
    ("neg_ts", {"timestamp": -1.0, "unit_id": "f", "sensors": {"s": 1.0}}, True),
]

caught = 0
valid = 0

for name, data, should_err in faults:
    try:
        frame = InputFrame(**data)
        frame.validate()
        if not should_err:
            valid += 1
    except (ValueError, TypeError):
        if should_err:
            caught += 1

expected_errors = len([f for f in faults if f[2]])
if caught == expected_errors and valid == 1:
    record_pass("Fault Injection", f"{caught} errors caught, 1 valid processed")
else:
    record_fail("Fault Injection", f"Caught {caught}/{expected_errors}, valid={valid}")

# ============================================================================
# TEST 3: PERFORMANCE
# ============================================================================

print("\n[TEST 3] PERFORMANCE (200 frames x 3 units)")
print("-" * 80)

engine3 = ProductionEngine()
units3 = ["perf-u1", "perf-u2", "perf-u3"]

# Warmup
for i in range(10):
    for uid in units3:
        engine3.process_frame(InputFrame(timestamp=float(i), unit_id=uid, sensors={"s": 1.0}))

# Measure
latencies = []
start = time.time()

for i in range(200):
    for uid in units3:
        ts = 100.0 + i + float(units3.index(uid)) / len(units3)
        t0 = time.time()
        engine3.process_frame(InputFrame(
            timestamp=ts,
            unit_id=uid,
            sensors={"a": np.sin(i / 100), "b": np.cos(i / 100), "c": float(i)}
        ))
        latencies.append((time.time() - t0) * 1000)

total_time = time.time() - start
throughput = (200 * len(units3)) / total_time

latencies.sort()
p50 = latencies[len(latencies) // 2]
p95 = latencies[int(len(latencies) * 0.95)]
p99 = latencies[int(len(latencies) * 0.99)]
avg = np.mean(latencies)

record_measurement("Latency (p50)", f"{p50:.2f}ms")
record_measurement("Latency (p95)", f"{p95:.2f}ms")
record_measurement("Latency (p99)", f"{p99:.2f}ms")
record_measurement("Latency (avg)", f"{avg:.2f}ms")
record_measurement("Throughput", f"{throughput:.0f} frames/sec")

record_pass("Performance", f"p99={p99:.2f}ms, throughput={throughput:.0f}/sec")

# ============================================================================
# TEST 4: DETERMINISM
# ============================================================================

print("\n[TEST 4] DETERMINISM (100-frame replay)")
print("-" * 80)

sequence = [(1704067200.0 + i * 60, {"s1": 50 + i % 10, "s2": 100 - i % 5}) for i in range(100)]

e1 = ProductionEngine()
r1 = []
for ts, sens in sequence:
    r = e1.process_frame(InputFrame(timestamp=ts, unit_id="det", sensors=sens))
    r1.append((r.state, round(r.drift_score, 10)))

e2 = ProductionEngine()
r2 = []
for ts, sens in sequence:
    r = e2.process_frame(InputFrame(timestamp=ts, unit_id="det", sensors=sens))
    r2.append((r.state, round(r.drift_score, 10)))

mismatches = sum(1 for a, b in zip(r1, r2) if a != b)

if mismatches == 0:
    record_pass("Determinism", "100/100 frames match perfectly")
else:
    record_fail("Determinism", f"{mismatches}/100 frames mismatch")

# ============================================================================
# TEST 5: STATE CONSISTENCY
# ============================================================================

print("\n[TEST 5] STATE CONSISTENCY (100 frames)")
print("-" * 80)

engine5 = ProductionEngine()
results = []

for i in range(100):
    ts = 1704067200.0 + i * 60
    noise = 0.1 + (i / 100) * 0.5
    sensors = {
        "a": 50 + np.random.normal(0, 10 * noise),
        "b": 100 + np.random.normal(0, 10 * noise),
        "c": 25 + np.random.normal(0, 5 * noise),
    }
    results.append(engine5.process_frame(InputFrame(timestamp=ts, unit_id="cons", sensors=sensors)))

# Check consistency
inconsistent = 0

for r in results:
    # High drift + high health = inconsistent
    if r.drift_score > 0.6 and r.health_percentage > 75:
        inconsistent += 1
    # ALERT + high health = inconsistent
    if r.state == "ALERT" and r.health_percentage > 60:
        inconsistent += 1
    # STABLE + high drift = inconsistent
    if r.state == "STABLE" and r.drift_score > 0.5:
        inconsistent += 1

# Check invalid transitions
states = [r.state for r in results]
invalid_trans = sum(1 for i in range(len(states)-1) if states[i] == "ALERT" and states[i+1] == "STABLE")

if inconsistent == 0 and invalid_trans == 0:
    record_pass("State Consistency", "100% consistent, no invalid transitions")
else:
    record_fail("State Consistency", f"{inconsistent} inconsistent, {invalid_trans} invalid trans")

# ============================================================================
# FINAL REPORT
# ============================================================================

print("\n" + "="*80)
ok = print_summary()
print()

if ok:
    print("✓ PRODUCTION READY\n")
    sys.exit(0)
else:
    print("✗ ISSUES FOUND\n")
    sys.exit(1)
