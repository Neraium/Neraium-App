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

for i, path in enumerate(files, start=1):
    try:
        raw = pd.read_csv(path, sep=r"\s+", header=None)
    except Exception:
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
        "file_name": path.name,
        "drift": float(out.get("structural_drift_score", 0.0) or 0.0),
    })

    global_t += 1.0

    if i % 50 == 0 or i == len(files):
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0.0
        print(f"processed {i}/{len(files)} | {rate:.1f} files/sec | {elapsed:.1f}s", flush=True)

df = pd.DataFrame(rows)
if df.empty:
    raise RuntimeError("No IMS rows were processed")

# ---------------------------------
# Smooth
# ---------------------------------
df["drift_smooth"] = df["drift"].rolling(25, min_periods=1).mean()

# ---------------------------------
# Thresholds
# ---------------------------------
watch_threshold = float(df["drift_smooth"].quantile(0.65))
alert_threshold = float(df["drift_smooth"].quantile(0.92))

# ---------------------------------
# State logic
# ---------------------------------
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

# ---------------------------------
# Summary metrics
# ---------------------------------
first_watch = df.loc[df["state"] == "WATCH", "t"].min() if (df["state"] == "WATCH").any() else None
first_alert = df.loc[df["state"] == "ALERT", "t"].min() if (df["state"] == "ALERT").any() else None

peak_idx = df["drift_smooth"].idxmax()
peak_row = df.loc[peak_idx]

df["drift_diff"] = df["drift_smooth"].diff()
accel_idx = df["drift_diff"].idxmax()
accel_row = df.loc[accel_idx]

# ---------------------------------
# Contiguous state segments
# ---------------------------------
segments = []
start = 0
current = df.loc[0, "state"]

for i in range(1, len(df)):
    s = df.loc[i, "state"]
    if s != current:
        segments.append({
            "state": current,
            "start_t": int(df.loc[start, "t"]),
            "end_t": int(df.loc[i - 1, "t"]),
            "duration": int(df.loc[i - 1, "t"] - df.loc[start, "t"] + 1),
        })
        start = i
        current = s

segments.append({
    "state": current,
    "start_t": int(df.loc[start, "t"]),
    "end_t": int(df.loc[len(df) - 1, "t"]),
    "duration": int(df.loc[len(df) - 1, "t"] - df.loc[start, "t"] + 1),
})

seg_df = pd.DataFrame(segments)

# ---------------------------------
# Save outputs
# ---------------------------------
df.to_csv("IMS_production_results_final.csv", index=False)
seg_df.to_csv("IMS_state_segments_final.csv", index=False)

# ---------------------------------
# Print summary
# ---------------------------------
print("\n" + "=" * 70, flush=True)
print("IMS FINAL SUMMARY", flush=True)
print("=" * 70, flush=True)

print("watch_threshold =", round(watch_threshold, 4), flush=True)
print("alert_threshold =", round(alert_threshold, 4), flush=True)

print("\nSTATE COUNTS", flush=True)
print(df["state"].value_counts(dropna=False).to_string(), flush=True)

print("\nSTATE PERCENTAGES", flush=True)
print((df["state"].value_counts(normalize=True, dropna=False) * 100).round(2).to_string(), flush=True)

print("\nFIRST WATCH:", first_watch, flush=True)
print("FIRST ALERT:", first_alert, flush=True)

print("\nPEAK DRIFT:", round(float(peak_row["drift_smooth"]), 2), flush=True)
print("PEAK AT t =", int(peak_row["t"]), flush=True)
print("PEAK FILE =", peak_row["file_name"], flush=True)

print("\nLEAD TIME", flush=True)
print("watch_to_alert =", (first_alert - first_watch) if first_watch is not None and first_alert is not None else None, flush=True)
print("alert_to_peak =", (int(peak_row["t"]) - first_alert) if first_alert is not None else None, flush=True)

print("\nMAX DRIFT ACCELERATION", flush=True)
print("t =", int(accel_row["t"]), flush=True)
print("file =", accel_row["file_name"], flush=True)
print("drift_smooth =", round(float(accel_row["drift_smooth"]), 4), flush=True)
print("delta =", round(float(accel_row["drift_diff"]), 4), flush=True)

print("\nCONTIGUOUS STATE SEGMENTS", flush=True)
print(seg_df.to_string(index=False), flush=True)

print("\nTOP 10 HIGHEST-DRIFT FILES", flush=True)
top10 = df.nlargest(10, "drift_smooth")[["t", "file_name", "drift", "drift_smooth", "state"]]
print(top10.to_string(index=False), flush=True)

# ---------------------------------
# Plots
# ---------------------------------
plt.figure(figsize=(12, 6))
plt.plot(df["t"], df["drift_smooth"])
plt.axhline(watch_threshold, linestyle="--", label="WATCH threshold")
plt.axhline(alert_threshold, linestyle="--", label="ALERT threshold")
plt.title("IMS Drift (Final Combined)")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.legend()
plt.tight_layout()
plt.savefig("ims_final_combined_drift.png", dpi=200)
plt.show()

colors = df["state"].map({
    "STABLE": "green",
    "WATCH": "orange",
    "ALERT": "red",
})

plt.figure(figsize=(12, 6))
plt.scatter(df["t"], df["drift_smooth"], c=colors, s=10)
plt.plot(df["t"], df["drift_smooth"])
plt.title("IMS Drift + States (Final Combined)")
plt.xlabel("Time")
plt.ylabel("Drift Score")
plt.tight_layout()
plt.savefig("ims_final_combined_overlay.png", dpi=200)
plt.show()

plt.figure(figsize=(12, 4))
plt.plot(df["t"], df["state_num"])
plt.yticks([0, 1, 2], ["STABLE", "WATCH", "ALERT"])
plt.title("IMS State Transitions (Final Combined)")
plt.xlabel("Time")
plt.ylabel("State")
plt.tight_layout()
plt.savefig("ims_final_combined_states.png", dpi=200)
plt.show()

elapsed = time.time() - t0
print("\nSAVED FILES", flush=True)
print(" - IMS_production_results_final.csv", flush=True)
print(" - IMS_state_segments_final.csv", flush=True)
print(" - ims_final_combined_drift.png", flush=True)
print(" - ims_final_combined_overlay.png", flush=True)
print(" - ims_final_combined_states.png", flush=True)
print("\nTOTAL ELAPSED:", round(elapsed, 1), "seconds", flush=True)
