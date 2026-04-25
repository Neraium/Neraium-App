import time
import pandas as pd
from pathlib import Path
from run_engine import StructuralEngine

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASET = "FD004"
OUT_FILE = Path("FD004_simple_results.csv")

print("=" * 60, flush=True)
print("RUNNING FD004 WITH SIMPLE ENGINE", flush=True)
print("=" * 60, flush=True)

file_path = DATA_DIR / f"test_{DATASET}.txt"
print("input:", file_path, flush=True)
print("exists:", file_path.exists(), flush=True)

if not file_path.exists():
    raise FileNotFoundError(file_path)

df = pd.read_csv(file_path, sep=r"\s+", header=None)
df.columns = ["unit", "cycle"] + [f"os{i}" for i in range(1, 4)] + [f"s{i}" for i in range(1, 22)]

print("rows:", len(df), flush=True)

engine = StructuralEngine(
    baseline_window=24,
    recent_window=8,
    max_frames=500,
)

rows = []
global_t = 0.0
t0 = time.time()
total = len(df)

for i, row in df.iterrows():
    frame = {
        "timestamp": global_t,
        "site_id": "nasa",
        "asset_id": f"engine_{int(row['unit'])}",
        "sensor_values": {
            **{f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)},
            **{f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)},
        },
    }

    out = engine.process_frame(frame)

    rows.append({
        "unit": int(row["unit"]),
        "cycle": int(row["cycle"]),
        "state": out.get("state"),
        "structural_drift_score": out.get("structural_drift_score"),
        "relational_stability_score": out.get("relational_stability_score"),
        "system_health": out.get("system_health"),
        "drift_alert": out.get("drift_alert"),
        "lead_time_hours": out.get("lead_time_hours"),
        "lead_time_confidence": out.get("lead_time_confidence"),
        "drift_velocity": out.get("drift_velocity"),
        "mahalanobis_score": out.get("mahalanobis_score"),
        "covariance_drift_score": out.get("covariance_drift_score"),
        "latest_instability": out.get("latest_instability"),
        "confidence_score": out.get("confidence_score"),
        "interpreted_state": out.get("interpreted_state"),
        "regime_name": out.get("regime_name"),
    })

    global_t += 1.0

    if i % 100 == 0:
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed if elapsed > 0 else 0.0
        print(f"processed {i+1}/{total} | {rate:.1f} rows/sec | {elapsed:.1f}s", flush=True)

out_df = pd.DataFrame(rows)
out_df.to_csv(OUT_FILE, index=False)

elapsed = time.time() - t0
print("\nDONE ->", OUT_FILE, flush=True)
print(f"total rows: {len(rows)} | elapsed: {elapsed:.1f}s", flush=True)
