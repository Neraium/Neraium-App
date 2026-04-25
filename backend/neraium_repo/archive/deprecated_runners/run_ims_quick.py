import time
import numpy as np
import pandas as pd
from pathlib import Path
from run_engine import StructuralEngine

IMS_DIR = Path(r"C:\Users\Owner\Downloads\IMS-DATASET-main\IMS-DATASET-main\data")
OUT_FILE = Path("IMS_quick_results.csv")

print("=" * 60, flush=True)
print("RUNNING IMS QUICK TEST", flush=True)
print("=" * 60, flush=True)
print("input dir:", IMS_DIR, flush=True)
print("exists:", IMS_DIR.exists(), flush=True)

if not IMS_DIR.exists():
    raise FileNotFoundError(IMS_DIR)

files = sorted([p for p in IMS_DIR.iterdir() if p.is_file() and not p.name.startswith("._")])

print("files found:", len(files), flush=True)
if not files:
    raise RuntimeError("No IMS files found")

# quick smoke test
files = files[:200]
print("files used for quick test:", len(files), flush=True)

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
t0 = time.time()
global_t = 0.0

def safe_peakiness(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    rms = float(np.sqrt(np.mean(x**2))) if len(x) else 0.0
    if rms <= 1e-12:
        return 0.0
    return float(np.max(np.abs(x)) / rms)

for idx, path in enumerate(files, start=1):
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    except Exception as e:
        print(f"skip read error: {path.name} -> {e}", flush=True)
        continue

    if df.empty:
        continue

    sensor_values = {}

    for col in df.columns:
        x = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=float)
        if len(x) == 0:
            continue

        sensor_values[f"ch{col+1}_rms"] = float(np.sqrt(np.mean(x**2)))
        sensor_values[f"ch{col+1}_std"] = float(np.std(x))
        sensor_values[f"ch{col+1}_peakiness"] = safe_peakiness(x)

    if not sensor_values:
        continue

    frame = {
        "timestamp": global_t,
        "site_id": "ims",
        "asset_id": "bearing_rig",
        "sensor_values": sensor_values,
    }

    out = engine.process_frame(frame)

    rows.append({
        "file_index": idx,
        "file_name": path.name,
        "state": out.get("state"),
        "drift_alert": out.get("drift_alert"),
        "structural_drift_score": out.get("structural_drift_score"),
        "relational_stability_score": out.get("relational_stability_score"),
        "system_health": out.get("system_health"),
        "lead_time_hours": out.get("lead_time_hours"),
        "lead_time_confidence": out.get("lead_time_confidence"),
        "drift_velocity": out.get("drift_velocity"),
        "latest_instability": out.get("latest_instability"),
        "confidence_score": out.get("confidence_score"),
        "interpreted_state": out.get("interpreted_state"),
        "regime_name": out.get("regime_name"),
        "engine_ready": out.get("engine_ready"),
    })

    global_t += 1.0

    if idx % 25 == 0:
        elapsed = time.time() - t0
        rate = idx / elapsed if elapsed > 0 else 0.0
        print(f"processed {idx}/{len(files)} files | {rate:.1f} files/sec | {elapsed:.1f}s", flush=True)

out_df = pd.DataFrame(rows)
out_df.to_csv(OUT_FILE, index=False)

elapsed = time.time() - t0
print("\nDONE ->", OUT_FILE, flush=True)
print("rows written:", len(out_df), flush=True)
print("elapsed:", round(elapsed, 1), "seconds", flush=True)

if not out_df.empty:
    print("\nstate counts:", flush=True)
    print(out_df["state"].value_counts(dropna=False).to_string(), flush=True)
