import os
import time
import pandas as pd
from pathlib import Path
from neraium_core.alignment import StructuralEngine

# FAST MODE
os.environ["NERAIUM_INCREMENTAL"] = "1"
os.environ["NERAIUM_TRANSITION_AWARE"] = "0"
os.environ["NERAIUM_CAUSAL_INTELLIGENCE"] = "0"
os.environ["NERAIUM_CAUSAL_ROOT_CAUSE_CHAINS"] = "0"

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASET = "FD004"
OUT_FILE = Path("FD004_fast_results.csv")

print("RUNNING FAST FD004", flush=True)
print("input:", DATA_DIR / f"test_{DATASET}.txt", flush=True)
print("output:", OUT_FILE, flush=True)

df = pd.read_csv(DATA_DIR / f"test_{DATASET}.txt", sep=r"\s+", header=None)
df.columns = ["unit", "cycle"] + [f"os{i}" for i in range(1,4)] + [f"s{i}" for i in range(1,22)]

engine = StructuralEngine(
    baseline_window=10,
    recent_window=5,
)

rows = []
global_t = 0.0
t0 = time.time()

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

    rows.append({
        "unit": int(row["unit"]),
        "cycle": int(row["cycle"]),
        "state": out.get("state"),
        "structural_drift_score": out.get("structural_drift_score"),
        "latest_instability": out.get("latest_instability"),
        "engine_ready": out.get("engine_ready"),
    })

    global_t += 1.0

    if i % 25 == 0:
        elapsed = time.time() - t0
        print(f"processed {i+1}/{len(df)} rows | elapsed={elapsed:.1f}s", flush=True)

pd.DataFrame(rows).to_csv(OUT_FILE, index=False)

print("DONE ->", OUT_FILE, flush=True)
