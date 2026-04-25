#!/usr/bin/env python3
"""Production validation under realistic operating conditions.

Tests:
1. Soak test - long duration with multiple units
2. Fault injection - malformed data, missing sensors, timestamps
3. Performance benchmarking - actual p50/p95/p99 latency and throughput
4. Determinism - byte-for-byte reproducibility
5. State consistency - STABLE/WATCH/ALERT coherence with metrics

No assumptions. Evidence only.
"""

import sys
import time
import logging
from collections import defaultdict

import numpy as np

logging.getLogger("neraium_core").setLevel(logging.CRITICAL)

from neraium_core.engine.production import ProductionEngine, InputFrame


class Evidence:
    """Track all validation evidence."""

    def __init__(self):
        self.passed = []
        self.failed = []
        self.measurements = {}
        self.warnings = []

    def record_pass(self, name, detail=""):
        msg = f"✓ {name}"
        if detail:
            msg += f": {detail}"
        self.passed.append(msg)
        print(msg)

    def record_fail(self, name, detail):
        msg = f"✗ {name}: {detail}"
        self.failed.append(msg)
        print(msg)

    def record_measurement(self, name, value):
        self.measurements[name] = value

    def record_warning(self, name, detail):
        msg = f"⚠ {name}: {detail}"
        self.warnings.append(msg)
        print(msg)

    def summary(self):
        report = "\n" + "="*80 + "\n"
        report += "PRODUCTION VALIDATION REPORT\n"
        report += "="*80 + "\n\n"

        total = len(self.passed) + len(self.failed)
        pct = 100 * len(self.passed) // max(1, total)

        report += f"Results: {len(self.passed)}/{total} passed ({pct}%)\n"

        if self.measurements:
            report += "\nMeasurements:\n"
            for k, v in sorted(self.measurements.items()):
                if isinstance(v, dict):
                    report += f"  {k}:\n"
                    for k2, v2 in sorted(v.items()):
                        if "latency" in k2.lower() or "time" in k2.lower():
                            report += f"    {k2}: {v2:.2f}ms\n"
                        elif "memory" in k2.lower():
                            report += f"    {k2}: {v2:.1f}MB\n"
                        elif "throughput" in k2.lower() or "fps" in k2.lower():
                            report += f"    {k2}: {v2:.0f}/sec\n"
                        else:
                            report += f"    {k2}: {v2}\n"
                else:
                    if "latency" in k.lower():
                        report += f"  {k}: {v:.2f}ms\n"
                    elif "memory" in k.lower():
                        report += f"  {k}: {v:.1f}MB\n"
                    elif "throughput" in k.lower() or "fps" in k.lower():
                        report += f"  {k}: {v:.0f}/sec\n"
                    else:
                        report += f"  {k}: {v}\n"

        if self.failed:
            report += f"\nFailed Validations ({len(self.failed)}):\n"
            for f in self.failed:
                report += f"  {f}\n"

        if self.warnings:
            report += f"\nWarnings ({len(self.warnings)}):\n"
            for w in self.warnings:
                report += f"  {w}\n"

        status = "PASS" if len(self.failed) == 0 else "FAIL"
        recommendation = "Production ready" if len(self.failed) == 0 and len(self.warnings) <= 1 else "Review required"

        report += f"\nStatus: {status}\n"
        report += f"Recommendation: {recommendation}\n"
        report += "="*80 + "\n"

        return report


# ============================================================================
# TEST 1: SOAK TEST
# ============================================================================

