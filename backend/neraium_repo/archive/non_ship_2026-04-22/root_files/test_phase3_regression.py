#!/usr/bin/env python3
"""Quick test runner for Phase 3 temporal intelligence on FD004 Unit 001."""

import json
from pathlib import Path
from neraium_core.decision import DecisionEngine
from neraium_core.decision.models import SeverityLevel


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
    phase_map = {"drift": "degrading"}
    system_phase = phase_map.get(phase, phase)

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
        "data_quality": {
            "missing_sensor_count": 0,
            "valid_signal_count": 3,
        },
    }


def main():
    print("\n" + "=" * 80)
    print("PHASE 3 TEMPORAL INTELLIGENCE REGRESSION TEST")
    print("=" * 80 + "\n")

    # Load test data
    report_path = Path("fd004_outputs_subset/fd004_real_report.json")
    if not report_path.exists():
        print(f"ERROR: Test data not found at {report_path}")
        return 1

    with open(report_path) as f:
        data = json.load(f)

    timeseries = data.get("timeseries", [])
    unit001_frames = [f for f in timeseries if f.get("asset_id") == "unit_001"]

    if not unit001_frames:
        print("ERROR: No Unit 001 frames found")
        return 1

    print(f"Loaded {len(unit001_frames)} frames for Unit 001\n")

    # Initialize engine with Phase 3
    engine = DecisionEngine(enable_persistence_tracking=True)

    # Track metrics
    metrics = {
        "first_elevated_cycle": None,
        "first_high_cycle": None,
        "total_surfaced": 0,
        "total_suppressed": 0,
        "high_streaks": [],
        "current_high_streak": 0,
        "last_rec": None,
        "rec_changes": 0,
        "trajectories": {},
        "transitions": [],
    }

    # Process frames
    print(f"{'Cycle':<8} {'Drift':<8} {'Sev':<12} {'Traj':<12} {'Trans':<20} {'Action':<15} {'Suppress':<10}")
    print("-" * 100)

    for cycle, frame in enumerate(unit001_frames, start=1):
        sii_output = build_sii_output_from_timeseries(frame)
        decision = engine.decide(sii_output=sii_output)

        # Track metrics
        if not decision.suppress:
            metrics["total_surfaced"] += 1
            if decision.severity == "ELEVATED" and metrics["first_elevated_cycle"] is None:
                metrics["first_elevated_cycle"] = cycle
            if decision.severity == "HIGH" and metrics["first_high_cycle"] is None:
                metrics["first_high_cycle"] = cycle
        else:
            metrics["total_suppressed"] += 1

        if decision.recommended_action and decision.recommended_action != metrics["last_rec"]:
            metrics["rec_changes"] += 1
            metrics["last_rec"] = decision.recommended_action

        if decision.severity == "HIGH":
            metrics["current_high_streak"] += 1
        else:
            if metrics["current_high_streak"] > 0:
                metrics["high_streaks"].append(metrics["current_high_streak"])
                metrics["current_high_streak"] = 0

        metrics["trajectories"][decision.trajectory] = metrics["trajectories"].get(decision.trajectory, 0) + 1

        if decision.transition_event:
            metrics["transitions"].append((cycle, decision.transition_event))

        # Print frames
        show = cycle <= 30 or cycle >= len(unit001_frames) - 10
        if show:
            drift = float(frame.get("structural_drift_score", 0.0))
            trans = decision.transition_event or ""
            rec = decision.recommended_action or "none"
            print(
                f"{cycle:<8} {drift:<8.3f} {decision.severity:<12} "
                f"{decision.trajectory:<12} {trans:<20} {rec:<15} "
                f"{'Y' if decision.suppress else 'N':<10}"
            )
        elif cycle == 31:
            print(f"... (frames 31-{len(unit001_frames) - 11}) ...")

    if metrics["current_high_streak"] > 0:
        metrics["high_streaks"].append(metrics["current_high_streak"])

    # Report results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80 + "\n")

    print(f"First ELEVATED: Cycle {metrics['first_elevated_cycle']}")
    print(f"First HIGH: Cycle {metrics['first_high_cycle']}")
    if metrics["first_high_cycle"]:
        lead_time = len(unit001_frames) - metrics["first_high_cycle"]
        print(f"Lead time: {lead_time} cycles ({lead_time * 100 / len(unit001_frames):.1f}%)")

    print(f"\nSurfaced alerts: {metrics['total_surfaced']}")
    print(f"Suppressed events: {metrics['total_suppressed']}")
    print(f"Recommendation changes: {metrics['rec_changes']}")
    print(f"Total HIGH frames: {sum(metrics['high_streaks'])}")
    print(f"HIGH streak count: {len(metrics['high_streaks'])}")
    if metrics["high_streaks"]:
        print(f"HIGH streak lengths: {metrics['high_streaks']}")

    print(f"\nTrajectory distribution:")
    for traj, count in sorted(metrics["trajectories"].items()):
        print(f"  {traj}: {count} frames")

    print(f"\nState transitions detected: {len(metrics['transitions'])}")
    for cycle, event in metrics["transitions"][:5]:
        print(f"  Cycle {cycle}: {event}")

    # Validation: HIGH should appear at cycle ~26 based on FD004 Unit 001
    expected_high_cycle = 26
    if metrics["first_high_cycle"] is not None:
        if metrics["first_high_cycle"] <= expected_high_cycle + 5:
            print(f"\n✓ PASS: HIGH detected at cycle {metrics['first_high_cycle']} (expected ~{expected_high_cycle})")
            return 0
        else:
            print(f"\n✗ FAIL: HIGH detected at cycle {metrics['first_high_cycle']} (expected ~{expected_high_cycle})")
            return 1
    else:
        print(f"\n✗ FAIL: HIGH severity never reached")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
