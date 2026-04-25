import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
RUL_FILE = DATA_DIR / "RUL_FD004.txt"

OUT_DIR = Path("fd004_canonical_fast_outputs")
OUT_DIR.mkdir(exist_ok=True)

SCORED_CSV = OUT_DIR / "FD004_scored.csv"
SUMMARY_JSON = OUT_DIR / "FD004_summary.json"
LEAD_HIST_PNG = OUT_DIR / "fd004_lead_time_hist.png"
TIMELINE_PNG = OUT_DIR / "fd004_timeline.png"
HERO1_PNG = OUT_DIR / "fd004_hero_1.png"
HERO2_PNG = OUT_DIR / "fd004_hero_2.png"

CANDIDATE_SCORED = [
    Path("FD004_ims_policy_tuned_scored.csv"),
    Path("fd004_scored.csv"),
    Path("FD004_ims_policy_scored.csv"),
]
RAW_RESULTS = Path("FD004_by_unit_results.csv")


def classify_alert_quality(x):
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


def load_scored_file():
    for path in CANDIDATE_SCORED:
        if path.exists():
            df = pd.read_csv(path)
            df.columns = [c.lower() for c in df.columns]
            print(f"Using scored file: {path}")
            return df, path
    return None, None


def build_scored_from_raw():
    if not RAW_RESULTS.exists():
        raise FileNotFoundError(
            "No scored file found and missing raw file FD004_by_unit_results.csv"
        )
    if not RUL_FILE.exists():
        raise FileNotFoundError(f"Missing {RUL_FILE}")

    raw = pd.read_csv(RAW_RESULTS)
    raw.columns = [c.lower() for c in raw.columns]

    if "unit" not in raw.columns or "cycle" not in raw.columns:
        raise ValueError("FD004_by_unit_results.csv must contain unit and cycle")

    rul = pd.read_csv(RUL_FILE, sep=r"\s+", header=None)
    rul = rul.iloc[:, [0]].copy()
    rul.columns = ["true_rul"]
    rul["unit"] = range(1, len(rul) + 1)

    last_cycle = (
        raw.groupby("unit", as_index=False)["cycle"]
        .max()
        .rename(columns={"cycle": "last_cycle"})
    )

    scored = last_cycle.merge(rul, on="unit", how="left")
    scored["failure_cycle"] = scored["last_cycle"] + scored["true_rul"]

    # derive alert/watch cycles from available columns
    if "policy_alert" in raw.columns:
        alert_src = raw["policy_alert"].astype(bool)
    elif "has_alert" in raw.columns:
        alert_src = raw["has_alert"].astype(bool)
    elif "state" in raw.columns:
        alert_src = raw["state"].astype(str).str.upper().eq("ALERT")
    else:
        raise ValueError("Could not derive alerts from raw file")

    if "policy_watch" in raw.columns:
        watch_src = raw["policy_watch"].astype(bool)
    elif "has_watch" in raw.columns:
        watch_src = raw["has_watch"].astype(bool)
    elif "state" in raw.columns:
        watch_src = raw["state"].astype(str).str.upper().eq("WATCH")
    else:
        watch_src = pd.Series(False, index=raw.index)

    alert_cycles = (
        raw.loc[alert_src]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "alert_cycle"})
    )

    watch_cycles = (
        raw.loc[watch_src]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "watch_cycle"})
    )

    scored = (
        scored.merge(watch_cycles, on="unit", how="left")
              .merge(alert_cycles, on="unit", how="left")
    )

    scored["has_watch"] = scored["watch_cycle"].notna()
    scored["has_alert"] = scored["alert_cycle"].notna()
    scored["watch_lead"] = scored["failure_cycle"] - scored["watch_cycle"]
    scored["alert_lead"] = scored["failure_cycle"] - scored["alert_cycle"]
    scored["alert_quality"] = scored["alert_lead"].apply(classify_alert_quality)

    print("Built scored results from raw replay file")
    return scored, RAW_RESULTS


scored, source_path = load_scored_file()
if scored is None:
    scored, source_path = build_scored_from_raw()

scored.columns = [c.lower() for c in scored.columns]

required_cols = ["unit"]
missing = [c for c in required_cols if c not in scored.columns]
if missing:
    raise ValueError(f"Missing required columns in {source_path}: {missing}")

# normalize schema if using an already-scored file
if "has_watch" not in scored.columns and "watch_cycle" in scored.columns:
    scored["has_watch"] = scored["watch_cycle"].notna()

if "has_alert" not in scored.columns and "alert_cycle" in scored.columns:
    scored["has_alert"] = scored["alert_cycle"].notna()

if "watch_lead" not in scored.columns and {"failure_cycle", "watch_cycle"}.issubset(scored.columns):
    scored["watch_lead"] = scored["failure_cycle"] - scored["watch_cycle"]

if "alert_lead" not in scored.columns and {"failure_cycle", "alert_cycle"}.issubset(scored.columns):
    scored["alert_lead"] = scored["failure_cycle"] - scored["alert_cycle"]

if "alert_quality" not in scored.columns and "alert_lead" in scored.columns:
    scored["alert_quality"] = scored["alert_lead"].apply(classify_alert_quality)

if "true_rul" not in scored.columns and RUL_FILE.exists():
    rul = pd.read_csv(RUL_FILE, sep=r"\s+", header=None)
    rul = rul.iloc[:, [0]].copy()
    rul.columns = ["true_rul"]
    rul["unit"] = range(1, len(rul) + 1)
    scored = scored.merge(rul, on="unit", how="left")

