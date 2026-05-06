from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from rul_datasets import FemtoReader
from neraium_core.sii_engine_unified import SIIEngine


OUT_DIR = Path("test_reports/pronostia_demo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_MEANINGFUL_LEAD = 100


def load_pronostia(fd=1, split="dev", run_index=0):
    print("Loading PRONOSTIA / FEMTO...")

    ds = FemtoReader(fd=fd)
    ds.prepare_data()
    X, y = ds.load_split(split)

    raw_run = X[run_index]
    rul = y[run_index]
    failure_cycle = int(np.where(rul <= 1)[0][0])

    print("raw run:", raw_run.shape)
    print("rul:", rul.shape)
    print("failure_cycle:", failure_cycle)
    print("rul start/end:", rul[0], rul[-1])

    return raw_run, rul, failure_cycle


def window_to_state(window):
    window = np.asarray(window, dtype=float)

    mean = window.mean(axis=0)
    std = window.std(axis=0)
    rms = np.sqrt(np.mean(window ** 2, axis=0))
    ptp = np.ptp(window, axis=0)

    return np.concatenate([mean, std, rms, ptp])


def smooth(series, window=35):
    series = np.asarray(series, dtype=float)

    if len(series) < window:
        return series

    kernel = np.ones(window) / window
    return np.convolve(series, kernel, mode="same")


def normalize(series):
    series = np.asarray(series, dtype=float)

    lo = np.nanmin(series)
    hi = np.nanmax(series)

    if hi - lo < 1e-12:
        return np.zeros_like(series)

    return (series - lo) / (hi - lo)


def classify_departure_confidence(cycle):
    if cycle is None:
        return "NONE"

    if cycle < 100:
        return "LOW"
    if cycle < 200:
        return "MEDIUM"

    return "HIGH"


def detect_confirmed_instability(drift_history, regime, urgency):
    """
    Confirmation layer.

    This is deliberately not just a slope test.
    It accepts nonlinear degradation by checking:
    - level
    - directional pressure
    - curvature
    - persistence
    - regime or urgency support
    """
    if len(drift_history) < 30:
        return False

    recent = np.asarray(drift_history[-30:], dtype=float)

    slope = float(np.polyfit(np.arange(len(recent)), recent, 1)[0])
    curvature = float(np.mean(np.diff(recent, 2)))
    increasing_ratio = float(np.mean(np.diff(recent) > 0))
    current = float(recent[-1])

    strong_level = current >= 0.65
    moderate_level = current >= 0.55

    directional_pressure = slope > 0.0005 or curvature > 0
    persistence = increasing_ratio >= 0.50

    regime_confirmed = regime in ("TRANSITION", "UNSTABLE", "LOCK_IN")
    urgency_confirmed = urgency in ("WATCH", "ALERT", "CRITICAL")

    return (
        (strong_level and (directional_pressure or persistence))
        or (moderate_level and persistence and (regime_confirmed or urgency_confirmed))
    )


def actionable_instability(drift_history, confirmed_cycle):
    if confirmed_cycle is None:
        return None

    min_window = 20
    max_window = 80

    for window in range(min_window, max_window + 1):
        if len(drift_history) < confirmed_cycle + window:
            return None

        segment = np.asarray(
            drift_history[confirmed_cycle:confirmed_cycle + window],
            dtype=float,
        )

        sustained = float(np.mean(segment > 0.60))
        slope = float(np.polyfit(np.arange(len(segment)), segment, 1)[0])
        not_recovering = slope >= -0.001

        if sustained >= 0.70 and not_recovering:
            return confirmed_cycle + window

    return None


def estimate_failure_trajectory(drift_history, current_cycle):
    if current_cycle is None:
        return {
            "time_to_failure": None,
            "estimated_failure_cycle": None,
            "confidence": 0.0,
            "trend": "not_actionable",
            "mode": "monitoring",
            "velocity": None,
            "acceleration": None,
            "risk_band": "unknown",
        }

    if len(drift_history) < 50:
        return {
            "time_to_failure": None,
            "estimated_failure_cycle": None,
            "confidence": 0.0,
            "trend": "insufficient_history",
            "mode": "monitoring",
            "velocity": None,
            "acceleration": None,
            "risk_band": "unknown",
        }

    recent_window = min(120, len(drift_history))
    recent = np.asarray(drift_history[-recent_window:], dtype=float)
    x = np.arange(len(recent))

    linear = np.polyfit(x, recent, 1)
    quadratic = np.polyfit(x, recent, 2)

    velocity = float(linear[0])
    acceleration = float(quadratic[0])
    current_drift = float(recent[-1])

    trend = "accelerating" if acceleration > 0 else "linear_or_flat_degradation"

    if current_drift >= 0.90:
        risk_band = "high"
    elif current_drift >= 0.70:
        risk_band = "elevated"
    elif current_drift >= 0.50:
        risk_band = "watch"
    else:
        risk_band = "low"

    late_stage = (
        current_drift > 0.85
        and velocity > 0.004
        and len(drift_history) > 150
    )

    if not late_stage:
        confidence = 0.60 if velocity > 0 else 0.35
        return {
            "time_to_failure": None,
            "estimated_failure_cycle": None,
            "confidence": round(confidence, 3),
            "trend": trend,
            "mode": "early_stage_monitoring",
            "velocity": velocity,
            "acceleration": acceleration,
            "risk_band": risk_band,
        }

    recent_min = float(np.min(recent))
    recent_max = float(np.max(recent))
    recent_span = recent_max - recent_min

    if recent_span < 1e-6:
        return {
            "time_to_failure": None,
            "estimated_failure_cycle": None,
            "confidence": 0.45,
            "trend": trend,
            "mode": "predictive_blocked_flat_span",
            "velocity": velocity,
            "acceleration": acceleration,
            "risk_band": risk_band,
        }

    normalized_position = (current_drift - recent_min) / recent_span
    normalized_position = float(np.clip(normalized_position, 0.0, 1.0))

    projected_horizon = int((1.0 - normalized_position) * 200)

    if projected_horizon <= 0 or projected_horizon > 500:
        return {
            "time_to_failure": None,
            "estimated_failure_cycle": None,
            "confidence": 0.50,
            "trend": trend,
            "mode": "predictive_blocked_unreliable_horizon",
            "velocity": velocity,
            "acceleration": acceleration,
            "risk_band": risk_band,
        }

    confidence = 0.55
    confidence += min(0.25, max(0.0, velocity * 10))
    confidence += min(0.20, max(0.0, acceleration * 100))
    confidence = round(min(0.90, max(0.40, confidence)), 3)

    return {
        "time_to_failure": projected_horizon,
        "estimated_failure_cycle": int(current_cycle + projected_horizon),
        "confidence": confidence,
        "trend": trend,
        "mode": "predictive_late_stage",
        "velocity": velocity,
        "acceleration": acceleration,
        "risk_band": risk_band,
    }


def run_engine(
    raw_run,
    failure_cycle,
    baseline_window=50,
    recent_window=12,
    post_baseline_delay=40,
    persistence_required=4,
    adaptive_window=75,
    adaptive_z=2.5,
):
    print("Running structural-first SII validation...")

    engine = SIIEngine(
        baseline_window=baseline_window,
        recent_window=recent_window,
    )

    cycles = []
    drift_history = []
    instability_history = []
    regimes = []
    urgencies = []

    baseline_departure_cycle = None
    confirmed_instability_cycle = None
    actionable_cycle = None

    departure_type = None
    departure_regime = None
    departure_urgency = None
    drift_at_departure = None
    departure_confidence = "NONE"

    confirmed_regime = None
    confirmed_urgency = None
    drift_at_confirmed = None

    actionable_regime = None
    actionable_urgency = None
    drift_at_actionable = None

    baseline_finalized_cycle = None
    baseline_was_ready = False
    drift_hit_streak = 0

    trajectory = None

    for cycle, window in enumerate(raw_run, start=1):
        state_vector = window_to_state(window)
        output = engine.update(state_vector, float(cycle))

        drift = float(output.structural_drift)
        instability = float(output.instability_score)
        regime = output.regime
        urgency = output.urgency

        cycles.append(cycle)
        drift_history.append(drift)
        instability_history.append(instability)
        regimes.append(regime)
        urgencies.append(urgency)

        if output.regime != "WARMUP" and not baseline_was_ready and engine.baseline_ready:
            baseline_finalized_cycle = cycle
            baseline_was_ready = True

        if output.regime == "WARMUP":
            continue

        if not baseline_was_ready:
            continue

        if cycle < baseline_finalized_cycle + post_baseline_delay:
            continue

        history = np.asarray(drift_history, dtype=float)

        if len(history) >= adaptive_window:
            recent = history[-adaptive_window:]
            adaptive_threshold = float(
                np.mean(recent) + adaptive_z * (np.std(recent) + 1e-9)
            )
        else:
            adaptive_threshold = float("inf")

        adaptive_structural_hit = drift > adaptive_threshold

        if adaptive_structural_hit:
            drift_hit_streak += 1
        else:
            drift_hit_streak = 0

        baseline_departure_hit = drift_hit_streak >= persistence_required

        regime_hit = regime in ("TRANSITION", "UNSTABLE", "LOCK_IN")
        urgency_hit = urgency in ("ALERT", "CRITICAL")

        regime_confirmation_hit = regime_hit and drift >= 0.40
        urgency_confirmation_hit = urgency_hit and drift >= 0.40

        if baseline_departure_cycle is None:
            if baseline_departure_hit:
                baseline_departure_cycle = cycle
                departure_type = "adaptive_baseline_departure"
                departure_regime = regime
                departure_urgency = urgency
                drift_at_departure = drift
                departure_confidence = classify_departure_confidence(cycle)

            elif regime_confirmation_hit:
                baseline_departure_cycle = cycle
                departure_type = "regime_confirmed_departure"
                departure_regime = regime
                departure_urgency = urgency
                drift_at_departure = drift
                departure_confidence = classify_departure_confidence(cycle)

            elif urgency_confirmation_hit:
                baseline_departure_cycle = cycle
                departure_type = "urgency_confirmed_departure"
                departure_regime = regime
                departure_urgency = urgency
                drift_at_departure = drift
                departure_confidence = classify_departure_confidence(cycle)

        if confirmed_instability_cycle is None:
            if detect_confirmed_instability(drift_history, regime, urgency):
                confirmed_instability_cycle = cycle
                confirmed_regime = regime
                confirmed_urgency = urgency
                drift_at_confirmed = drift

        if actionable_cycle is None:
            possible_actionable = actionable_instability(
                drift_history,
                confirmed_instability_cycle,
            )

            if possible_actionable is not None:
                actionable_cycle = possible_actionable
                actionable_regime = regime
                actionable_urgency = urgency
                drift_at_actionable = drift
                trajectory = estimate_failure_trajectory(
                    drift_history,
                    actionable_cycle,
                )

    baseline_departure_lead = (
        failure_cycle - baseline_departure_cycle
        if baseline_departure_cycle is not None and baseline_departure_cycle < failure_cycle
        else None
    )

    confirmed_instability_lead = (
        failure_cycle - confirmed_instability_cycle
        if confirmed_instability_cycle is not None and confirmed_instability_cycle < failure_cycle
        else None
    )

    actionable_lead = (
        failure_cycle - actionable_cycle
        if actionable_cycle is not None and actionable_cycle < failure_cycle
        else None
    )

    detected = (
        baseline_departure_cycle is not None
        and baseline_departure_cycle < failure_cycle
        and baseline_departure_lead is not None
        and baseline_departure_lead >= MIN_MEANINGFUL_LEAD
    )

    if trajectory is None:
        trajectory = estimate_failure_trajectory(
            drift_history,
            actionable_cycle,
        )

    return {
        "cycles": np.asarray(cycles),
        "drift": np.asarray(drift_history),
        "instability": np.asarray(instability_history),
        "regimes": regimes,
        "urgencies": urgencies,
        "detected": detected,
        "baseline_finalized_cycle": baseline_finalized_cycle,
        "baseline_departure_cycle": baseline_departure_cycle,
        "confirmed_instability_cycle": confirmed_instability_cycle,
        "actionable_cycle": actionable_cycle,
        "failure_cycle": failure_cycle,
        "baseline_departure_lead_cycles": baseline_departure_lead,
        "confirmed_instability_lead_cycles": confirmed_instability_lead,
        "actionable_lead_cycles": actionable_lead,
        "departure_type": departure_type,
        "departure_confidence": departure_confidence,
        "departure_regime": departure_regime,
        "departure_urgency": departure_urgency,
        "drift_at_departure": drift_at_departure,
        "confirmed_regime": confirmed_regime,
        "confirmed_urgency": confirmed_urgency,
        "drift_at_confirmed": drift_at_confirmed,
        "actionable_regime": actionable_regime,
        "actionable_urgency": actionable_urgency,
        "drift_at_actionable": drift_at_actionable,
        "trajectory": trajectory,
    }


def save_outputs(results, rul):
    drift_norm = normalize(results["drift"])
    drift_smooth = smooth(drift_norm, window=35)

    out_csv = OUT_DIR / "pronostia_decision_trajectory_demo_run.csv"
    out_png = OUT_DIR / "pronostia_decision_trajectory_demo.png"

    trajectory = results["trajectory"]

    np.savetxt(
        out_csv,
        np.column_stack(
            [
                results["cycles"],
                rul,
                results["drift"],
                results["instability"],
                drift_norm,
                drift_smooth,
            ]
        ),
        delimiter=",",
        header="cycle,rul,structural_drift,instability_score,drift_norm,drift_smooth",
        comments="",
    )

    plt.figure(figsize=(12, 6))
    plt.plot(results["cycles"], drift_smooth, label="Structural drift score")

    if results["baseline_finalized_cycle"] is not None:
        plt.axvline(
            results["baseline_finalized_cycle"],
            linestyle=":",
            label="Baseline finalized",
        )

    if results["baseline_departure_cycle"] is not None:
        plt.axvline(
            results["baseline_departure_cycle"],
            linestyle="-.",
            label=(
                f"Baseline departure, {results['departure_confidence']} confidence, "
                f"{results['baseline_departure_lead_cycles']} cycles before endpoint"
            ),
        )

    if results["confirmed_instability_cycle"] is not None:
        plt.axvline(
            results["confirmed_instability_cycle"],
            linestyle="-",
            label=(
                f"Confirmed instability, "
                f"{results['confirmed_instability_lead_cycles']} cycles before endpoint"
            ),
        )

    if results["actionable_cycle"] is not None:
        plt.axvline(
            results["actionable_cycle"],
            linestyle=":",
            label=(
                f"Actionable point, "
                f"{results['actionable_lead_cycles']} cycles before endpoint"
            ),
        )

    if trajectory["estimated_failure_cycle"] is not None:
        plt.axvline(
            trajectory["estimated_failure_cycle"],
            linestyle="--",
            label=f"Estimated endpoint, confidence {trajectory['confidence']}",
        )

    plt.axvline(
        results["failure_cycle"],
        linestyle="--",
        label="Actual failure endpoint",
    )

    plt.title("PRONOSTIA Demo: Structural Departure, Actionability, Trajectory")
    plt.xlabel("Cycle")
    plt.ylabel("Normalized structural drift")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)

    print("Saved CSV:", out_csv)
    print("Saved plot:", out_png)


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

    trajectory = results["trajectory"]

    print()
    print("RESULT")
    print("detected:", results["detected"])
    print("baseline_finalized_cycle:", results["baseline_finalized_cycle"])
    print("baseline_departure_cycle:", results["baseline_departure_cycle"])
    print("departure_confidence:", results["departure_confidence"])
    print("confirmed_instability_cycle:", results["confirmed_instability_cycle"])
    print("actionable_cycle:", results["actionable_cycle"])
    print("failure_cycle:", results["failure_cycle"])
    print("baseline_departure_lead_cycles:", results["baseline_departure_lead_cycles"])
    print("confirmed_instability_lead_cycles:", results["confirmed_instability_lead_cycles"])
    print("actionable_lead_cycles:", results["actionable_lead_cycles"])
    print("departure_type:", results["departure_type"])
    print("departure_regime:", results["departure_regime"])
    print("departure_urgency:", results["departure_urgency"])
    print("drift_at_departure:", results["drift_at_departure"])
    print("confirmed_regime:", results["confirmed_regime"])
    print("confirmed_urgency:", results["confirmed_urgency"])
    print("drift_at_confirmed:", results["drift_at_confirmed"])
    print("actionable_regime:", results["actionable_regime"])
    print("actionable_urgency:", results["actionable_urgency"])
    print("drift_at_actionable:", results["drift_at_actionable"])
    print("trajectory_trend:", trajectory["trend"])
    print("trajectory_mode:", trajectory["mode"])
    print("risk_band:", trajectory["risk_band"])
    print("time_to_failure:", trajectory["time_to_failure"])
    print("estimated_failure_cycle:", trajectory["estimated_failure_cycle"])
    print("failure_confidence:", trajectory["confidence"])
    print("trajectory_velocity:", trajectory["velocity"])
    print("trajectory_acceleration:", trajectory["acceleration"])

    save_outputs(results, rul)

    print("Done.")


if __name__ == "__main__":
    main()