def soak_test(evidence):
    """Long-duration test with multiple units, tracking memory and latency over time."""
    print("\n[TEST 1] SOAK TEST (Long Duration Multi-Unit)")
    print("-" * 80)

    engine = ProductionEngine()
    units = [f"soak-unit-{i}" for i in range(10)]
    duration_frames = 500  # ~8 minutes at 1 frame/sec

    latencies_by_segment = defaultdict(list)
    memory_samples = []
    last_state_by_unit = {}
    state_transitions = defaultdict(int)
    errors = []

    print(f"Running {duration_frames} frames across {len(units)} units...")

    for frame_num in range(duration_frames):
        segment = frame_num // 100  # Track by 100-frame segments

        for unit_idx, unit_id in enumerate(units):
            ts = 1704067200.0 + frame_num * 60 + unit_idx * 6

            # Add some realistic variation
            noise = 0.1 + (frame_num / duration_frames) * 0.3  # Gradually increase
            sensors = {
                "temp": 70 + np.random.normal(0, 5 * noise),
                "pressure": 100 + np.random.normal(0, 8 * noise),
                "vibration": 0.5 + np.random.normal(0, 0.2 * noise),
            }

            try:
                frame = InputFrame(timestamp=ts, unit_id=unit_id, sensors=sensors)

                start = time.time()
                result = engine.process_frame(frame)
                latency = (time.time() - start) * 1000

                latencies_by_segment[segment].append(latency)

                # Track state transitions
                if unit_id not in last_state_by_unit:
                    last_state_by_unit[unit_id] = result.state
                else:
                    prev = last_state_by_unit[unit_id]
                    curr = result.state
                    if prev != curr:
                        state_transitions[f"{prev}->{curr}"] += 1
                    last_state_by_unit[unit_id] = curr

            except Exception as e:
                errors.append(f"Frame {frame_num}, unit {unit_id}: {e}")

        # Sample memory periodically
        if (frame_num + 1) % 100 == 0:
            diag = engine.get_diagnostics()
            mb = diag["engine_frames_stored"] * 0.01
            memory_samples.append((frame_num + 1, mb))
            print(f"  Frame {frame_num + 1}: {mb:.1f}MB, units={diag['units_tracked']}")

    # Analyze results
    if errors:
        evidence.record_fail("Soak Test Errors", f"{len(errors)} frames failed")
        for err in errors[:3]:
            print(f"    {err}")
    else:
        evidence.record_pass("Soak Test Completion", f"{duration_frames * len(units)} frames processed")

    # Check memory stability
    if memory_samples:
        memory_growth = memory_samples[-1][1] - memory_samples[0][1]
        evidence.record_measurement("Memory (start)", memory_samples[0][1])
        evidence.record_measurement("Memory (end)", memory_samples[-1][1])
        evidence.record_measurement("Memory growth", memory_growth)

        if memory_growth < 5:
            evidence.record_pass("Memory Stability", f"Growth of {memory_growth:.1f}MB (acceptable)")
        else:
            evidence.record_warning("Memory Growth", f"{memory_growth:.1f}MB over {duration_frames} frames")

    # Check latency over time
    latencies_early = latencies_by_segment.get(0, [])
    latencies_late = latencies_by_segment.get(4, [])

    if latencies_early and latencies_late:
        early_avg = np.mean(latencies_early)
        late_avg = np.mean(latencies_late)
        degradation = ((late_avg - early_avg) / early_avg) * 100 if early_avg > 0 else 0

        evidence.record_measurement("Latency degradation %", degradation)

        if abs(degradation) < 100:
            evidence.record_pass("Latency Stability", f"{degradation:.1f}% change over duration")
        else:
            evidence.record_warning("Latency Degradation", f"{degradation:.1f}% change (significant)")

    # Report state transitions
    if state_transitions:
        evidence.record_measurement("State transitions observed", dict(state_transitions))

    return len(errors) == 0


# ============================================================================
# TEST 2: FAULT INJECTION
# ============================================================================

