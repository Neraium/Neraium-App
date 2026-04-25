import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from run_engine import StructuralEngine

# -----------------------------
# PATH (already correct for you)
# -----------------------------
IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")

print("IMS DIR:", IMS_DIR)
print("exists:", IMS_DIR.exists())

files = sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith("._")])
print("total files:", len(files))

# -----------------------------
# USE MORE DATA (IMPORTANT)
# -----------------------------
files = files[:1000]   # 🔥 increase to full later
print("files used:", len(files))

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
t0 = time.time()
global_t = 0.0

def safe_peakiness(x):
    rms = np.sqrt(np.mean(x**2)) if len(x) else 0
    return np.max(np.abs(x)) / rms if rms > 1e-12 else 0

# -----------------------------
# RUN ENGINE
# -----------------------------
for idx, path in enumerate(files, start=1):
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    except:
        continue

    if df.empty:
        continue

    sensor_values = {}

    for col in df.columns:
        x = pd.to_numeric(df[col], errors="coerce").dropna().values
        if len(x) == 0:
            continue

        sensor_values[f"ch{col+1}_rms"] = float(np.sqrt(np.mean(x**2)))
        sensor_values[f"ch{col+1}_std"] = float(np.std(x))
        sensor_values[f"ch{col+1}_peak"] = float(safe_peakiness(x))

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
        "file_index": idx,
        "state": out.get("state"),
        "drift": out.get("structural_drift_score"),
    })

    global_t += 1.0

    if idx % 50 == 0:
        print(f"processed {idx}/{len(files)}")

df = pd.DataFrame(rows)
df.to_csv("IMS_full_results.csv", index=False)

print("\nDONE. rows:", len(df))
print("elapsed:", round(time.time() - t0, 1), "seconds")

# -----------------------------
# SMOOTH DRIFT (important)
# -----------------------------
df["drift_smooth"] = df["drift"].rolling(10, min_periods=1).mean()

# -----------------------------
# STATE → NUMERIC
# -----------------------------
state_map = {"STABLE": 0, "WATCH": 1, "ALERT": 2}
df["state_num"] = df["state"].map(state_map)

# -----------------------------
# COLOR MAP
# -----------------------------
colors = df["state"].map({
    "STABLE": "green",
    "WATCH": "orange",
    "ALERT": "red"
})

# -----------------------------
# PLOT 1: SMOOTH DRIFT
# -----------------------------
plt.figure(figsize=(12, 6))
plt.plot(df["file_index"], df["drift_smooth"])
plt.title("IMS Drift (Smoothed)")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.tight_layout()
plt.savefig("ims_drift_smooth.png", dpi=200)
plt.show()

# -----------------------------
# PLOT 2: STATE OVERLAY
# -----------------------------
plt.figure(figsize=(12, 6))
plt.scatter(df["file_index"], df["drift"], c=colors, s=10)
plt.plot(df["file_index"], df["drift_smooth"], linewidth=2)

plt.title("IMS Drift + State Overlay")
plt.xlabel("Time")
plt.ylabel("Drift Score")

plt.tight_layout()
plt.savefig("ims_state_overlay.png", dpi=200)
plt.show()

# -----------------------------
# PLOT 3: STATE TIMELINE
# -----------------------------
plt.figure(figsize=(12, 4))
plt.plot(df["file_index"], df["state_num"])
plt.yticks([0,1,2], ["STABLE","WATCH","ALERT"])
plt.title("IMS State Transitions")
plt.tight_layout()
plt.savefig("ims_state_timeline.png", dpi=200)
plt.show()

print("\nSaved:")
print(" ims_drift_smooth.png")
print(" ims_state_overlay.png")
print(" ims_state_timeline.png")
