import time
import pandas as pd
from pathlib import Path
from run_engine import StructuralEngine

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASET = "FD004"
OUT_FILE = Path("FD004_by_unit_results.csv")

print("=" * 70, flush=True)
print("FAST FD004 (BY UNIT)", flush=True)
print("=" * 70, flush=True)

file_path = DATA_DIR / f"test_{DATASET}.txt"
print("input:", file_path, flush=True)

df = pd.read_csv(file_path, sep=r"\s+", header=None)
df.columns = ["unit", "cycle"] + [f"os{i}" for i in range(1, 4)] + [f"s{i}" for i in range(1, 22)]
df = df.sort_values(["unit", "cycle"]).reset_index(drop=True)

units = sorted(df["unit"].unique())

print("total rows:", len(df), flush=True)
print("total units:", len(units), flush=True)

all_rows = []
t0 = time.time()

for u_idx, unit_id in enumerate(units, start=1):
    unit_df = df[df["unit"] == unit_id]

    print(f"\nUNIT {unit_id} ({u_idx}/{len(units)}) | rows={len(unit_df)}", flush=True)

    # 🔥 NEW ENGINE PER UNIT (KEY FIX)
    engine = StructuralEngine(
        baseline_window=24,
        recent_window=8,
        max_frames=500,
    )

    global_t = 0.0

    for i, (_, row) in enumerate(unit_df.iterrows()):
        frame = {
            "timestamp": global_t,
            "site_id": "nasa",
            "asset_id": f"engine_{unit_id}",
            "sensor_values": {
                **{f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)},
                **{f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)},
            },
        }

        out = engine.process_frame(frame)

        all_rows.append({
            "unit": unit_id,
            "cycle": int(row["cycle"]),
            "state": out.get("state"),
            "drift_alert": out.get("drift_alert"),
            "structural_drift_score": out.get("structural_drift_score"),
            "lead_time_hours": out.get("lead_time_hours"),
            "lead_time_confidence": out.get("lead_time_confidence"),
            "system_health": out.get("system_health"),
        })

        global_t += 1.0

        if i % 50 == 0:
            print(f"  row {i+1}/{len(unit_df)}", flush=True)

elapsed = time.time() - t0

pd.DataFrame(all_rows).to_csv(OUT_FILE, index=False)

print("\nDONE", flush=True)
print("saved ->", OUT_FILE, flush=True)
print("elapsed:", round(elapsed, 1), "seconds", flush=True)
