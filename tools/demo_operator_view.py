from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pronostia_runner import load_pronostia, run_engine, save_outputs


def classify_severity(velocity):
    if velocity is None:
        return "UNCERTAIN"

    if velocity > 0.008:
        return "FAST DEGRADATION"
    if velocity > 0.003:
        return "MODERATE DEGRADATION"

    return "SLOW OR UNCERTAIN"


def build_operator_summary(results):
    traj = results["trajectory"]

    if results["actionable_cycle"] is not None:
        stage = "ACTIONABLE"
    elif results["confirmed_instability_cycle"] is not None:
        stage = "CONFIRMED INSTABILITY"
    elif results["baseline_departure_cycle"] is not None:
        stage = "BASELINE DEPARTURE"
    else:
        stage = "STABLE"

    time_since_departure = None
    if (
        results["baseline_departure_cycle"] is not None
        and results["actionable_cycle"] is not None
    ):
        time_since_departure = (
            results["actionable_cycle"] - results["baseline_departure_cycle"]
        )

    severity = classify_severity(traj["velocity"])

    if stage == "ACTIONABLE":
        recommendation = "Investigate and plan intervention before degradation locks in."
    elif stage == "CONFIRMED INSTABILITY":
        recommendation = "Monitor closely. Structural instability is confirmed."
    elif stage == "BASELINE DEPARTURE":
        recommendation = "System has deviated from baseline. Continue monitoring."
    else:
        recommendation = "System operating within normal behavior."

    return {
        "system_status": stage,
        "risk_band": traj["risk_band"],
        "severity": severity,
        "departure_confidence": results["departure_confidence"],
        "baseline_finalized_cycle": results["baseline_finalized_cycle"],
        "baseline_departure_cycle": results["baseline_departure_cycle"],
        "structural_confirmation_cycle": results["confirmed_instability_cycle"],
        "actionable_cycle": results["actionable_cycle"],
        "failure_endpoint": results["failure_cycle"],
        "time_since_departure": time_since_departure,
        "actionable_lead_cycles": results["actionable_lead_cycles"],
        "trend": traj["trend"],
        "trajectory_mode": traj["mode"],
        "trajectory_velocity": traj["velocity"],
        "trajectory_acceleration": traj["acceleration"],
        "failure_time_estimate": traj["time_to_failure"],
        "recommendation": recommendation,
    }


def print_operator_view(summary):
    print()
    print("=" * 72)
    print("NERAIUM OPERATOR VIEW")
    print("=" * 72)

    print(f"System Status:          {summary['system_status']}")
    print(f"Risk Band:              {summary['risk_band']}")
    print(f"Severity:               {summary['severity']}")
    print(f"Departure Confidence:   {summary['departure_confidence']}")

    print()
    print("Timeline")
    print("-" * 72)
    print(f"Baseline Finalized:     {summary['baseline_finalized_cycle']}")
    print(f"Baseline Departure:     {summary['baseline_departure_cycle']}")
    print(f"Structural Confirmation: {summary['structural_confirmation_cycle']}")
    print(f"Actionable Point:       {summary['actionable_cycle']}")
    print(f"Failure Endpoint:       {summary['failure_endpoint']}")

    print()
    print("Decision Context")
    print("-" * 72)
    print(f"Time Since Departure:   {summary['time_since_departure']}")
    print(f"Actionable Lead Time:   {summary['actionable_lead_cycles']}")
    print(f"Trend:                  {summary['trend']}")
    print(f"Trajectory Mode:        {summary['trajectory_mode']}")
    print(f"Velocity:               {summary['trajectory_velocity']}")
    print(f"Acceleration:           {summary['trajectory_acceleration']}")
    print(f"Failure Time Estimate:  {summary['failure_time_estimate']}")

    print()
    print("Recommendation")
    print("-" * 72)
    print(summary["recommendation"])
    print("=" * 72)
    print()


def main():
    raw_run, rul, failure_cycle = load_pronostia(
        fd=1,
        split="dev",
        run_index=0,
    )

    results = run_engine(
        raw_run=raw_run,
        failure_cycle=failure_cycle,
        baseline_window=50,
        recent_window=12,
        post_baseline_delay=40,
        persistence_required=4,
        adaptive_window=75,
        adaptive_z=2.5,
    )

    summary = build_operator_summary(results)
    print_operator_view(summary)

    save_outputs(results, rul)

    print("Demo complete.")


if __name__ == "__main__":
    main()