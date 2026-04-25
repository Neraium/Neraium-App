import pandas as pd
from pathlib import Path
from neraium_core.alignment import StructuralEngine

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")

DATASETS = ["FD001", "FD002", "FD003", "FD004"]

def load_dataset(name):
    path = DATA_DIR / f"train_{name}.txt"
    df = pd.read_csv(path, sep=r"\s+", header=None)
    df = df.dropna(axis=1)

    cols = ["unit", "cycle"] + [f"s{i}" for i in range(1, df.shape[1]-1)]
    df.columns = cols
    return df

def run_dataset(name):
    print(f"\n=== Running {name} ===")

    df = load_dataset(name)

    engine = StructuralEngine(
        baseline_window=50,
        recent_window=12,
        drift_smoothing_window=10,
        watch_quantile=0.90,
        alert_quantile=0.98,
        watch_persistence=3,
        alert_persistence=2,
        alert_latch_enabled=True,
        unlatch_ratio=0.8,
    )

    results = []

    for _, row in df.iterrows():
        frame = {
            "timestamp": float(row["cycle"]),
            "site_id": name,
            "asset_id": int(row["unit"]),
            "sensor_values": {
                f"s{i}": float(row[f"s{i}"])
                for i in range(1, len(row)-1)
                if f"s{i}" in row
            },
        }

        out = engine.process_frame(frame)

        results.append({
            "unit": int(row["unit"]),
            "cycle": int(row["cycle"]),
            "state": out.get("state"),
            "alert": out.get("policy_alert", False),
        })

    res = pd.DataFrame(results)

    # collapse to first alert per unit
    alert_cycles = (
        res[res["alert"]]
        .groupby("unit")["cycle"]
        .min()
    )

    last_cycles = res.groupby("unit")["cycle"].max()

    summary = {
        "dataset": name,
        "units": len(last_cycles),
        "alert_coverage": alert_cycles.notna().mean(),
        "mean_alert_cycle": alert_cycles.mean(),
        "median_alert_cycle": alert_cycles.median(),
        "misses": (~alert_cycles.notna()).sum(),
    }

    return summary

all_results = []

for ds in DATASETS:
    try:
        summary = run_dataset(ds)
        all_results.append(summary)
    except Exception as e:
        print(f"ERROR on {ds}: {e}")

df = pd.DataFrame(all_results)

print("\n=== CMAPSS SUITE RESULTS ===")
print(df.to_string(index=False))

df.to_csv("cmapss_suite_results.csv", index=False)
print("\nSaved: cmapss_suite_results.csv")
