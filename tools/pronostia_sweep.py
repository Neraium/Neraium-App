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
    print(f"\nProcessing FD{fd}...")

    ds = FemtoReader(fd=fd)
    ds.prepare_data()
    X, y = ds.load_split("dev")

    for run_index in range(len(X)):
        raw_run = X[run_index]
        rul = y[run_index]

        try:
            failure_cycle = int(np.where(rul <= 1)[0][0])
        except Exception:
            failure_cycle = len(rul)

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

            rows.append({
                "fd": fd,
                "run_index": run_index,
                "cycles": len(raw_run),
                "failure_cycle": failure_cycle,
                "detected": result["detected"],
                "baseline_finalized": result["baseline_finalized_cycle"],
                "baseline_departure": result["baseline_departure_cycle"],
                "confirmed_instability": result["confirmed_instability_cycle"],
                "actionable": result["actionable_cycle"],
                "departure_lead": result["baseline_departure_lead_cycles"],
                "confirmed_lead": result["confirmed_instability_lead_cycles"],
                "actionable_lead": result["actionable_lead_cycles"],
                "departure_type": result["departure_type"],
                "risk_band": traj["risk_band"],
                "trajectory_mode": traj["mode"],
                "velocity": traj["velocity"],
                "acceleration": traj["acceleration"],
                "confidence": traj["confidence"],
                "error": "",
            })

        except Exception as e:
            rows.append({
                "fd": fd,
                "run_index": run_index,
                "cycles": len(raw_run),
                "failure_cycle": failure_cycle,
                "detected": False,
                "baseline_finalized": None,
                "baseline_departure": None,
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
                "error": repr(e),
            })

df = pd.DataFrame(rows)

out = OUT_DIR / "pronostia_sweep_results.csv"
df.to_csv(out, index=False)

print("\nFULL RESULTS\n")
print(df.to_string(index=False))

# =========================
# IMPROVED SUMMARY SECTION
# =========================

print()
print("SUMMARY")
print("runs:", len(df))

# Coverage
baseline_cov = df["baseline_departure"].notna().mean()
confirmed_cov = df["confirmed_instability"].notna().mean()
actionable_cov = df["actionable"].notna().mean()

print("baseline_departure_coverage_pct:", round(100 * baseline_cov, 2))
print("confirmed_instability_coverage_pct:", round(100 * confirmed_cov, 2))
print("actionable_coverage_pct:", round(100 * actionable_cov, 2))

# Lead stats
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

# Early detection sanity check
early_flags = df[df["baseline_departure"] < 100]
print("early_detection_count_under_100_cycles:", len(early_flags))

# Missing stages
missing_confirmed = df[df["confirmed_instability"].isna()]
missing_actionable = df[df["actionable"].isna()]

print("missing_confirmed_instability_count:", len(missing_confirmed))
print("missing_actionable_count:", len(missing_actionable))

# Errors
errors = df[df["error"].astype(str) != ""]
print("errors:", len(errors))

# Debug problem runs
if len(missing_confirmed):
    print("\nRUNS MISSING CONFIRMED INSTABILITY\n")
    print(missing_confirmed[
        ["fd", "run_index", "cycles", "failure_cycle",
         "baseline_departure", "departure_lead"]
    ].to_string(index=False))

if len(missing_actionable):
    print("\nRUNS MISSING ACTIONABLE POINT\n")
    print(missing_actionable[
        ["fd", "run_index", "cycles", "failure_cycle",
         "baseline_departure", "confirmed_instability",
         "departure_lead"]
    ].to_string(index=False))

print("\nSaved:", out)