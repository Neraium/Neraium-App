import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from neraium_core.alignment import StructuralEngine


# ============================================================
# CONFIG
# ============================================================
DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
TEST_FILE = DATA_DIR / "test_FD004.txt"
RUL_FILE = DATA_DIR / "RUL_FD004.txt"

OUT_DIR = Path("fd004_canonical_outputs")
OUT_DIR.mkdir(exist_ok=True)

RESULTS_CSV = OUT_DIR / "FD004_by_unit_results.csv"
SCORED_CSV = OUT_DIR / "FD004_scored.csv"
SUMMARY_JSON = OUT_DIR / "FD004_summary.json"

LEAD_HIST_PNG = OUT_DIR / "fd004_lead_time_hist.png"
TIMELINE_PNG = OUT_DIR / "fd004_timeline.png"
HERO1_PNG = OUT_DIR / "fd004_hero_1.png"
HERO2_PNG = OUT_DIR / "fd004_hero_2.png"


# ============================================================
# HELPERS
# ============================================================
def classify_alert_quality(x: float) -> str:
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


def load_fd004(test_file: Path) -> pd.DataFrame:
    df = pd.read_csv(test_file, sep=r"\s+", header=None)
    df = df.iloc[:, :26].copy()
    df.columns = (
        ["unit", "cycle", "os1", "os2", "os3"]
        + [f"s{i}" for i in range(1, 22)]
    )
    return df


