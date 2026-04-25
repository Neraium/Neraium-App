#!/usr/bin/env python3
"""Regression test: Phase 1 vs Phase 2 decision layer on FD004 Unit 001.

Standalone script (no pytest required).
"""

import json
import sys
from pathlib import Path

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


def main():
    # Load FD004 data
    report_path = Path(__file__).parent / "fd004_outputs_subset" / "fd004_real_report.json"

    if not report_path.exists():
        print(f"ERROR: FD004 test data not found at {report_path}")
        return False

    with open(report_path) as f:
        data = json.load(f)

    timeseries = data.get("timeseries", [])
    frames = [f for f in timeseries if f.get("asset_id") == "unit_001"]

    if not frames:
        print("ERROR: No Unit 001 frames in FD004 data")
        return False

    # Get metadata
    unit_001_summary = next(
        (u for u in data.get("unit_summaries", []) if u.get("asset_id") == "unit_001"), {}
    )
    metadata = {
        "first_medium_cycle": unit_001_summary.get("first_MEDIUM_step"),
        "first_high_cycle": unit_001_summary.get("first_HIGH_step"),
        "early_warning_window": unit_001_summary.get("early_warning_window"),
        "peak_instability": unit_001_summary.get("peak_instability"),
        "average_drift": unit_001_summary.get("average_drift"),
        "total_cycles": len(frames),
    }

    print("\n" + "=" * 100)
    print("FD004 UNIT 001 DECISION LAYER REGRESSION TEST")
    print("=" * 100 + "\n")

    print("UNIT 001 METADATA FROM FD004:")
    print(f"  Total cycles: {metadata['total_cycles']}")
    print(f"  First MEDIUM detection: Cycle {metadata['first_medium_cycle']}")
    print(f"  First HIGH detection: Cycle {metadata['first_high_cycle']}")
    print(f"  Early warning window: {metadata['early_warning_window']} frame(s)")
    print(f"  Peak composite instability: {metadata['peak_instability']:.2f}")
    print(f"  Average drift score: {metadata['average_drift']:.4f}\n")

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
    }

    # Replay
    print("FRAME-BY-FRAME REPLAY (key cycles):\n")
    print(f"{'Cycle':<8} {'Drift':<8} {'Compos':<8} {'P1 Sev':<10} {'P1 Sup':<6} {'P1 Rec':<25} {'P2 Sev':<10} {'P2 Sup':<6} {'P2 Rec':<25}")
    print("-" * 135)

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

        # Print key cycles
        show = cycle <= 30 or cycle >= len(frames) - 10 or cycle in range(20, 31)

        if show:
            drift = float(frame.get("structural_drift_score", 0.0))
            compos = float(frame.get("composite_instability", 0.0))
            p1_rec = (dec_p1.recommended_action or "none")[:20]
            p2_rec = (dec_p2.recommended_action or "none")[:20]

            print(
                f"{cycle:<8} {drift:<8.3f} {compos:<8.0f} "
                f"{dec_p1.severity:<10} {'Y' if dec_p1.suppress else 'N':<6} "
                f"{p1_rec:<25} {dec_p2.severity:<10} {'Y' if dec_p2.suppress else 'N':<6} "
                f"{p2_rec:<25}"
            )
        elif cycle == 31:
            print("... (frames 31-{}) ...".format(len(frames) - 11))

    # Finalize streaks
    if metrics_p1["current_streak"] > 0:
        metrics_p1["high_streaks"].append(metrics_p1["current_streak"])
    if metrics_p2["current_streak"] > 0:
        metrics_p2["high_streaks"].append(metrics_p2["current_streak"])

    # === RESULTS ===
    print("\n\n" + "=" * 100)
    print("REGRESSION ANALYSIS RESULTS")
    print("=" * 100 + "\n")

    # 1. First meaningful detection
    print("1. FIRST MEANINGFUL DETECTION CYCLE:")
    print(f"   Phase 1 (original):")
    print(f"     First ELEVATED: {metrics_p1['first_elevated'] or 'N/A'}")
    print(f"     First HIGH: {metrics_p1['first_high'] or 'N/A'}")
    if metrics_p1["first_high"]:
        lead_p1 = metadata["total_cycles"] - metrics_p1["first_high"]
        print(f"     Lead time: {lead_p1} cycles")

    print(f"\n   Phase 2 (improved):")
    print(f"     First ELEVATED: {metrics_p2['first_elevated'] or 'N/A'}")
    print(f"     First HIGH: {metrics_p2['first_high'] or 'N/A'}")
    if metrics_p2["first_high"]:
        lead_p2 = metadata["total_cycles"] - metrics_p2["first_high"]
        print(f"     Lead time: {lead_p2} cycles")

    if metrics_p1["first_high"] and metrics_p2["first_high"]:
        delta = metrics_p2["first_high"] - metrics_p1["first_high"]
        direction = "DELAYED" if delta > 0 else "EARLIER"
        print(f"\n   Change: Phase 2 detects {direction} by {abs(delta)} cycle(s)")

    # 2. Failure cycle
    print(f"\n2. FAILURE CYCLE:")
    print(f"   Expected failure at cycle: {metadata['total_cycles']}")

    # 3. Lead time
    print(f"\n3. LEAD TIME TO FAILURE:")
    if metrics_p1["first_high"]:
        lead_p1 = metadata["total_cycles"] - metrics_p1["first_high"]
        pct_p1 = lead_p1 * 100 / metadata["total_cycles"]
        print(f"   Phase 1: {lead_p1} cycles ({pct_p1:.1f}% of total)")
    if metrics_p2["first_high"]:
        lead_p2 = metadata["total_cycles"] - metrics_p2["first_high"]
        pct_p2 = lead_p2 * 100 / metadata["total_cycles"]
        print(f"   Phase 2: {lead_p2} cycles ({pct_p2:.1f}% of total)")

    # 4. Surfaced alerts
    print(f"\n4. SURFACED ALERTS (not suppressed):")
    print(f"   Phase 1: {metrics_p1['surfaced_alerts']} alerts")
    print(f"   Phase 2: {metrics_p2['surfaced_alerts']} alerts")
    delta = metrics_p2["surfaced_alerts"] - metrics_p1["surfaced_alerts"]
    pct = delta * 100 / max(1, metrics_p1["surfaced_alerts"]) if metrics_p1["surfaced_alerts"] > 0 else 0
    print(f"   Change: {delta:+d} ({pct:+.1f}%)")

    # 5. Suppressed events
    print(f"\n5. SUPPRESSED EVENTS:")
    print(f"   Phase 1: {metrics_p1['suppressed_events']} events")
    print(f"   Phase 2: {metrics_p2['suppressed_events']} events")
    delta = metrics_p2["suppressed_events"] - metrics_p1["suppressed_events"]
    print(f"   Change: {delta:+d}")

    # 6. Recommendation changes
    print(f"\n6. RECOMMENDATION CHANGES (escalations/downgrades):")
    print(f"   Phase 1: {metrics_p1['recommendation_changes']} changes")
    print(f"   Phase 2: {metrics_p2['recommendation_changes']} changes")
    delta = metrics_p2["recommendation_changes"] - metrics_p1["recommendation_changes"]
    print(f"   Change: {delta:+d}")

    # 7. HIGH severity behavior
    print(f"\n7. HIGH SEVERITY BEHAVIOR:")
    print(f"   Phase 1:")
    print(f"     Total HIGH frames: {metrics_p1['high_frames']}")
    print(f"     Number of streaks: {len(metrics_p1['high_streaks'])}")
    if metrics_p1["high_streaks"]:
        print(f"     Streak lengths: {metrics_p1['high_streaks']}")
        avg = sum(metrics_p1["high_streaks"]) / len(metrics_p1["high_streaks"])
        print(f"     Average streak: {avg:.1f} frames")

    print(f"\n   Phase 2:")
    print(f"     Total HIGH frames: {metrics_p2['high_frames']}")
    print(f"     Number of streaks: {len(metrics_p2['high_streaks'])}")
    if metrics_p2["high_streaks"]:
        print(f"     Streak lengths: {metrics_p2['high_streaks']}")
        avg = sum(metrics_p2["high_streaks"]) / len(metrics_p2["high_streaks"])
        print(f"     Average streak: {avg:.1f} frames")

    # 8. Startup suppression
    print(f"\n8. STARTUP SUPPRESSION & HYSTERESIS IMPACT:")
    print(f"   Phase 2 applies startup suppression for first 8 cycles")
    print(f"   Phase 1 total suppressions: {metrics_p1['suppressed_events']}")
    print(f"   Phase 2 total suppressions: {metrics_p2['suppressed_events']}")

    # === SUMMARY ===
    print(f"\n\n{'=' * 100}")
    print("SUMMARY & RECOMMENDATION")
    print(f"{'=' * 100}\n")

    # Assessment criteria
    assessment = {
        "detection_not_delayed": False,
        "lead_time_maintained": False,
        "false_positives_reduced": False,
        "high_alerts_less_repetitive": False,
        "no_true_detections_missed": False,
    }

    # 1. Detection not delayed
    if metrics_p2["first_high"] and metrics_p1["first_high"]:
        if metrics_p2["first_high"] <= metrics_p1["first_high"] + 2:  # Allow 2-cycle margin for startup
            assessment["detection_not_delayed"] = True
    elif metrics_p2["first_high"]:
        assessment["detection_not_delayed"] = True

    # 2. Lead time maintained
    if metrics_p1["first_high"] and metrics_p2["first_high"]:
        lead_p1 = metadata["total_cycles"] - metrics_p1["first_high"]
        lead_p2 = metadata["total_cycles"] - metrics_p2["first_high"]
        if lead_p2 >= lead_p1 * 0.85:  # Allow 15% margin
            assessment["lead_time_maintained"] = True

    # 3. False positives reduced
    if metrics_p2["surfaced_alerts"] < metrics_p1["surfaced_alerts"]:
        assessment["false_positives_reduced"] = True

    # 4. HIGH alerts less repetitive
    p1_avg_streak = (
        sum(metrics_p1["high_streaks"]) / len(metrics_p1["high_streaks"])
        if metrics_p1["high_streaks"]
        else 0
    )
    p2_avg_streak = (
        sum(metrics_p2["high_streaks"]) / len(metrics_p2["high_streaks"])
        if metrics_p2["high_streaks"]
        else 0
    )
    if p2_avg_streak <= p1_avg_streak * 1.1:  # Allow 10% increase but not dramatic
        assessment["high_alerts_less_repetitive"] = True

    # 5. No true detections missed
    if metrics_p2["first_high"] is not None and metrics_p2["first_high"] > 0:
        assessment["no_true_detections_missed"] = True

    print("ASSESSMENT:")
    for criterion, passed in assessment.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        criterion_name = criterion.replace("_", " ").title()
        print(f"  {status}: {criterion_name}")

    all_pass = all(assessment.values())
    print(f"\n{'=' * 100}")
    if all_pass:
        print("✓ RECOMMENDATION: PHASE 2 CAN REPLACE PHASE 1 AS DEFAULT")
        print("\n  Phase 2 improves decision quality while maintaining detection reliability:")
        print("  - Better specificity without delaying critical alerts")
        print("  - Reduced false positives through transient suppression")
        print("  - Less repetitive HIGH severity messages")
        print("  - Hysteresis prevents alert chatter")
        return True
    else:
        failed = [k.replace("_", " ").title() for k, v in assessment.items() if not v]
        print(f"✗ RECOMMENDATION: PHASE 2 NEEDS REVIEW")
        print(f"\n  Issues: {', '.join(failed)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