if "failure_cycle" not in scored.columns and {"last_cycle", "true_rul"}.issubset(scored.columns):
    scored["failure_cycle"] = scored["last_cycle"] + scored["true_rul"]

if "last_cycle" not in scored.columns and {"failure_cycle", "true_rul"}.issubset(scored.columns):
    scored["last_cycle"] = scored["failure_cycle"] - scored["true_rul"]

needed_now = ["has_alert", "alert_lead", "alert_quality", "failure_cycle", "alert_cycle"]
still_missing = [c for c in needed_now if c not in scored.columns]
if still_missing:
    raise ValueError(f"Still missing columns after normalization: {still_missing}")

scored.to_csv(SCORED_CSV, index=False)

lead = scored.loc[scored["has_alert"], "alert_lead"]

summary = {
    "source_file": str(source_path),
    "units": int(len(scored)),
    "watch_coverage": float(scored["has_watch"].mean()) if "has_watch" in scored.columns else None,
    "alert_coverage": float(scored["has_alert"].mean()),
    "mean_alert_lead": float(lead.mean()) if len(lead) else None,
    "median_alert_lead": float(lead.median()) if len(lead) else None,
    "min_alert_lead": int(lead.min()) if len(lead) else None,
    "max_alert_lead": int(lead.max()) if len(lead) else None,
    "misses": int((~scored["has_alert"]).sum()),
    "alert_quality_counts": scored["alert_quality"].value_counts(dropna=False).to_dict(),
}
SUMMARY_JSON.write_text(json.dumps(summary, indent=2))

print("\nFD004 FAST CANONICAL SUMMARY")
print("=" * 60)
print("source:", summary["source_file"])
print("units:", summary["units"])
if summary["watch_coverage"] is not None:
    print("watch coverage:", round(summary["watch_coverage"], 4))
print("alert coverage:", round(summary["alert_coverage"], 4))
print("mean alert lead:", round(summary["mean_alert_lead"], 2) if summary["mean_alert_lead"] is not None else None)
print("median alert lead:", round(summary["median_alert_lead"], 2) if summary["median_alert_lead"] is not None else None)
print("min alert lead:", summary["min_alert_lead"])
print("max alert lead:", summary["max_alert_lead"])
print("misses:", summary["misses"])
print("\nALERT QUALITY")
print(scored["alert_quality"].value_counts(dropna=False).to_string())

# lead histogram
plt.figure(figsize=(10, 6))
plt.hist(lead, bins=30)
plt.axvline(lead.mean(), linestyle="--", label=f"Mean = {lead.mean():.1f}")
plt.axvline(lead.median(), linestyle=":", label=f"Median = {lead.median():.1f}")
plt.title("FD004 Lead Time Distribution")
plt.xlabel("Cycles Before Failure")
plt.ylabel("Count")
plt.legend()
plt.tight_layout()
plt.savefig(LEAD_HIST_PNG, dpi=200)
plt.close()

# timeline
timeline_df = scored[scored["has_alert"]].sort_values("failure_cycle").reset_index(drop=True)

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
plt.savefig(TIMELINE_PNG, dpi=200)
plt.close()

# hero plots if raw replay exists
raw_df = None
if RAW_RESULTS.exists():
    raw_df = pd.read_csv(RAW_RESULTS)
    raw_df.columns = [c.lower() for c in raw_df.columns]

hero_df = timeline_df.sort_values("alert_lead").reset_index(drop=True)
hero_units = []
if len(hero_df) >= 2:
    hero_units = [
        int(hero_df.iloc[len(hero_df) // 4]["unit"]),
        int(hero_df.iloc[len(hero_df) * 3 // 4]["unit"]),
    ]

hero_paths = [HERO1_PNG, HERO2_PNG]
for i, unit in enumerate(hero_units[:2]):
    if raw_df is None:
        break

    unit_raw = raw_df[raw_df["unit"] == unit].sort_values("cycle")
    unit_score = scored[scored["unit"] == unit].iloc[0]

    y_col = None
    if "structural_drift_score" in unit_raw.columns:
        y_col = "structural_drift_score"
    elif "drift_smooth" in unit_raw.columns:
        y_col = "drift_smooth"

    if unit_raw.empty or y_col is None:
        continue

    plt.figure(figsize=(10, 6))
    plt.plot(unit_raw["cycle"], unit_raw[y_col], label=y_col)
    plt.axvline(unit_score["alert_cycle"], linestyle="--", label=f"Alert @ {int(unit_score['alert_cycle'])}")
    plt.axvline(unit_score["failure_cycle"], linestyle=":", label=f"Failure @ {int(unit_score['failure_cycle'])}")
    plt.title(f"FD004 Hero Unit {unit}")
    plt.xlabel("Cycle")
    plt.ylabel(y_col)
    plt.legend()
    plt.tight_layout()
    plt.savefig(hero_paths[i], dpi=200)
    plt.close()

print("\nSaved:")
print(" -", SCORED_CSV)
print(" -", SUMMARY_JSON)
print(" -", LEAD_HIST_PNG)
print(" -", TIMELINE_PNG)
if raw_df is not None and hero_units:
    print(" -", HERO1_PNG)
    print(" -", HERO2_PNG)
