import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from run_engine import StructuralEngine

IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")

files = sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith("._")])
files = files[:1500]

print("IMS_DIR:", IMS_DIR, flush=True)
print("exists:", IMS_DIR.exists(), flush=True)
print("TOTAL FILES FOUND:", len(sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith('._')])), flush=True)
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

    if i % 50 == 0:
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0.0
        print(f"processed {i}/{len(files)} files | {rate:.1f} files/sec | {elapsed:.1f}s", flush=True)

df = pd.DataFrame(rows)
if df.empty:
    raise RuntimeError("No IMS rows were processed")

df["drift_smooth"] = df["drift"].rolling(25, min_periods=1).mean()

watch_threshold = float(df["drift_smooth"].quantile(0.75))
alert_threshold = float(df["drift_smooth"].quantile(0.92))

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

df.to_csv("IMS_production_results_v1500.csv", index=False)

plt.figure(figsize=(12, 6))
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift (Production Smoothed v1500)")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.tight_layout()
plt.savefig("ims_prod_v1500_drift.png", dpi=200)
plt.show()

colors = df["state"].map({
    "STABLE": "green",
    "WATCH": "orange",
    "ALERT": "red",
})

plt.figure(figsize=(12, 6))
plt.scatter(df["t"], df["drift_smooth"], c=colors, s=10)
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift + Stable States v1500")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.tight_layout()
plt.savefig("ims_prod_v1500_overlay.png", dpi=200)
plt.show()

plt.figure(figsize=(12, 4))
plt.plot(df["t"], df["state_num"])
plt.yticks([0, 1, 2], ["STABLE", "WATCH", "ALERT"])
plt.title("IMS Clean State Transitions v1500")
plt.xlabel("Time")
plt.ylabel("State")
plt.tight_layout()
plt.savefig("ims_prod_v1500_states.png", dpi=200)
plt.show()

print("\nthresholds:", flush=True)
print("watch_threshold =", round(watch_threshold, 4), flush=True)
print("alert_threshold =", round(alert_threshold, 4), flush=True)

print("\nstate counts:", flush=True)
print(df["state"].value_counts(dropna=False).to_string(), flush=True)

print("\nSaved:", flush=True)
print(" - IMS_production_results_v1500.csv", flush=True)
print(" - ims_prod_v1500_drift.png", flush=True)
print(" - ims_prod_v1500_overlay.png", flush=True)
print(" - ims_prod_v1500_states.png", flush=True)
