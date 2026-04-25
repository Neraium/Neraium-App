import time
from pathlib import Path
import pandas as pd
from neraium_core.alignment import StructuralEngine

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASET = "FD001"   # change to FD002 / FD003 / FD004 after
PATH = DATA_DIR / f"train_{DATASET}.txt"

print("STARTING...", flush=True)
print("DATASET:", DATASET, flush=True)
print("PATH:", PATH, flush=True)

if not PATH.exists():
    raise FileNotFoundError(f"Missing {PATH}")

print("Loading file...", flush=True)
df = pd.read_csv(PATH, sep=r"\s+", header=None, engine="python")
df = df.dropna(axis=1).copy()

n_cols = df.shape[1]
sensor_count = n_cols - 5
df.columns = ["unit", "cycle", "os1", "os2", "os3"] + [f"s{i}" for i in range(1, sensor_count + 1)]

units = sorted(df["unit"].unique())
print("Rows loaded:", len(df), flush=True)
print("Units loaded:", len(units), flush=True)

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    drift_smoothing_window=25,
    watch_quantile=0.65,
    alert_quantile=0.85,
    watch_persistence=5,
    alert_persistence=3,
    fast_trigger_multiplier=1.25,
    alert_latch_enabled=True,
    unlatch_ratio=0.75,
)

results = []
t0 = time.time()

for idx, unit in enumerate(units, start=1):
    unit_df = df[df["unit"] == unit].sort_values("cycle")

    first_watch = None
    first_alert = None
    last_cycle = int(unit_df["cycle"].max())

    for row in unit_df.itertuples(index=False):
        sensor_values = {
            "os1": float(row.os1),
            "os2": float(row.os2),
            "os3": float(row.os3),
        }
        for i in range(1, sensor_count + 1):
            sensor_values[f"s{i}"] = float(getattr(row, f"s{i}"))

        frame = {
            "timestamp": float(row.cycle),
            "site_id": DATASET,
            "asset_id": f"{DATASET}_unit_{int(row.unit)}",
            "sensor_values": sensor_values,
        }

        out = engine.process_frame(frame)
        state = out.get("policy_state", out.get("state"))
        watch = bool(out.get("policy_watch", False)) or state == "WATCH"
        alert = bool(out.get("policy_alert", False)) or state == "ALERT"

        if first_watch is None and watch:
            first_watch = int(row.cycle)
        if first_alert is None and alert:
            first_alert = int(row.cycle)

    results.append({
        "dataset": DATASET,
        "unit": int(unit),
        "last_cycle": last_cycle,
        "first_watch_cycle": first_watch,
        "first_alert_cycle": first_alert,
        "has_watch": first_watch is not None,
        "has_alert": first_alert is not None,
    })

    elapsed = time.time() - t0
    alerts_so_far = sum(r["has_alert"] for r in results)
    print(
        f"{DATASET} unit {idx}/{len(units)} | alerts {alerts_so_far} | elapsed {elapsed:.1f}s",
        flush=True
    )

out_df = pd.DataFrame(results)
out_file = Path(f"{DATASET}_one_visible_summary.csv")
out_df.to_csv(out_file, index=False)

print("\nDONE", flush=True)
print("watch coverage:", round(float(out_df["has_watch"].mean()), 4), flush=True)
print("alert coverage:", round(float(out_df["has_alert"].mean()), 4), flush=True)
print("misses:", int((~out_df["has_alert"]).sum()), flush=True)
print("saved ->", out_file, flush=True)
