from pathlib import Path
import sys
import numpy as np
import pandas as pd
from rul_datasets import FemtoReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pronostia_runner import run_engine

OUT_DIR = Path("test_reports/pronostia_demo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

rows = []

for fd in [1, 2, 3]:
    print(f"\nBenchmarking PRONOSTIA FD{fd}...")

    ds = FemtoReader(fd=fd)
    ds.prepare_data()
    X, y = ds.load_split("dev")

    for run_index in range(len(X)):
        raw_run = X[run_index]
        rul = y[run_index]

        try:
            failure_cycle = int(np.where(rul <= 1)[0][0])
        except Exception:
            failure_cycle = len(rul) - 1

        try:
            result = run_engine(
                raw_run=raw_run,
                failure_cycle=failure_cycle,
                baseline_window=50,
                recent_window=12,
                post_baseline_delay=40,
                persistence_required=4,
                adaptive_window=75,
                adaptive_z=2.5,
            )

            traj = result["trajectory"]

            baseline_departure = result["baseline_departure_cycle"]
            confirmed = result["confirmed_instability_cycle"]
            actionable = result["actionable_cycle"]

            departure_hit = baseline_departure is not None
            confirmed_hit = confirmed is not None
            actionable_hit = actionable is not None

            early_signal_class = "NONE"

            if baseline_departure is not None and baseline_departure < 100:
                if confirmed_hit or actionable_hit:
                    early_signal_class = "EARLY_VALIDATED"
                else:
                    early_signal_class = "EARLY_UNCONFIRMED"
            elif baseline_departure is not None:
                early_signal_class = "NORMAL"

            stage_score = 0

            if departure_hit:
                stage_score += 35
            if confirmed_hit:
                stage_score += 30
            if actionable_hit:
                stage_score += 25
            if traj["risk_band"] in ("elevated", "high"):
                stage_score += 10

            if early_signal_class == "EARLY_UNCONFIRMED":
                stage_score -= 10

            stage_score = max(0, min(100, stage_score))

            if actionable_hit:
                status = "ACTIONABLE"
            elif confirmed_hit:
                status = "CONFIRMED_ONLY"
            elif departure_hit:
                status = "DEPARTURE_ONLY"
            else:
                status = "MISSED"

            rows.append({
                "fd": fd,
                "run_index": run_index,
                "cycles": len(raw_run),
                "failure_cycle": failure_cycle,
                "status": status,
                "score": stage_score,
                "baseline_finalized": result["baseline_finalized_cycle"],
                "baseline_departure": baseline_departure,
                "departure_confidence": result.get("departure_confidence"),
                "confirmed_instability": confirmed,
                "actionable": actionable,
                "departure_lead": result["baseline_departure_lead_cycles"],
                "confirmed_lead": result["confirmed_instability_lead_cycles"],
                "actionable_lead": result["actionable_lead_cycles"],
                "departure_type": result["departure_type"],
                "risk_band": traj["risk_band"],
                "trajectory_mode": traj["mode"],
                "velocity": traj["velocity"],
                "acceleration": traj["acceleration"],
                "confidence": traj["confidence"],
                "early_signal_class": early_signal_class,
                "error": "",
            })

        except Exception as e:
            rows.append({
                "fd": fd,
                "run_index": run_index,
                "cycles": len(raw_run),
                "failure_cycle": failure_cycle,
                "status": "ERROR",
                "score": 0,
                "baseline_finalized": None,
                "baseline_departure": None,
                "departure_confidence": None,
                "confirmed_instability": None,
                "actionable": None,
                "departure_lead": None,
                "confirmed_lead": None,
                "actionable_lead": None,
                "departure_type": None,
                "risk_band": None,
                "trajectory_mode": None,
                "velocity": None,
                "acceleration": None,
                "confidence": None,
                "early_signal_class": "ERROR",
                "error": repr(e),
            })

df = pd.DataFrame(rows)

out_csv = OUT_DIR / "pronostia_benchmark_results.csv"
df.to_csv(out_csv, index=False)

print("\nBENCHMARK RESULTS\n")
print(df.to_string(index=False))

print("\nSCORECARD")
print("runs:", len(df))
print("errors:", int((df["status"] == "ERROR").sum()))
print("avg_score:", round(float(df["score"].mean()), 2))

print("baseline_departure_coverage_pct:", round(100 * df["baseline_departure"].notna().mean(), 2))
print("confirmed_instability_coverage_pct:", round(100 * df["confirmed_instability"].notna().mean(), 2))
print("actionable_coverage_pct:", round(100 * df["actionable"].notna().mean(), 2))

valid_dep = df.dropna(subset=["departure_lead"])
valid_conf = df.dropna(subset=["confirmed_lead"])
valid_act = df.dropna(subset=["actionable_lead"])

if len(valid_dep):
    print("median_departure_lead:", float(valid_dep["departure_lead"].median()))
    print("min_departure_lead:", float(valid_dep["departure_lead"].min()))
    print("max_departure_lead:", float(valid_dep["departure_lead"].max()))

if len(valid_conf):
    print("median_confirmed_lead:", float(valid_conf["confirmed_lead"].median()))
    print("min_confirmed_lead:", float(valid_conf["confirmed_lead"].min()))
    print("max_confirmed_lead:", float(valid_conf["confirmed_lead"].max()))

if len(valid_act):
    print("median_actionable_lead:", float(valid_act["actionable_lead"].median()))
    print("min_actionable_lead:", float(valid_act["actionable_lead"].min()))
    print("max_actionable_lead:", float(valid_act["actionable_lead"].max()))

print("early_signal_classes:")
print(df["early_signal_class"].value_counts(dropna=False).to_string())

print("\nSTATUS COUNTS")
print(df["status"].value_counts(dropna=False).to_string())

weak = df[df["status"].isin(["DEPARTURE_ONLY", "CONFIRMED_ONLY", "MISSED", "ERROR"])]
if len(weak):
    print("\nWEAK RUNS")
    print(weak[[
        "fd", "run_index", "cycles", "failure_cycle", "status", "score",
        "baseline_departure", "confirmed_instability", "actionable",
        "departure_lead", "early_signal_class", "error"
    ]].to_string(index=False))

print("\nSaved:", out_csv)