def load_rul(rul_file: Path) -> pd.DataFrame:
    rul = pd.read_csv(rul_file, sep=r"\s+", header=None)
    rul = rul.iloc[:, [0]].copy()
    rul.columns = ["true_rul"]
    rul["unit"] = range(1, len(rul) + 1)
    return rul


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    if not TEST_FILE.exists():
        raise FileNotFoundError(f"Missing test file: {TEST_FILE}")
    if not RUL_FILE.exists():
        raise FileNotFoundError(f"Missing RUL file: {RUL_FILE}")

    print("=" * 70)
    print("RUNNING FD004 CANONICAL")
    print("=" * 70)
    print("TEST_FILE:", TEST_FILE)
    print("RUL_FILE :", RUL_FILE)
    print("OUT_DIR  :", OUT_DIR)

    df = load_fd004(TEST_FILE)
    rul = load_rul(RUL_FILE)

    print("rows loaded:", len(df))
    print("units loaded:", df["unit"].nunique())

    engine = StructuralEngine(
        baseline_window=24,
        recent_window=8,
        drift_smoothing_window=25,
        watch_quantile=0.65,
        alert_quantile=0.85,
        watch_persistence=5,
        alert_persistence=3,
        fast_trigger_multiplier=1.25,
        alert_latch_enabled=True,
        unlatch_ratio=0.75,
    )

    rows = []
    total_units = df["unit"].nunique()

    for idx, (unit, unit_df) in enumerate(df.groupby("unit", sort=True), start=1):
        unit_df = unit_df.sort_values("cycle").reset_index(drop=True)

        for _, row in unit_df.iterrows():
            sensor_values = {
                f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)
            }
            sensor_values.update({
                f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)
            })

            frame = {
                "timestamp": float(row["cycle"]),
                "site_id": "cmapss",
                "asset_id": f"FD004_unit_{int(unit)}",
                "sensor_values": sensor_values,
            }

            out = engine.process_frame(frame)

            rows.append({
                "unit": int(unit),
                "cycle": int(row["cycle"]),
                "policy_state": out.get("policy_state", out.get("state")),
                "policy_watch": bool(out.get("policy_watch", False)),
                "policy_alert": bool(out.get("policy_alert", False)),
                "state": out.get("state"),
                "structural_drift_score": float(out.get("structural_drift_score", 0.0) or 0.0),
                "drift_smooth": float(
                    out.get("drift_smooth",
                    out.get("structural_drift_score_smoothed",
                    out.get("latest_drift_smoothed", 0.0))) or 0.0
                ),
                "watch_threshold": float(out.get("watch_threshold", np.nan) or np.nan),
                "alert_threshold": float(out.get("alert_threshold", np.nan) or np.nan),
            })

        if idx % 25 == 0 or idx == total_units:
            print(f"processed units: {idx}/{total_units}")

    results_df = pd.DataFrame(rows)
    results_df.to_csv(RESULTS_CSV, index=False)

    # ------------------------------------------------------------
    # Score
    # ------------------------------------------------------------
    last_cycle = (
        results_df.groupby("unit", as_index=False)["cycle"]
        .max()
        .rename(columns={"cycle": "last_cycle"})
    )

    watch_cycles = (
        results_df[results_df["policy_watch"]]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "watch_cycle"})
    )

    alert_cycles = (
        results_df[results_df["policy_alert"]]
        .groupby("unit", as_index=False)["cycle"]
        .min()
        .rename(columns={"cycle": "alert_cycle"})
    )

    scored = (
        last_cycle
        .merge(rul, on="unit", how="left")
        .merge(watch_cycles, on="unit", how="left")
        .merge(alert_cycles, on="unit", how="left")
    )

    scored["failure_cycle"] = scored["last_cycle"] + scored["true_rul"]
    scored["watch_lead"] = scored["failure_cycle"] - scored["watch_cycle"]
    scored["alert_lead"] = scored["failure_cycle"] - scored["alert_cycle"]
    scored["has_watch"] = scored["watch_cycle"].notna()
    scored["has_alert"] = scored["alert_cycle"].notna()
    scored["alert_quality"] = scored["alert_lead"].apply(classify_alert_quality)

    scored.to_csv(SCORED_CSV, index=False)

    lead = scored.loc[scored["has_alert"], "alert_lead"]

    summary = {
        "units": int(len(scored)),
        "watch_coverage": float(scored["has_watch"].mean()),
        "alert_coverage": float(scored["has_alert"].mean()),
        "mean_alert_lead": float(lead.mean()) if len(lead) else None,
        "median_alert_lead": float(lead.median()) if len(lead) else None,
        "min_alert_lead": int(lead.min()) if len(lead) else None,
        "max_alert_lead": int(lead.max()) if len(lead) else None,
        "misses": int((~scored["has_alert"]).sum()),
        "alert_quality_counts": scored["alert_quality"].value_counts(dropna=False).to_dict(),
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2))

    print("\nFD004 CANONICAL SUMMARY")
    print("=" * 70)
    print("units:", summary["units"])
    print("watch coverage:", round(summary["watch_coverage"], 4))
    print("alert coverage:", round(summary["alert_coverage"], 4))
    print("mean alert lead:", round(summary["mean_alert_lead"], 2) if summary["mean_alert_lead"] is not None else None)
    print("median alert lead:", round(summary["median_alert_lead"], 2) if summary["median_alert_lead"] is not None else None)
    print("min alert lead:", summary["min_alert_lead"])
    print("max alert lead:", summary["max_alert_lead"])
    print("misses:", summary["misses"])
    print("\nALERT QUALITY")
    print(scored["alert_quality"].value_counts(dropna=False).to_string())

    # ------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------
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

    hero_df = timeline_df.sort_values("alert_lead").reset_index(drop=True)
    hero_units = []
    if len(hero_df) >= 2:
        hero_units = [
            int(hero_df.iloc[len(hero_df) // 4]["unit"]),
            int(hero_df.iloc[len(hero_df) * 3 // 4]["unit"]),
        ]

    hero_paths = [HERO1_PNG, HERO2_PNG]
    for i, unit in enumerate(hero_units[:2]):
        unit_series = results_df[results_df["unit"] == unit].sort_values("cycle")
        unit_score = scored[scored["unit"] == unit].iloc[0]

        plt.figure(figsize=(10, 6))
        plt.plot(unit_series["cycle"], unit_series["structural_drift_score"], label="Structural Drift Score")
        plt.axvline(unit_score["alert_cycle"], linestyle="--", label=f"Alert @ {int(unit_score['alert_cycle'])}")
        plt.axvline(unit_score["failure_cycle"], linestyle=":", label=f"Failure @ {int(unit_score['failure_cycle'])}")
        plt.title(f"FD004 Hero Unit {unit}")
        plt.xlabel("Cycle")
        plt.ylabel("Structural Drift Score")
        plt.legend()
        plt.tight_layout()
        plt.savefig(hero_paths[i], dpi=200)
        plt.close()

    print("\nSaved:")
    print(" -", RESULTS_CSV)
    print(" -", SCORED_CSV)
    print(" -", SUMMARY_JSON)
    print(" -", LEAD_HIST_PNG)
    print(" -", TIMELINE_PNG)
    if hero_units:
        print(" -", HERO1_PNG)
        print(" -", HERO2_PNG)


if __name__ == "__main__":
    main()
