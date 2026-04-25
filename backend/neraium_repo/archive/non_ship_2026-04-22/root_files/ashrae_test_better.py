import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from neraium_core.intelligence_stack import StructuralDriftDetector, DetectorConfig

print("Loading data...")
train = pd.read_feather("data/ashrae_gep3/train.feather")
weather = pd.read_feather("data/ashrae_gep3/weather_train.feather")
meta = pd.read_feather("data/ashrae_gep3/building_metadata.feather")

print("Merging metadata...")
df = train.merge(
    meta[["building_id", "site_id"]],
    on="building_id",
    how="left"
)

print("Merging weather...")
df = df.merge(
    weather,
    on=["site_id", "timestamp"],
    how="left"
)

print("Preprocessing...")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values(["building_id", "meter", "timestamp"])

grp = df.groupby(["building_id", "meter"])

print("Building features...")
df["delta_1"] = grp["meter_reading"].diff()

df["rolling_mean"] = grp["meter_reading"].transform(
    lambda x: x.rolling(24, min_periods=24).mean()
)

df["rolling_std"] = grp["meter_reading"].transform(
    lambda x: x.rolling(24, min_periods=24).std()
)

df["rolling_max"] = grp["meter_reading"].transform(
    lambda x: x.rolling(24, min_periods=24).max()
)

df["rolling_min"] = grp["meter_reading"].transform(
    lambda x: x.rolling(24, min_periods=24).min()
)

df["range_24"] = df["rolling_max"] - df["rolling_min"]
df["deviation"] = df["meter_reading"] - df["rolling_mean"]
df["z_score"] = df["deviation"] / (df["rolling_std"] + 1e-6)

if "air_temperature" in df.columns:
    df["temp_delta"] = grp["air_temperature"].diff()
    df["energy_per_temp"] = df["meter_reading"] / (df["air_temperature"].abs() + 1e-3)
else:
    df["air_temperature"] = np.nan
    df["temp_delta"] = np.nan
    df["energy_per_temp"] = np.nan

# Keep only the columns we care about
feature_cols = [
    "meter_reading",
    "delta_1",
    "rolling_mean",
    "rolling_std",
    "range_24",
    "deviation",
    "z_score",
    "air_temperature",
    "temp_delta",
    "energy_per_temp",
]

detector = StructuralDriftDetector(DetectorConfig())

tested = 0
valid = []
failed = []

max_groups = 200
seen = 0

print("Scanning groups...")

for (b, m), g in df.groupby(["building_id", "meter"]):
    seen += 1

    if seen % 10 == 0:
        print(f"Seen {seen} groups... tested {tested}... valid {len(valid)}... failed {len(failed)}")

    if seen > max_groups:
        break

    unit = g[feature_cols].replace([np.inf, -np.inf], np.nan).dropna()

    if len(unit) < 500:
        continue

    # Skip near-constant / dead streams
    mean_std = unit.std(numeric_only=True).replace(0, np.nan).mean()
    if pd.isna(mean_std) or mean_std < 1e-6:
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
print("Groups seen:", seen)
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

# Save results for reuse
out = pd.DataFrame(valid, columns=["building_id", "meter", "warning_index", "n_cycles", "warning_ratio"])
out.to_csv("ashrae_warning_results.csv", index=False)
print("\nSaved: ashrae_warning_results.csv")
