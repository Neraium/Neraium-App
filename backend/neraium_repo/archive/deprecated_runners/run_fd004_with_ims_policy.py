import pandas as pd
from pathlib import Path

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
RAW_RESULTS = Path("FD004_by_unit_results.csv")
RUL_FILE = DATA_DIR / "RUL_FD004.txt"

if not RAW_RESULTS.exists():
    raise FileNotFoundError(f"Missing {RAW_RESULTS}")

if not RUL_FILE.exists():
    raise FileNotFoundError(f"Missing {RUL_FILE}")

df = pd.read_csv(RAW_RESULTS).sort_values(["unit", "cycle"]).reset_index(drop=True)
df.columns = [c.lower() for c in df.columns]

if "structural_drift_score" not in df.columns:
    raise ValueError("FD004_by_unit_results.csv must contain structural_drift_score")

# -----------------------------
# IMS-style policy layer
# -----------------------------
out_frames = []

for unit, unit_df in df.groupby("unit", sort=True):
    unit_df = unit_df.sort_values("cycle").copy()

    unit_df["drift_smooth"] = unit_df["structural_drift_score"].rolling(25, min_periods=1).mean()

    watch_threshold = float(unit_df["drift_smooth"].quantile(0.65))
    alert_threshold = float(unit_df["drift_smooth"].quantile(0.92))

    states = []
    watch_counter = 0
    alert_counter = 0
    alert_latched = False

    for v in unit_df["drift_smooth"]:
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

        states.append(s)

    unit_df["ims_policy_state"] = states
    unit_df["ims_policy_alert"] = unit_df["ims_policy_state"] == "ALERT"
    unit_df["ims_policy_watch"] = unit_df["ims_policy_state"] == "WATCH"
    unit_df["ims_watch_threshold"] = watch_threshold
    unit_df["ims_alert_threshold"] = alert_threshold

    out_frames.append(unit_df)

policy_df = pd.concat(out_frames, ignore_index=True)
policy_df.to_csv("FD004_ims_policy_results.csv", index=False)

# -----------------------------
# Score against RUL
# -----------------------------
rul = pd.read_csv(RUL_FILE, sep=r"\s+", header=None)
rul = rul.iloc[:, [0]].copy()
rul.columns = ["true_rul"]
rul["unit"] = range(1, len(rul) + 1)

last_cycle = (
    policy_df.groupby("unit", as_index=False)["cycle"]
    .max()
    .rename(columns={"cycle": "last_cycle"})
)

watch_cycles = (
    policy_df[policy_df["ims_policy_watch"]]
    .groupby("unit", as_index=False)["cycle"]
    .min()
    .rename(columns={"cycle": "watch_cycle"})
)

alert_cycles = (
    policy_df[policy_df["ims_policy_alert"]]
    .groupby("unit", as_index=False)["cycle"]
    .min()
    .rename(columns={"cycle": "alert_cycle"})
)

summary = (
    last_cycle
    .merge(rul, on="unit", how="left")
    .merge(watch_cycles, on="unit", how="left")
    .merge(alert_cycles, on="unit", how="left")
)

summary["failure_cycle"] = summary["last_cycle"] + summary["true_rul"]
summary["watch_lead"] = summary["failure_cycle"] - summary["watch_cycle"]
summary["alert_lead"] = summary["failure_cycle"] - summary["alert_cycle"]
summary["has_watch"] = summary["watch_cycle"].notna()
summary["has_alert"] = summary["alert_cycle"].notna()

def classify(x):
    if pd.isna(x):
        return "miss"
    if x < 0:
        return "late"
    if x < 30:
        return "last_minute"
    if x < 100:
        return "usable"
    if x < 200:
        return "good"
    return "very_early"

summary["alert_quality"] = summary["alert_lead"].apply(classify)
summary.to_csv("FD004_ims_policy_scored.csv", index=False)

# -----------------------------
# Print summary
# -----------------------------
lead = summary.loc[summary["has_alert"], "alert_lead"]

print("\n" + "=" * 60)
print("FD004 WITH IMS POLICY")
print("=" * 60)
print("units:", len(summary))
print("watch coverage:", round(float(summary["has_watch"].mean()), 4))
print("alert coverage:", round(float(summary["has_alert"].mean()), 4))
print("mean alert lead:", round(float(lead.mean()), 2) if len(lead) else None)
print("median alert lead:", round(float(lead.median()), 2) if len(lead) else None)
print("min alert lead:", int(lead.min()) if len(lead) else None)
print("max alert lead:", int(lead.max()) if len(lead) else None)

print("\nALERT QUALITY")
print(summary["alert_quality"].value_counts(dropna=False).to_string())

print("\nSaved:")
print(" - FD004_ims_policy_results.csv")
print(" - FD004_ims_policy_scored.csv")
