import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv("fd004_scored.csv")
df.columns = [c.lower() for c in df.columns]

print("COLUMNS:", df.columns.tolist())

required = ["unit", "alert_cycle", "failure_cycle", "alert_lead"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing required columns: {missing}")

# keep only rows where an alert exists
plot_df = df[df["alert_cycle"].notna()].copy()

if plot_df.empty:
    raise RuntimeError("No alerted units found in fd004_scored.csv")

plot_df["unit"] = plot_df["unit"].astype(int)
plot_df["alert_cycle"] = plot_df["alert_cycle"].astype(float)
plot_df["failure_cycle"] = plot_df["failure_cycle"].astype(float)
plot_df["alert_lead"] = plot_df["alert_lead"].astype(float)

lead_times = plot_df["alert_lead"].tolist()

print("\nFD004 SUMMARY")
print("mean lead  =", round(float(np.mean(lead_times)), 2))
print("median lead=", round(float(np.median(lead_times)), 2))
print("min lead   =", int(np.min(lead_times)))
print("max lead   =", int(np.max(lead_times)))
print("units hit  =", len(plot_df))
print("units total=", df["unit"].nunique())

# 1. Lead time histogram
plt.figure(figsize=(10, 6))
plt.hist(lead_times, bins=30)
plt.axvline(np.mean(lead_times), linestyle="--", label=f"Mean = {np.mean(lead_times):.1f}")
plt.axvline(np.median(lead_times), linestyle=":", label=f"Median = {np.median(lead_times):.1f}")
plt.title("FD004 Lead Time Distribution")
plt.xlabel("Cycles Before Failure")
plt.ylabel("Count")
plt.legend()
plt.tight_layout()
plt.savefig("fd004_lead_time_hist.png", dpi=200)
plt.show()

# 2. Alert to failure timeline
timeline_df = plot_df.sort_values("failure_cycle").reset_index(drop=True)

plt.figure(figsize=(12, 7))
for idx, row in timeline_df.iterrows():
    plt.plot([row["alert_cycle"], row["failure_cycle"]], [idx, idx])

plt.scatter(timeline_df["alert_cycle"], range(len(timeline_df)), label="Alert")
plt.scatter(timeline_df["failure_cycle"], range(len(timeline_df)), label="Failure")

plt.title("FD004 Alert to Failure Timeline")
plt.xlabel("Cycle")
plt.ylabel("Units")
plt.legend()
plt.tight_layout()
plt.savefig("fd004_timeline.png", dpi=200)
plt.show()

# 3. Hero units: one earlier, one later
timeline_by_lead = plot_df.sort_values("alert_lead").reset_index(drop=True)
hero_units = [
    int(timeline_by_lead.iloc[len(timeline_by_lead)//4]["unit"]),
    int(timeline_by_lead.iloc[len(timeline_by_lead)*3//4]["unit"]),
]
print("\nHero units:", hero_units)

# For hero curves, use the raw replay file if available
raw_file = "FD004_by_unit_results.csv"
try:
    raw_df = pd.read_csv(raw_file)
    raw_df.columns = [c.lower() for c in raw_df.columns]

    for i, unit in enumerate(hero_units, start=1):
        unit_summary = plot_df[plot_df["unit"] == unit].iloc[0]
        unit_raw = raw_df[raw_df["unit"] == unit].sort_values("cycle").copy()

        plt.figure(figsize=(10, 6))

        y_col = None
        if "structural_drift_score" in unit_raw.columns:
            y_col = "structural_drift_score"
            plt.plot(unit_raw["cycle"], unit_raw[y_col], label="Structural Drift Score")
        elif "system_health" in unit_raw.columns:
            y_col = "system_health"
            plt.plot(unit_raw["cycle"], unit_raw[y_col], label="System Health")

        if y_col is not None:
            plt.axvline(unit_summary["alert_cycle"], linestyle="--", label=f"Alert @ {int(unit_summary['alert_cycle'])}")
            plt.axvline(unit_summary["failure_cycle"], linestyle=":", label=f"Failure @ {int(unit_summary['failure_cycle'])}")

        plt.title(f"FD004 Hero Unit {unit}")
        plt.xlabel("Cycle")
        plt.ylabel(y_col if y_col is not None else "Value")
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"fd004_hero_{i}_unit_{unit}.png", dpi=200)
        plt.show()

except FileNotFoundError:
    print(f"\n{raw_file} not found, so hero curves were skipped.")
    print("Histogram and timeline were still saved.")

print("\nDONE")
print(" - fd004_lead_time_hist.png")
print(" - fd004_timeline.png")
print(" - fd004_hero_1_unit_*.png / fd004_hero_2_unit_*.png if raw replay file exists")
