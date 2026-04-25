import pandas as pd
from pathlib import Path

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
RESULTS = Path("FD004_by_unit_results.csv")
OUT = Path("FD004_policy_benchmark.csv")

df = pd.read_csv(RESULTS).sort_values(["unit", "cycle"]).reset_index(drop=True)

rul = pd.read_csv(DATA_DIR / "RUL_FD004.txt", sep=r"\s+", header=None)
rul = rul.iloc[:, [0]].copy()
rul.columns = ["true_rul"]
rul["unit"] = range(1, len(rul) + 1)

last_cycle = df.groupby("unit", as_index=False)["cycle"].max().rename(columns={"cycle": "last_cycle"})
base = last_cycle.merge(rul, on="unit", how="left")
base["failure_cycle"] = base["last_cycle"] + base["true_rul"]

def score_policy(name, alert_mask):
    alert_cycles = (
        df[alert_mask]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "alert_cycle"})
    )

    scored = base.merge(alert_cycles, on="unit", how="left")
    scored["has_alert"] = scored["alert_cycle"].notna()
    scored["alert_lead"] = scored["failure_cycle"] - scored["alert_cycle"]

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

    scored["quality"] = scored["alert_lead"].apply(classify)

    lead = scored.loc[scored["has_alert"], "alert_lead"]

    row = {
        "policy": name,
        "units": len(scored),
        "coverage": float(scored["has_alert"].mean()),
        "mean_lead": float(lead.mean()) if len(lead) else None,
        "median_lead": float(lead.median()) if len(lead) else None,
        "min_lead": float(lead.min()) if len(lead) else None,
        "max_lead": float(lead.max()) if len(lead) else None,
        "miss": int((scored["quality"] == "miss").sum()),
        "late": int((scored["quality"] == "late").sum()),
        "last_minute": int((scored["quality"] == "last_minute").sum()),
        "usable": int((scored["quality"] == "usable").sum()),
        "good": int((scored["quality"] == "good").sum()),
        "very_early": int((scored["quality"] == "very_early").sum()),
    }
    return row

# Original alert
original_alert = df["state"] == "ALERT"

# Persistence only
df["is_watch"] = df["state"] == "WATCH"
df["watch_streak"] = df.groupby("unit")["is_watch"].transform(
    lambda x: x.astype(int).rolling(10, min_periods=1).sum()
)
persist_only = (df["state"] == "ALERT") | (df["watch_streak"] >= 8)

# Persistence + delay
first_watch = (
    df[df["is_watch"]]
    .groupby("unit", as_index=False)["cycle"]
    .min()
    .rename(columns={"cycle": "first_watch_cycle"})
)
df = df.merge(first_watch, on="unit", how="left")

persist_delay = (
    (df["state"] == "ALERT") |
    (
        (df["watch_streak"] >= 8) &
        (df["cycle"] > df["first_watch_cycle"] + 20)
    )
)

# Persistence + delay + strength
watch_rows = df[df["is_watch"]].copy()
score_threshold = watch_rows["structural_drift_score"].quantile(0.80)

persist_delay_strength = (
    (df["state"] == "ALERT") |
    (
        (df["watch_streak"] >= 8) &
        (df["cycle"] > df["first_watch_cycle"] + 20) &
        (df["structural_drift_score"] >= score_threshold)
    )
)

rows = [
    score_policy("original_alert", original_alert),
    score_policy("persistence_only", persist_only),
    score_policy("persistence_plus_delay", persist_delay),
    score_policy("persistence_delay_strength", persist_delay_strength),
]

out_df = pd.DataFrame(rows)
out_df.to_csv(OUT, index=False)

print(out_df.to_string(index=False))
print("\nsaved ->", OUT)
print(f"\nstrength threshold used: {score_threshold}")
