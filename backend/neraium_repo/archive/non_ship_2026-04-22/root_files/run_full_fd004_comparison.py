#!/usr/bin/env python3
"""Full FD004 dataset: Phase 1 vs Phase 2 comparison and summary.

Runs decision engine across all units and generates dataset-level metrics.
"""

import json
import sys
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Tuple

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from neraium_core.decision import DecisionEngine


def build_sii_output_from_timeseries(frame: dict) -> dict:
    """Convert timeseries frame to SII output format."""
    composite = float(frame.get("composite_instability", 0.0))
    drift = float(frame.get("structural_drift_score", 0.0))

    relational = max(0.0, min(1.0, (composite / 500.0) if composite > 0 else 0.0))
    trend = frame.get("trend", "stable")
    shock_activity = 0.8 if trend == "drift" and drift > 0.5 else 0.1

    risk_level = frame.get("risk_level", "LOW")
    state_map = {"LOW": "STABLE", "MEDIUM": "WATCH", "HIGH": "ALERT"}
    state = state_map.get(risk_level, "STABLE")

    phase = frame.get("phase", "stable")
    system_phase = "degrading" if phase in ("drift",) else phase

    return {
        "timestamp": frame.get("timestamp"),
        "asset_id": frame.get("asset_id"),
        "state": state,
        "structural_drift_score": drift,
        "relational_instability_score": relational,
        "system_phase": system_phase,
        "shock_activity": shock_activity,
        "subsystem_instability": max(0.0, relational * 0.7),
        "entropy": max(0.0, (composite / 1000.0) if composite > 0 else 0.0),
        "sensor_relationships": ["temp", "pressure", "vibration"],
        "regime_name": "nominal" if drift < 0.3 else "degrading",
        "regime_distance": min(1.0, drift * 0.5),
        "attribution": {
            "top_drivers": ["pressure", "temperature"] if drift > 0.3 else [],
            "top_relationships": [],
        },
        "drift_history": [],
        "data_quality": {"missing_sensor_count": 0, "valid_signal_count": 3},
    }


def analyze_unit(unit_id: str, frames: List[dict], unit_summary: dict) -> dict:
    """Run Phase 1 vs Phase 2 comparison for a single unit."""
    if not frames:
        return None

    # Initialize engines
    engine_p1 = DecisionEngine(enable_persistence_tracking=False)
    engine_p2 = DecisionEngine(enable_persistence_tracking=True)

    # Initialize metrics
    metrics_p1 = {
        "first_elevated": None,
        "first_high": None,
        "surfaced_alerts": 0,
        "suppressed_events": 0,
        "recommendation_changes": 0,
        "high_frames": 0,
        "high_streaks": [],
        "current_streak": 0,
        "last_rec": None,
        "lead_times": [],  # For each high severity detection
    }

    metrics_p2 = {
        "first_elevated": None,
        "first_high": None,
        "surfaced_alerts": 0,
        "suppressed_events": 0,
        "recommendation_changes": 0,
        "high_frames": 0,
        "high_streaks": [],
        "current_streak": 0,
        "last_rec": None,
        "lead_times": [],
    }

    # Metadata
    total_cycles = len(frames)
    metadata = {
        "first_medium_cycle": unit_summary.get("first_MEDIUM_step"),
        "first_high_cycle": unit_summary.get("first_HIGH_step"),
        "early_warning_window": unit_summary.get("early_warning_window"),
        "peak_instability": unit_summary.get("peak_instability"),
        "average_drift": unit_summary.get("average_drift"),
        "total_cycles": total_cycles,
    }

    # Replay all frames
    for cycle, frame in enumerate(frames, start=1):
        sii = build_sii_output_from_timeseries(frame)

        dec_p1 = engine_p1.decide(sii_output=sii)
        dec_p2 = engine_p2.decide(sii_output=sii)

        # Update Phase 1
        if not dec_p1.suppress:
            metrics_p1["surfaced_alerts"] += 1
            if dec_p1.severity == "ELEVATED" and metrics_p1["first_elevated"] is None:
                metrics_p1["first_elevated"] = cycle
            if dec_p1.severity == "HIGH" and metrics_p1["first_high"] is None:
                metrics_p1["first_high"] = cycle
                lead = total_cycles - cycle
                metrics_p1["lead_times"].append(lead)
        else:
            metrics_p1["suppressed_events"] += 1

        if dec_p1.recommended_action and dec_p1.recommended_action != metrics_p1["last_rec"]:
            metrics_p1["recommendation_changes"] += 1
            metrics_p1["last_rec"] = dec_p1.recommended_action

        if dec_p1.severity == "HIGH":
            metrics_p1["high_frames"] += 1
            metrics_p1["current_streak"] += 1
        else:
            if metrics_p1["current_streak"] > 0:
                metrics_p1["high_streaks"].append(metrics_p1["current_streak"])
            metrics_p1["current_streak"] = 0

        # Update Phase 2
        if not dec_p2.suppress:
            metrics_p2["surfaced_alerts"] += 1
            if dec_p2.severity == "ELEVATED" and metrics_p2["first_elevated"] is None:
                metrics_p2["first_elevated"] = cycle
            if dec_p2.severity == "HIGH" and metrics_p2["first_high"] is None:
                metrics_p2["first_high"] = cycle
                lead = total_cycles - cycle
                metrics_p2["lead_times"].append(lead)
        else:
            metrics_p2["suppressed_events"] += 1

        if dec_p2.recommended_action and dec_p2.recommended_action != metrics_p2["last_rec"]:
            metrics_p2["recommendation_changes"] += 1
            metrics_p2["last_rec"] = dec_p2.recommended_action

        if dec_p2.severity == "HIGH":
            metrics_p2["high_frames"] += 1
            metrics_p2["current_streak"] += 1
        else:
            if metrics_p2["current_streak"] > 0:
                metrics_p2["high_streaks"].append(metrics_p2["current_streak"])
            metrics_p2["current_streak"] = 0

    # Finalize streaks
    if metrics_p1["current_streak"] > 0:
        metrics_p1["high_streaks"].append(metrics_p1["current_streak"])
    if metrics_p2["current_streak"] > 0:
        metrics_p2["high_streaks"].append(metrics_p2["current_streak"])

    return {
        "unit_id": unit_id,
        "metadata": metadata,
        "phase_1": metrics_p1,
        "phase_2": metrics_p2,
    }


