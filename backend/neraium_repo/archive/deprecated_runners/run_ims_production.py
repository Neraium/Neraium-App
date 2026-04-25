import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from run_engine import StructuralEngine

IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")

files = sorted([p for p in IMS_DIR.iterdir() if p.is_file()])
files = files[:1000]

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
global_t = 0

def safe_peak(x):
    rms = np.sqrt(np.mean(x**2)) if len(x) else 0
    return np.max(np.abs(x)) / rms if rms > 1e-12 else 0

# -----------------------------
# RUN ENGINE
# -----------------------------
for i, path in enumerate(files, 1):
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None)
    except:
        continue

    sensor = {}
    for c in df.columns:
        x = pd.to_numeric(df[c], errors="coerce").dropna().values
        if len(x) == 0:
            continue
        sensor[f"c{c}"] = float(np.std(x))  # faster + enough signal

    frame = {
        "timestamp": global_t,
        "site_id": "ims",
        "asset_id": "bearing",
        "sensor_values": sensor,
    }

    out = engine.process_frame(frame)

    rows.append({
        "t": i,
        "drift": out.get("structural_drift_score", 0),
    })

    global_t += 1

df = pd.DataFrame(rows)

# -----------------------------
# SMOOTH HARDER
# -----------------------------
df["drift_smooth"] = df["drift"].rolling(25, min_periods=1).mean()

# -----------------------------
# PERSISTENCE LOGIC
# -----------------------------
ALERT_THRESHOLD = df["drift_smooth"].quantile(0.92)
WATCH_THRESHOLD = df["drift_smooth"].quantile(0.75)

state = []
alert_counter = 0

for v in df["drift_smooth"]:
    if v > ALERT_THRESHOLD:
        alert_counter += 1
    else:
        alert_counter = 0

    if alert_counter >= 5:
        state.append("ALERT")
    elif v > WATCH_THRESHOLD:
        state.append("WATCH")
    else:
        state.append("STABLE")

df["state"] = state

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
plt.title("IMS Drift (Production Smoothed)")
plt.savefig("ims_prod_drift.png", dpi=200)
plt.show()

plt.figure(figsize=(12,6))
plt.scatter(df["t"], df["drift_smooth"], c=colors, s=8)
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift + Stable States")
plt.savefig("ims_prod_overlay.png", dpi=200)
plt.show()

state_map = {"STABLE":0,"WATCH":1,"ALERT":2}
plt.figure(figsize=(12,4))
plt.plot(df["t"], df["state"].map(state_map))
plt.yticks([0,1,2],["STABLE","WATCH","ALERT"])
plt.title("IMS Clean State Transitions")
plt.savefig("ims_prod_states.png", dpi=200)
plt.show()

print("\nSTATE COUNTS:")
print(df["state"].value_counts())
