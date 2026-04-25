import os
import time
import pandas as pd
from pathlib import Path
from neraium_core.alignment import StructuralEngine

# 🔥 PRODUCTION / FAST MODE
os.environ["NERAIUM_FAST_MODE"] = "1"
os.environ["NERAIUM_INCREMENTAL"] = "1"
os.environ["NERAIUM_TRANSITION_AWARE"] = "1"
os.environ["NERAIUM_CAUSAL_INTELLIGENCE"] = "0"
os.environ["NERAIUM_CAUSAL_ROOT_CAUSE_CHAINS"] = "0"

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASET = "FD004"
OUT_FILE = Path("FD004_fast_results.csv")

print("="*60, flush=True)
print("RUNNING FAST FD004 (PRODUCTION MODE)", flush=True)
print("="*60, flush=True)

df = pd.read_csv(DATA_DIR / f"test_{DATASET}.txt", sep=r"\s+", header=None)
df.columns = ["unit", "cycle"] + [f"os{i}" for i in range(1,4)] + [f"s{i}" for i in range(1,22)]

engine = StructuralEngine(
    baseline_window=10,   # 🔥 key change
    recent_window=5       # 🔥 key change
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
            **{f"os{i}": float(row[f"os{i}"]) for i in range(1,4)},
            **{f"s{i}": float(row[f"s{i}"]) for i in range(1,22)},
        },
    }

    out = engine.process_frame(frame)

    # 🔥 ONLY KEEP FAST FIELDS
    rows.append({
        "unit": int(row["unit"]),
        "cycle": int(row["cycle"]),
        "state": out.get("state"),
        "transition_state": out.get("transition_state"),
        "structural_drift_score": out.get("structural_drift_score"),
        "transition_pressure": out.get("transition_pressure"),
        "latest_instability": out.get("latest_instability"),
        "engine_ready": out.get("engine_ready"),
    })

    global_t += 1

    if i % 50 == 0:
        elapsed = time.time() - t0
        rate = (i+1)/elapsed if elapsed > 0 else 0
        print(f"processed {i+1}/{total} | {rate:.1f} rows/sec | {elapsed:.1f}s", flush=True)

pd.DataFrame(rows).to_csv(OUT_FILE, index=False)

print("\nDONE ->", OUT_FILE, flush=True)