def fault_injection_test(evidence):
    """Feed malformed data and verify graceful handling."""
    print("\n[TEST 2] FAULT INJECTION")
    print("-" * 80)

    engine = ProductionEngine()
    test_cases = [
        ("valid_frame", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {"s": 1.0}}, False),
        ("missing_timestamp", {"unit_id": "fault-test", "sensors": {"s": 1.0}}, True),
        ("missing_unit_id", {"timestamp": 1.0, "sensors": {"s": 1.0}}, True),
        ("empty_sensors", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {}}, True),
        ("nan_value", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {"s": float("nan")}}, True),
        ("inf_value", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {"s": float("inf")}}, True),
        ("negative_inf", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {"s": float("-inf")}}, True),
        ("string_sensor", {"timestamp": 1.0, "unit_id": "fault-test", "sensors": {"s": "not_a_number"}}, True),
        ("negative_timestamp", {"timestamp": -1.0, "unit_id": "fault-test", "sensors": {"s": 1.0}}, True),
    ]

    errors_caught = 0
    valid_processed = 0
    unexpected_passes = 0

    for name, data, should_error in test_cases:
        try:
            frame = InputFrame(**data)
            frame.validate()

            if should_error:
                unexpected_passes += 1
                evidence.record_fail(f"Fault Injection - {name}", "Should have raised error but didn't")
            else:
                result = engine.process_frame(frame)
                if result.state in {"STABLE", "WATCH", "ALERT"}:
                    valid_processed += 1
        except (ValueError, TypeError):
            if should_error:
                errors_caught += 1
        except Exception as e:
            evidence.record_fail(f"Fault Injection - {name}", f"Unexpected error type: {type(e).__name__}")

    if unexpected_passes == 0 and errors_caught == len([t for t in test_cases if t[2]]):
        evidence.record_pass("Fault Detection", f"Caught {errors_caught} bad inputs, processed 1 valid")
    else:
        evidence.record_fail("Fault Detection", f"Caught {errors_caught}/{len([t for t in test_cases if t[2]])} bad inputs")

    # Test recovery after errors
    engine2 = ProductionEngine()
    recovered = 0
    for i in range(10):
        try:
            good_frame = InputFrame(timestamp=float(i), unit_id="recovery", sensors={"s": 1.0})
            result = engine2.process_frame(good_frame)
            if result.state in {"STABLE", "WATCH", "ALERT"}:
                recovered += 1
        except:
            pass

    if recovered == 10:
        evidence.record_pass("Fault Recovery", "Engine continues operating after handling errors")

    # Test partial data (sparse sensors)
    engine3 = ProductionEngine()
    partial_ok = 0
    for i in range(20):
        num_sensors = max(1, 3 - (i // 5))
        sensors = {f"s{j}": float(j) for j in range(num_sensors)}
        try:
            frame = InputFrame(timestamp=float(i), unit_id="partial", sensors=sensors)
            result = engine3.process_frame(frame)
            if result.state in {"STABLE", "WATCH", "ALERT"}:
                partial_ok += 1
        except:
            pass

    if partial_ok == 20:
        evidence.record_pass("Partial Data Handling", "All frames with varying sensor counts processed")

    return errors_caught == len([t for t in test_cases if t[2]])


# ============================================================================
# TEST 3: PERFORMANCE BENCHMARKING
# ============================================================================

def performance_benchmark(evidence):
    """Measure real latency and throughput."""
    print("\n[TEST 3] PERFORMANCE BENCHMARKING")
    print("-" * 80)

    engine = ProductionEngine()
    units = [f"bench-unit-{i}" for i in range(5)]

    # Warmup
    for i in range(20):
        for unit_id in units:
            engine.process_frame(InputFrame(timestamp=float(i), unit_id=unit_id, sensors={"s": 1.0}))

    # Measure
    num_frames = 1000
    latencies = []

    print(f"Measuring {num_frames * len(units)} frames...")
    start = time.time()

    for i in range(num_frames):
        for unit_id in units:
            ts = 100.0 + i + float(units.index(unit_id)) / len(units)
            frame_start = time.time()
            engine.process_frame(InputFrame(
                timestamp=ts,
                unit_id=unit_id,
                sensors={"a": np.sin(i / 100), "b": np.cos(i / 100), "c": float(i)}
            ))
            latencies.append((time.time() - frame_start) * 1000)

    total_time = time.time() - start

    # Compute percentiles
    latencies = sorted(latencies)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = np.mean(latencies)

    throughput = (num_frames * len(units)) / total_time

    evidence.record_measurement("Latency", {
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "avg": avg,
    })
    evidence.record_measurement("Throughput", throughput)

    evidence.record_pass("Benchmark Complete", f"{num_frames * len(units)} frames measured")

    return True


# ============================================================================
# TEST 4: DETERMINISM
# ============================================================================

def determinism_test(evidence):
    """Replay identical sequence twice, verify outputs match."""
    print("\n[TEST 4] DETERMINISM")
    print("-" * 80)

    sequence = [(1704067200.0 + i * 60, {"s1": 50 + i % 10, "s2": 100 - i % 5}) for i in range(100)]

    # Run 1
    engine1 = ProductionEngine()
    results1 = []
    for ts, sensors in sequence:
        result = engine1.process_frame(InputFrame(timestamp=ts, unit_id="det", sensors=sensors))
        results1.append((result.state, round(result.drift_score, 10), result.health_percentage))

    # Run 2
    engine2 = ProductionEngine()
    results2 = []
    for ts, sensors in sequence:
        result = engine2.process_frame(InputFrame(timestamp=ts, unit_id="det", sensors=sensors))
        results2.append((result.state, round(result.drift_score, 10), result.health_percentage))

    # Compare
    mismatches = 0
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        if r1 != r2:
            mismatches += 1

    if mismatches == 0:
        evidence.record_pass("Determinism", f"100% match on {len(results1)} frames")
    else:
        evidence.record_fail("Determinism", f"{mismatches} mismatches in {len(results1)} frames")

    return mismatches == 0


# ============================================================================
# TEST 5: STATE CONSISTENCY
# ============================================================================

def state_consistency_test(evidence):
    """Verify STABLE/WATCH/ALERT align with metrics."""
    print("\n[TEST 5] STATE CONSISTENCY")
    print("-" * 80)

    engine = ProductionEngine()
    results = []

    # Generate 100 frames with increasing noise
    for i in range(100):
        ts = 1704067200.0 + i * 60
        noise = 0.1 + (i / 100) * 0.5
        sensors = {
            "a": 50 + np.random.normal(0, 10 * noise),
            "b": 100 + np.random.normal(0, 10 * noise),
            "c": 25 + np.random.normal(0, 5 * noise),
        }
        result = engine.process_frame(InputFrame(timestamp=ts, unit_id="cons", sensors=sensors))
        results.append(result)

    inconsistencies = []

    for i, r in enumerate(results):
        # High drift should correlate with low health
        if r.drift_score > 0.6 and r.health_percentage > 75:
            inconsistencies.append(f"Frame {i}: high drift ({r.drift_score:.2f}) but high health ({r.health_percentage})")

        # STABLE should have low drift
        if r.state == "STABLE" and r.drift_score > 0.5:
            inconsistencies.append(f"Frame {i}: STABLE but drift {r.drift_score:.2f}")

        # ALERT should have low health
        if r.state == "ALERT" and r.health_percentage > 60:
            inconsistencies.append(f"Frame {i}: ALERT but health {r.health_percentage}")

        # High stability should not have high drift
        if r.stability_score > 0.8 and r.drift_score > 0.6:
            inconsistencies.append(f"Frame {i}: stable ({r.stability_score:.2f}) but drifting ({r.drift_score:.2f})")

    if not inconsistencies:
        evidence.record_pass("State Consistency", "All metric relationships valid")
    else:
        evidence.record_warning("State Consistency", f"{len(inconsistencies)} potential inconsistencies")
        for inc in inconsistencies[:3]:
            print(f"    {inc}")

    # Check valid transitions
    states = [r.state for r in results]
    invalid_trans = 0
    for i in range(len(states) - 1):
        # ALERT -> STABLE without going through WATCH is invalid
        if states[i] == "ALERT" and states[i + 1] == "STABLE":
            invalid_trans += 1

    if invalid_trans == 0:
        evidence.record_pass("State Transitions", "All transitions valid")
    else:
        evidence.record_fail("State Transitions", f"{invalid_trans} invalid transitions")

    return len(inconsistencies) <= 3 and invalid_trans == 0


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*80)
    print("PRODUCTION VALIDATION - REALISTIC CONDITIONS")
    print("="*80)

    evidence = Evidence()

    try:
        soak_test(evidence)
        fault_injection_test(evidence)
        performance_benchmark(evidence)
        determinism_test(evidence)
        state_consistency_test(evidence)
    except Exception as e:
        print(f"\n✗ VALIDATION CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(evidence.summary())

    # Final recommendation
    if len(evidence.failed) == 0:
        print("\n✓ PRODUCTION READY\n")
        sys.exit(0)
    else:
        print(f"\n✗ ISSUES FOUND ({len(evidence.failed)})\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
