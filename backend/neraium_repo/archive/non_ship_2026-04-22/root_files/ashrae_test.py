import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from neraium_core.intelligence_stack import StructuralDriftDetector, DetectorConfig

df = pd.read_feather("data/ashrae_gep3/train.feather")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["building_id", "meter", "timestamp"])

grp = df.groupby(["building_id", "meter"])
df["delta_1"] = grp["meter_reading"].diff()
df["rolling_mean"] = grp["meter_reading"].transform(
    lambda x: x.rolling(24, min_periods=24).mean()
)

detector = StructuralDriftDetector(DetectorConfig())

tested = 0
valid = []
failed = []

groups = list(df.groupby(["building_id", "meter"]))
total_groups = len(groups)

for idx, ((b, m), g) in enumerate(groups, start=1):
    if idx % 50 == 0:
        print(f"Processed {idx}/{total_groups} groups...")

    unit = g[["meter_reading", "delta_1", "rolling_mean"]].dropna()

    if len(unit) < 500:
        continue

    if unit.std(numeric_only=True).mean() < 1e-6:
        continue

    unit = unit.replace([np.inf, -np.inf], np.nan).dropna()

    if len(unit) < 500:
        continue

    data = unit.to_numpy(dtype=float)
    tested += 1

    try:
        result = detector.process_unit(data)
        if result.warning_index is not None:
            ratio = result.warning_index / result.n_cycles
            valid.append((b, m, result.warning_index, result.n_cycles, ratio))
    except Exception as e:
        failed.append((b, m, str(e)))

print("\n=== RESULTS ===")
print("Units tested:", tested)
print("Valid warnings:", len(valid))
print("Failed units:", len(failed))

if valid:
    ratios = [r[4] for r in valid]
    print("Avg warning ratio:", sum(ratios) / len(ratios))
    print("Min/Max:", min(ratios), max(ratios))
    print("\nFirst 10 warnings:")
    for row in valid[:10]:
        print(row)
else:
    print("No warnings detected")

if failed:
    print("\nFirst 10 failures:")
    for row in failed[:10]:
        print(row)