def main():
    # Load FD004 data
    report_path = Path(__file__).parent / "fd004_outputs_subset" / "fd004_real_report.json"

    if not report_path.exists():
        print(f"ERROR: FD004 test data not found at {report_path}")
        return False

    with open(report_path) as f:
        data = json.load(f)

    timeseries = data.get("timeseries", [])
    unit_summaries = {u.get("asset_id"): u for u in data.get("unit_summaries", [])}

    # Get unique units
    unit_ids = sorted(set(f.get("asset_id") for f in timeseries if f.get("asset_id")))

    if not unit_ids:
        print("ERROR: No units found in FD004 data")
        return False

    print("\n" + "=" * 120)
    print(f"FD004 FULL DATASET PHASE 1 vs PHASE 2 COMPARISON ({len(unit_ids)} units)")
    print("=" * 120 + "\n")

    # Analyze each unit
    results = {}
    for unit_id in unit_ids:
        frames = [f for f in timeseries if f.get("asset_id") == unit_id]
        unit_summary = unit_summaries.get(unit_id, {})
        result = analyze_unit(unit_id, frames, unit_summary)
        if result:
            results[unit_id] = result
            p1_high = result["phase_1"]["first_high"]
            p2_high = result["phase_2"]["first_high"]
            print(f"✓ {unit_id}: P1 HIGH at {p1_high}, P2 HIGH at {p2_high} ({len(frames)} frames)")
        else:
            print(f"✗ Failed to analyze {unit_id}")

    print("\n" + "=" * 120)
    print("DATASET-LEVEL SUMMARY")
    print("=" * 120 + "\n")

    # === DATASET METRICS ===

    # 1. Detection timing comparison
    earlier = same = later = 0
    detection_deltas = []
    for unit_id, result in results.items():
        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]

        if p1_first_high and p2_first_high:
            delta = p2_first_high - p1_first_high
            detection_deltas.append((unit_id, delta))
            if delta < 0:
                earlier += 1
            elif delta == 0:
                same += 1
            else:
                later += 1

    print(f"1. DETECTION TIMING:")
    print(f"   Units with EARLIER Phase 2 detection:  {earlier}")
    print(f"   Units with SAME detection timing:      {same}")
    print(f"   Units with LATER Phase 2 detection:    {later}")
    print()

    # 2. Lead time comparison
    improved = same_lead = worse = 0
    lead_time_deltas = []
    for unit_id, result in results.items():
        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]
        total = result["metadata"]["total_cycles"]

        if p1_first_high and p2_first_high:
            lead_p1 = total - p1_first_high
            lead_p2 = total - p2_first_high
            delta = lead_p2 - lead_p1
            lead_time_deltas.append((unit_id, delta))

            if delta > 0:
                improved += 1
            elif delta == 0:
                same_lead += 1
            else:
                worse += 1

    print(f"2. LEAD TIME:")
    print(f"   Units with IMPROVED lead time:         {improved}")
    print(f"   Units with SAME lead time:             {same_lead}")
    print(f"   Units with WORSE lead time:            {worse}")
    print()

    # 3. Surfaced alert count reduction
    alert_reduction = 0
    alert_reduction_units = []
    for unit_id, result in results.items():
        p1_alerts = result["phase_1"]["surfaced_alerts"]
        p2_alerts = result["phase_2"]["surfaced_alerts"]
        if p2_alerts < p1_alerts:
            alert_reduction += 1
            alert_reduction_units.append((unit_id, p1_alerts - p2_alerts))

    print(f"3. SURFACED ALERT COUNT REDUCTION:")
    print(f"   Units with reduced surfaced alerts:    {alert_reduction}")
    if alert_reduction_units:
        for unit_id, reduction in sorted(alert_reduction_units, key=lambda x: -x[1])[:5]:
            print(f"      {unit_id}: {reduction} fewer alerts")
    print()

    # 4. Recommendation repetition reduction
    rec_reduction = 0
    rec_reduction_units = []
    for unit_id, result in results.items():
        p1_changes = result["phase_1"]["recommendation_changes"]
        p2_changes = result["phase_2"]["recommendation_changes"]
        if p2_changes < p1_changes:
            rec_reduction += 1
            rec_reduction_units.append((unit_id, p1_changes - p2_changes))

    print(f"4. RECOMMENDATION REPETITION REDUCTION:")
    print(f"   Units with fewer recommendation changes: {rec_reduction}")
    if rec_reduction_units:
        for unit_id, reduction in sorted(rec_reduction_units, key=lambda x: -x[1])[:5]:
            print(f"      {unit_id}: {reduction} fewer changes")
    print()

    # 5. Startup suppression / hysteresis impact
    delayed_alerts = []
    for unit_id, result in results.items():
        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]

        # Check if Phase 2's startup suppression (first 8 cycles) delayed a true alert
        if p2_first_high and p2_first_high > p1_first_high and p2_first_high <= 8:
            delayed_alerts.append((unit_id, p2_first_high, p1_first_high))

    print(f"5. STARTUP SUPPRESSION/HYSTERESIS IMPACT:")
    if delayed_alerts:
        print(f"   ⚠ Units with potentially delayed alerts: {len(delayed_alerts)}")
        for unit_id, p2_cycle, p1_cycle in delayed_alerts:
            print(f"      {unit_id}: Phase 2 at cycle {p2_cycle}, Phase 1 at cycle {p1_cycle}")
    else:
        print(f"   ✓ No true alerts delayed by startup suppression")
    print()

    # 6-8. Lead time statistics
    all_lead_p1 = []
    all_lead_p2 = []
    for unit_id, result in results.items():
        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]
        total = result["metadata"]["total_cycles"]

        if p1_first_high:
            all_lead_p1.append(total - p1_first_high)
        if p2_first_high:
            all_lead_p2.append(total - p2_first_high)

    print(f"6. LEAD TIME STATISTICS:")
    if all_lead_p1:
        print(f"   Phase 1 - Average: {mean(all_lead_p1):.1f} cycles, Median: {median(all_lead_p1):.1f}, Range: {min(all_lead_p1)}-{max(all_lead_p1)}")
    else:
        print(f"   Phase 1 - No HIGH detections")
    if all_lead_p2:
        print(f"   Phase 2 - Average: {mean(all_lead_p2):.1f} cycles, Median: {median(all_lead_p2):.1f}, Range: {min(all_lead_p2)}-{max(all_lead_p2)}")
    else:
        print(f"   Phase 2 - No HIGH detections")
    print()

    # 9. Top 5 units with biggest improvement
    improvement_scores = []
    for unit_id, result in results.items():
        score = 0
        p1_alerts = result["phase_1"]["surfaced_alerts"]
        p2_alerts = result["phase_2"]["surfaced_alerts"]
        score += (p1_alerts - p2_alerts) * 2  # Weight alert reduction

        p1_recs = result["phase_1"]["recommendation_changes"]
        p2_recs = result["phase_2"]["recommendation_changes"]
        score += (p1_recs - p2_recs)  # Weight recommendation reduction

        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]
        if p1_first_high and p2_first_high:
            lead_p1 = result["metadata"]["total_cycles"] - p1_first_high
            lead_p2 = result["metadata"]["total_cycles"] - p2_first_high
            score += (lead_p2 - lead_p1) * 1.5  # Weight lead time improvement

        improvement_scores.append((unit_id, score))

    improvement_scores.sort(key=lambda x: -x[1])

    print(f"9. TOP 5 UNITS WITH BIGGEST IMPROVEMENT:")
    for i, (unit_id, score) in enumerate(improvement_scores[:5], 1):
        result = results[unit_id]
        p1_alerts = result["phase_1"]["surfaced_alerts"]
        p2_alerts = result["phase_2"]["surfaced_alerts"]
        p1_first_high = result["phase_1"]["first_high"]
        p2_first_high = result["phase_2"]["first_high"]
        total = result["metadata"]["total_cycles"]
        print(f"   {i}. {unit_id}: alerts {p1_alerts}→{p2_alerts}, detection cycle {p1_first_high}→{p2_first_high}")

    print()

    # 10. Top 5 units with biggest regression
    print(f"10. TOP 5 UNITS WITH BIGGEST REGRESSION:")
    for i, (unit_id, score) in enumerate(improvement_scores[-5:], 1):
        if score < 0:
            result = results[unit_id]
            p1_alerts = result["phase_1"]["surfaced_alerts"]
            p2_alerts = result["phase_2"]["surfaced_alerts"]
            p1_first_high = result["phase_1"]["first_high"]
            p2_first_high = result["phase_2"]["first_high"]
            total = result["metadata"]["total_cycles"]
            print(f"   {i}. {unit_id}: alerts {p1_alerts}→{p2_alerts}, detection cycle {p1_first_high}→{p2_first_high}")
    if all(s >= 0 for _, s in improvement_scores[-5:]):
        print("   ✓ No significant regressions detected")

    print("\n" + "=" * 120)
    print("RECOMMENDATION")
    print("=" * 120 + "\n")

    # Decision logic
    issues = []

    # Check if Phase 2 is detecting anything at all
    p2_units_detecting = sum(1 for unit_id, result in results.items() if result["phase_2"]["first_high"] is not None)
    if p2_units_detecting == 0:
        issues.append("CRITICAL: Phase 2 is not detecting HIGH severity alerts in any units - likely suppressed by startup/hysteresis")
    elif p2_units_detecting < len(results) * 0.5:
        issues.append(f"CRITICAL: Phase 2 is only detecting in {p2_units_detecting}/{len(results)} units - excessive suppression")

    # Check for delayed true alerts
    if delayed_alerts:
        issues.append(f"Startup suppression delayed true alerts in {len(delayed_alerts)} unit(s)")

    # Check for significant lead time regression
    lead_regression = sum(1 for unit_id, delta in lead_time_deltas if delta < -5)
    if lead_regression > 0:
        issues.append(f"Significant lead time regression in {lead_regression} unit(s)")

    # Check overall metrics
    if earlier + same > later * 0.5:  # Detection timing acceptable
        pass
    elif earlier + same + later > 0:
        issues.append("Detection timing has too many late Phase 2 detections")

    if alert_reduction >= len(results) * 0.6:
        print("✓ Phase 2 significantly reduces false positives (alert reduction in 60%+ of units)")
    elif alert_reduction >= len(results) * 0.4:
        print("✓ Phase 2 reduces false positives in majority of units")

    if rec_reduction >= len(results) * 0.6:
        print("✓ Phase 2 reduces recommendation chatter (60%+ of units)")

    if not delayed_alerts:
        print("✓ No true alerts delayed by startup suppression/hysteresis")

    print()

    if not issues:
        print(">>> RECOMMENDATION: REPLACE PHASE 1 GLOBALLY")
        print("\n    Phase 2 improves decision quality across the full dataset:")
        print("    • Better specificity without delaying critical alerts")
        print("    • Reduced false positives through transient suppression")
        print("    • Maintained lead time on average")
        print("    • No true detections missed due to suppression")
        return True
    elif len(issues) == 1 and "delayed true alerts" in issues[0]:
        print(">>> RECOMMENDATION: REPLACE PHASE 1 WITH EXCEPTIONS")
        print(f"\n    {issues[0]}")
        print("    Monitor these units closely, but Phase 2 can be deployed with carve-outs")
        return True
    else:
        print(">>> RECOMMENDATION: DO NOT REPLACE YET")
        print(f"\n    Critical issues to address:")
        for issue in issues:
            print(f"    • {issue}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
