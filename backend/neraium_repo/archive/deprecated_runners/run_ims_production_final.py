import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from run_engine import StructuralEngine

IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")

files = sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith("._")])

print("IMS_DIR:", IMS_DIR, flush=True)
print("FILES USED:", len(files), flush=True)

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
global_t = 0.0
t0 = time.time()

def safe_peak(x):
    rms = np.sqrt(np.mean(x**2)) if len(x) else 0.0
    return np.max(np.abs(x)) / rms if rms > 1e-12 else 0.0

# -----------------------------
# RUN ENGINE
# -----------------------------
for i, path in enumerate(files, start=1):
    try:
        raw = pd.read_csv(path, sep=r"\s+", header=None)
    except:
        continue

    sensor = {}
    for c in raw.columns:
        x = pd.to_numeric(raw[c], errors="coerce").dropna().values
        if len(x) == 0:
            continue

        sensor[f"c{c}"] = float(np.std(x))

    if not sensor:
        continue

    frame = {
        "timestamp": global_t,
        "site_id": "ims",
        "asset_id": "bearing",
        "sensor_values": sensor,
    }

    out = engine.process_frame(frame)

    rows.append({
        "t": i,
        "file": path.name,
        "drift": float(out.get("structural_drift_score", 0)),
    })

    global_t += 1

    if i % 50 == 0:
        print(f"processed {i}/{len(files)}", flush=True)

df = pd.DataFrame(rows)

# -----------------------------
# SMOOTH
# -----------------------------
df["drift_smooth"] = df["drift"].rolling(25, min_periods=1).mean()

# -----------------------------
# THRESHOLDS
# -----------------------------
watch_threshold = df["drift_smooth"].quantile(0.75)
alert_threshold = df["drift_smooth"].quantile(0.92)

# -----------------------------
# STATE LOGIC
# -----------------------------
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

# -----------------------------
# SUMMARY METRICS
# -----------------------------
first_watch = df.loc[df["state"] == "WATCH", "t"].min()
first_alert = df.loc[df["state"] == "ALERT", "t"].min()

peak_idx = df["drift_smooth"].idxmax()
peak_row = df.loc[peak_idx]

print("\n" + "="*60)
print("SUMMARY")
print("="*60)

print("watch_threshold =", round(watch_threshold, 4))
print("alert_threshold =", round(alert_threshold, 4))

print("\nSTATE COUNTS")
print(df["state"].value_counts())

print("\nFIRST WATCH:", first_watch)
print("FIRST ALERT:", first_alert)

print("\nPEAK DRIFT:", round(peak_row["drift_smooth"], 2))
print("PEAK AT t =", int(peak_row["t"]))
print("PEAK FILE =", peak_row["file"])

print("\nLEAD TIME")
if first_watch and first_alert:
    print("watch_to_alert =", first_alert - first_watch)
else:
    print("watch_to_alert = None")

if first_alert:
    print("alert_to_peak =", int(peak_row["t"]) - first_alert)
else:
    print("alert_to_peak = None")

# -----------------------------
# PLOTS
# -----------------------------
colors = df["state"].map({
    "STABLE": "green",
    "WATCH": "orange",
    "ALERT": "red"
})

plt.figure(figsize=(12,6))
plt.plot(df["t"], df["drift_smooth"])
plt.axhline(watch_threshold, linestyle="--")
plt.axhline(alert_threshold, linestyle="--")
plt.title("IMS Drift (Final)")
plt.savefig("ims_final_drift.png", dpi=200)
plt.show()

plt.figure(figsize=(12,6))
plt.scatter(df["t"], df["drift_smooth"], c=colors, s=10)
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift + States (Final)")
plt.savefig("ims_final_overlay.png", dpi=200)
plt.show()

state_map = {"STABLE":0,"WATCH":1,"ALERT":2}
plt.figure(figsize=(12,4))
plt.plot(df["t"], df["state"].map(state_map))
plt.yticks([0,1,2],["STABLE","WATCH","ALERT"])
plt.title("IMS State Transitions (Final)")
plt.savefig("ims_final_states.png", dpi=200)
plt.show()

print("\nSaved charts + CSV")
