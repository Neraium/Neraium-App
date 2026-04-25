import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from run_engine import StructuralEngine

IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")

all_files = sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith("._")])
files = all_files

print("IMS_DIR:", IMS_DIR, flush=True)
print("exists:", IMS_DIR.exists(), flush=True)
print("FILES USED FOR THIS RUN:", len(files), flush=True)

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
global_t = 0.0
t0 = time.time()

def safe_peak(x: np.ndarray) -> float:
    rms = np.sqrt(np.mean(x**2)) if len(x) else 0.0
    return float(np.max(np.abs(x)) / rms) if rms > 1e-12 else 0.0

for i, path in enumerate(files, start=1):
    try:
        raw = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    except Exception as e:
        print(f"skip read error: {path.name} -> {e}", flush=True)
        continue

    if raw.empty:
        continue

    sensor_values = {}

    for c in raw.columns:
        x = pd.to_numeric(raw[c], errors="coerce").dropna().to_numpy(dtype=float)
        if len(x) == 0:
            continue

        sensor_values[f"ch{c+1}_std"] = float(np.std(x))
        sensor_values[f"ch{c+1}_rms"] = float(np.sqrt(np.mean(x**2)))
        sensor_values[f"ch{c+1}_peak"] = safe_peak(x)

    if not sensor_values:
        continue

    frame = {
        "timestamp": global_t,
        "site_id": "ims",
        "asset_id": "bearing",
        "sensor_values": sensor_values,
    }

    out = engine.process_frame(frame)

    rows.append({
        "t": i,
        "file_name": path.name,
        "raw_state": out.get("state"),
        "drift": float(out.get("structural_drift_score", 0.0) or 0.0),
    })

    global_t += 1.0

    if i % 50 == 0 or i == len(files):
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0.0
        print(f"processed {i}/{len(files)} files | {rate:.1f} files/sec | {elapsed:.1f}s", flush=True)

df = pd.DataFrame(rows)
if df.empty:
    raise RuntimeError("No IMS rows were processed")

# Smooth drift
df["drift_smooth"] = df["drift"].rolling(25, min_periods=1).mean()

# Thresholds
watch_threshold = float(df["drift_smooth"].quantile(0.75))
alert_threshold = float(df["drift_smooth"].quantile(0.92))

# Production-style state logic
state = []
watch_counter = 0
alert_counter = 0
alert_latched = False

for v in df["drift_smooth"]:
    if v > alert_threshold:
        alert_counter += 1
    else:
        alert_counter = max(0, alert_counter - 1)

    if v > watch_threshold:
        watch_counter += 1
    else:
        watch_counter = max(0, watch_counter - 1)

    if alert_counter >= 8:
        alert_latched = True

    if alert_latched and v < (watch_threshold * 0.75):
        alert_latched = False
        alert_counter = 0

    if alert_latched:
        s = "ALERT"
    elif watch_counter >= 5:
        s = "WATCH"
    else:
        s = "STABLE"

    state.append(s)

df["state"] = state
df["state_num"] = df["state"].map({"STABLE": 0, "WATCH": 1, "ALERT": 2})

# Save CSV
df.to_csv("IMS_production_results_full.csv", index=False)

# ---------- EXTRA PRINTS ----------
print("\n" + "=" * 70, flush=True)
print("IMS RUN SUMMARY", flush=True)
print("=" * 70, flush=True)

print("watch_threshold =", round(watch_threshold, 4), flush=True)
print("alert_threshold =", round(alert_threshold, 4), flush=True)

state_counts = df["state"].value_counts(dropna=False)
print("\nstate counts:", flush=True)
print(state_counts.to_string(), flush=True)

state_pct = (df["state"].value_counts(normalize=True, dropna=False) * 100).round(2)
print("\nstate percentages:", flush=True)
print(state_pct.to_string(), flush=True)

first_watch = df.loc[df["state"] == "WATCH", "t"].min() if (df["state"] == "WATCH").any() else None
first_alert = df.loc[df["state"] == "ALERT", "t"].min() if (df["state"] == "ALERT").any() else None

print("\nfirst WATCH at t =", first_watch, flush=True)
print("first ALERT at t =", first_alert, flush=True)

peak_idx = df["drift_smooth"].idxmax()
peak_row = df.loc[peak_idx]
print("\npeak drift_smooth =", round(float(peak_row['drift_smooth']), 4), flush=True)
print("peak at t =", int(peak_row["t"]), flush=True)
print("peak file =", peak_row["file_name"], flush=True)

final_row = df.iloc[-1]
print("\nfinal state =", final_row["state"], flush=True)
print("final drift_smooth =", round(float(final_row["drift_smooth"]), 4), flush=True)
print("final file =", final_row["file_name"], flush=True)

top10 = df.nlargest(10, "drift_smooth")[["t", "file_name", "drift", "drift_smooth", "state"]]
print("\nTop 10 highest-drift files:", flush=True)
print(top10.to_string(index=False), flush=True)

print("\nPhase summary:", flush=True)
print(" baseline ends around t = 24", flush=True)
print(f" watch onset            = {first_watch}", flush=True)
print(f" alert onset            = {first_alert}", flush=True)
print(f" max instability point  = {int(peak_row['t'])}", flush=True)

# ---------- PLOTS ----------
plt.figure(figsize=(12, 6))
plt.plot(df["t"], df["drift_smooth"])
plt.axhline(watch_threshold, linestyle="--", label="WATCH threshold")
plt.axhline(alert_threshold, linestyle="--", label="ALERT threshold")
plt.title("IMS Drift (Production Smoothed)")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.legend()
plt.tight_layout()
plt.savefig("ims_prod_full_drift.png", dpi=200)
plt.show()

colors = df["state"].map({
    "STABLE": "green",
    "WATCH": "orange",
    "ALERT": "red",
})

plt.figure(figsize=(12, 6))
plt.scatter(df["t"], df["drift_smooth"], c=colors, s=10)
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift + Stable States")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.tight_layout()
plt.savefig("ims_prod_full_overlay.png", dpi=200)
plt.show()

plt.figure(figsize=(12, 4))
plt.plot(df["t"], df["state_num"])
plt.yticks([0, 1, 2], ["STABLE", "WATCH", "ALERT"])
plt.title("IMS Clean State Transitions")
plt.xlabel("Time")
plt.ylabel("State")
plt.tight_layout()
plt.savefig("ims_prod_full_states.png", dpi=200)
plt.show()

elapsed = time.time() - t0
print("\nSaved:", flush=True)
print(" - IMS_production_results_full.csv", flush=True)
print(" - ims_prod_full_drift.png", flush=True)
print(" - ims_prod_full_overlay.png", flush=True)
print(" - ims_prod_full_states.png", flush=True)
print("\nTotal elapsed:", round(elapsed, 1), "seconds", flush=True)
