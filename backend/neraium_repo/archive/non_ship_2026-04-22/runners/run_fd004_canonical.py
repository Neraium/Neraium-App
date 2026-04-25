"""Canonical FD004 benchmark runner.

This is the ONLY official benchmark runner for FD004/FD001 datasets.
It uses StructuralEngine to process CMAPSS data and generate results.

Usage:
    # With explicit paths
    python -m runners.run_fd004_canonical --test test_FD004.txt --rul RUL_FD004.txt

    # Using environment variable
    export CMAPSS_DATA_DIR=/path/to/cmapss/data
    python -m runners.run_fd004_canonical

    # Using ./data/ directory in repo (if present)
    python -m runners.run_fd004_canonical

Output:
    Generates results in outputs/ directory with timestamp:
    - outputs/canonical_benchmarks/FD004_<timestamp>.csv (detailed results)
    - outputs/canonical_benchmarks/FD004_scored_<timestamp>.csv (scored with RUL)
    - outputs/canonical_benchmarks/FD004_summary_<timestamp>.json (summary metrics)
    - outputs/canonical_benchmarks/FD004_lead_time_<timestamp>.png (distribution)
    - outputs/canonical_benchmarks/FD004_timeline_<timestamp>.png (failure timeline)
    - outputs/canonical_benchmarks/FD004_hero_*.png (example units)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from neraium_core.alignment import StructuralEngine


# ============================================================
# CANONICAL CONFIGURATION
# ============================================================

# Output directory (canonical location)
OUTPUT_DIR = Path("outputs") / "canonical_benchmarks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Timestamp for this run
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# FD004 dataset paths will be resolved at runtime
TEST_FILE: Path | None = None
RUL_FILE: Path | None = None

# Output paths (canonical naming scheme)
RESULTS_CSV = OUTPUT_DIR / f"FD004_{TIMESTAMP}.csv"
SCORED_CSV = OUTPUT_DIR / f"FD004_scored_{TIMESTAMP}.csv"
SUMMARY_JSON = OUTPUT_DIR / f"FD004_summary_{TIMESTAMP}.json"
LEAD_HIST_PNG = OUTPUT_DIR / f"FD004_lead_time_{TIMESTAMP}.png"
TIMELINE_PNG = OUTPUT_DIR / f"FD004_timeline_{TIMESTAMP}.png"
HERO1_PNG = OUTPUT_DIR / f"FD004_hero_1_{TIMESTAMP}.png"
HERO2_PNG = OUTPUT_DIR / f"FD004_hero_2_{TIMESTAMP}.png"

# ============================================================
# ENGINE CONFIGURATION (FD004 locked policy)
# ============================================================

ENGINE_CONFIG = {
    "baseline_window": 24,
    "recent_window": 8,
    "drift_smoothing_window": 25,
    "watch_quantile": 0.65,
    "alert_quantile": 0.85,
    "watch_persistence": 5,
    "alert_persistence": 3,
    "fast_trigger_multiplier": 1.25,
    "alert_latch_enabled": True,
    "unlatch_ratio": 0.75,
}


# ============================================================
# HELPERS
# ============================================================

def resolve_data_paths(test_arg: str | None = None, rul_arg: str | None = None) -> tuple[Path, Path]:
    """Resolve test and RUL file paths with fallback logic.

    Priority:
    1. Command-line arguments (--test, --rul)
    2. Environment variable CMAPSS_DATA_DIR
    3. ./data/ directory in current repo
    4. Raise error if not found

    Args:
        test_arg: Path to test file from command-line (can be relative or absolute)
        rul_arg: Path to RUL file from command-line (can be relative or absolute)

    Returns:
        Tuple of (test_file, rul_file) as Path objects

    Raises:
        FileNotFoundError: If files cannot be located
    """
    test_file = None
    rul_file = None

    # Priority 1: Command-line arguments
    if test_arg and rul_arg:
        test_file = Path(test_arg).resolve()
        rul_file = Path(rul_arg).resolve()
        if test_file.exists() and rul_file.exists():
            return test_file, rul_file
        else:
            missing = []
            if not test_file.exists():
                missing.append(str(test_file))
            if not rul_file.exists():
                missing.append(str(rul_file))
            raise FileNotFoundError(f"Files not found: {', '.join(missing)}")

    # Priority 2: Environment variable CMAPSS_DATA_DIR
    env_dir = os.getenv("CMAPSS_DATA_DIR")
    if env_dir:
        env_path = Path(env_dir).resolve()
        test_file = env_path / "test_FD004.txt"
        rul_file = env_path / "RUL_FD004.txt"
        if test_file.exists() and rul_file.exists():
            return test_file, rul_file
        else:
            missing = []
            if not test_file.exists():
                missing.append(str(test_file))
            if not rul_file.exists():
                missing.append(str(rul_file))
            raise FileNotFoundError(
                f"CMAPSS_DATA_DIR={env_dir} set but files not found: {', '.join(missing)}"
            )

    # Priority 3: ./data/ directory in repo
    repo_data_dir = Path("./data").resolve()
    if repo_data_dir.exists():
        test_file = repo_data_dir / "test_FD004.txt"
        rul_file = repo_data_dir / "RUL_FD004.txt"
        if test_file.exists() and rul_file.exists():
            return test_file, rul_file

    # Priority 4: Error
    raise FileNotFoundError(
        "Cannot locate CMAPSS data files. Tried:\n"
        "  1. Command-line arguments (--test, --rul)\n"
        "  2. Environment variable CMAPSS_DATA_DIR\n"
        "  3. ./data/ directory in repo\n"
        "\n"
        "Please provide files using one of these methods:\n"
        f"  • python -m runners.run_fd004_canonical --test <path> --rul <path>\n"
        f"  • export CMAPSS_DATA_DIR=/path/to/cmapss/data\n"
        f"  • Place files in ./data/ directory"
    )


def classify_alert_quality(lead_time: float) -> str:
    """Classify alert lead time quality.

    Args:
        lead_time: Cycles between alert and failure

    Returns:
        Quality classification string
    """
    if pd.isna(lead_time):
        return "miss"
    if lead_time < 0:
        return "late"
    if lead_time < 30:
        return "last_minute"
    if lead_time < 100:
        return "usable"
    if lead_time < 200:
        return "good"
    return "very_early"


def load_fd004(test_file: Path) -> pd.DataFrame:
    """Load FD004 test data.

    Args:
        test_file: Path to FD004 test file

    Returns:
        DataFrame with columns: unit, cycle, os1-3, s1-21
    """
    df = pd.read_csv(test_file, sep=r"\s+", header=None)
    df = df.iloc[:, :26].copy()
    df.columns = (
        ["unit", "cycle", "os1", "os2", "os3"]
        + [f"s{i}" for i in range(1, 22)]
    )
    return df


def load_rul(rul_file: Path) -> pd.DataFrame:
    """Load FD004 RUL labels.

    Args:
        rul_file: Path to RUL file

    Returns:
        DataFrame with columns: unit, true_rul
    """
    rul = pd.read_csv(rul_file, sep=r"\s+", header=None)
    rul = rul.iloc[:, [0]].copy()
    rul.columns = ["true_rul"]
    rul["unit"] = range(1, len(rul) + 1)
    return rul


def run_engine(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Process data through StructuralEngine.

    Args:
        df: DataFrame with unit, cycle, os1-3, s1-21 columns

    Returns:
        List of result dicts with one entry per frame
    """
    engine = StructuralEngine(**ENGINE_CONFIG)

    rows = []
    total_units = df["unit"].nunique()

    print(f"\nProcessing {total_units} units through StructuralEngine...")

    for idx, (unit, unit_df) in enumerate(df.groupby("unit", sort=True), start=1):
        unit_df = unit_df.sort_values("cycle").reset_index(drop=True)

        for _, row in unit_df.iterrows():
            # Build sensor values dict from os1-3 and s1-21
            sensor_values = {
                f"os{i}": float(row[f"os{i}"]) for i in range(1, 4)
            }
            sensor_values.update({
                f"s{i}": float(row[f"s{i}"]) for i in range(1, 22)
            })

            # Canonical frame format
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
            print(f"  ✓ Processed {idx}/{total_units} units")

    return rows


def score_results(results_df: pd.DataFrame, rul_df: pd.DataFrame) -> pd.DataFrame:
    """Score results against RUL labels.

    Args:
        results_df: DataFrame from run_engine with all frames
        rul_df: DataFrame with true_rul for each unit

    Returns:
        Scored DataFrame with alert lead times and classifications
    """
    print("\nScoring results against RUL...")

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
        .merge(rul_df, on="unit", how="left")
        .merge(watch_cycles, on="unit", how="left")
        .merge(alert_cycles, on="unit", how="left")
    )

    scored["failure_cycle"] = scored["last_cycle"] + scored["true_rul"]
    scored["watch_lead"] = scored["failure_cycle"] - scored["watch_cycle"]
    scored["alert_lead"] = scored["failure_cycle"] - scored["alert_cycle"]
    scored["has_watch"] = scored["watch_cycle"].notna()
    scored["has_alert"] = scored["alert_cycle"].notna()
    scored["alert_quality"] = scored["alert_lead"].apply(classify_alert_quality)

    return scored


def compute_summary(scored_df: pd.DataFrame) -> dict[str, Any]:
    """Compute summary metrics.

    Args:
        scored_df: DataFrame from score_results

    Returns:
        Summary dict with coverage, lead times, quality counts
    """
    lead = scored_df.loc[scored_df["has_alert"], "alert_lead"]

    summary = {
        "units": int(len(scored_df)),
        "watch_coverage": float(scored_df["has_watch"].mean()),
        "alert_coverage": float(scored_df["has_alert"].mean()),
        "mean_alert_lead": float(lead.mean()) if len(lead) else None,
        "median_alert_lead": float(lead.median()) if len(lead) else None,
        "min_alert_lead": int(lead.min()) if len(lead) else None,
        "max_alert_lead": int(lead.max()) if len(lead) else None,
        "misses": int((~scored_df["has_alert"]).sum()),
        "alert_quality_counts": scored_df["alert_quality"].value_counts(dropna=False).to_dict(),
    }

    return summary


def generate_charts(results_df: pd.DataFrame, scored_df: pd.DataFrame) -> None:
    """Generate visualization charts.

    Args:
        results_df: DataFrame from run_engine (all frames)
        scored_df: DataFrame from score_results (summary per unit)
    """
    import matplotlib.pyplot as plt

    print("\nGenerating charts...")

    lead = scored_df.loc[scored_df["has_alert"], "alert_lead"]

    # Lead time distribution
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
    print(f"  ✓ Saved: {LEAD_HIST_PNG.name}")

    # Timeline
    timeline_df = scored_df[scored_df["has_alert"]].sort_values("failure_cycle").reset_index(drop=True)
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
    print(f"  ✓ Saved: {TIMELINE_PNG.name}")

    # Hero units
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
        unit_score = scored_df[scored_df["unit"] == unit].iloc[0]

        plt.figure(figsize=(10, 6))
        plt.plot(unit_series["cycle"], unit_series["structural_drift_score"], label="Structural Drift Score")
        plt.axvline(unit_score["alert_cycle"], linestyle="--", label=f"Alert @ {int(unit_score['alert_cycle'])}")
        plt.axvline(unit_score["failure_cycle"], linestyle=":", label=f"Failure @ {int(unit_score['failure_cycle'])}")
        plt.title(f"FD004 Hero Unit {int(unit)}")
        plt.xlabel("Cycle")
        plt.ylabel("Structural Drift Score")
        plt.legend()
        plt.tight_layout()
        plt.savefig(hero_paths[i], dpi=200)
        plt.close()
        print(f"  ✓ Saved: {hero_paths[i].name}")


def print_summary(summary: dict[str, Any], scored_df: pd.DataFrame) -> None:
    """Print formatted summary.

    Args:
        summary: Summary dict from compute_summary
        scored_df: Scored DataFrame
    """
    print("\n" + "=" * 70)
    print("FD004 CANONICAL BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Units: {summary['units']}")
    print(f"Watch Coverage: {summary['watch_coverage']:.4f}")
    print(f"Alert Coverage: {summary['alert_coverage']:.4f}")
    print(f"Mean Alert Lead: {summary['mean_alert_lead']:.2f}" if summary["mean_alert_lead"] is not None else "Mean Alert Lead: N/A")
    print(f"Median Alert Lead: {summary['median_alert_lead']:.2f}" if summary["median_alert_lead"] is not None else "Median Alert Lead: N/A")
    print(f"Min/Max Lead: {summary['min_alert_lead']} / {summary['max_alert_lead']}")
    print(f"Misses: {summary['misses']}")
    print("\nAlert Quality Distribution:")
    print(scored_df["alert_quality"].value_counts(dropna=False).to_string())
    print("=" * 70)


def main() -> None:
    """Run canonical FD004 benchmark."""
    parser = argparse.ArgumentParser(
        description="Canonical FD004 benchmark runner using StructuralEngine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Path resolution priority:\n"
            "  1. Command-line arguments (--test, --rul)\n"
            "  2. Environment variable CMAPSS_DATA_DIR\n"
            "  3. ./data/ directory in repo\n"
        ),
    )
    parser.add_argument(
        "--test",
        type=str,
        default=None,
        help="Path to test file (e.g., test_FD004.txt). Can be relative or absolute.",
    )
    parser.add_argument(
        "--rul",
        type=str,
        default=None,
        help="Path to RUL file (e.g., RUL_FD004.txt). Can be relative or absolute.",
    )
    args = parser.parse_args()

    # Resolve data paths with fallback logic
    global TEST_FILE, RUL_FILE
    TEST_FILE, RUL_FILE = resolve_data_paths(args.test, args.rul)

    print("=" * 70)
    print("CANONICAL FD004 BENCHMARK RUNNER")
    print("=" * 70)
    print(f"\nResolved paths:")
    print(f"  Test File: {TEST_FILE}")
    print(f"  RUL File:  {RUL_FILE}")
    print(f"  Output Dir: {OUTPUT_DIR}")
    print(f"  Timestamp: {TIMESTAMP}")

    # Load data
    df = load_fd004(TEST_FILE)
    rul = load_rul(RUL_FILE)
    print(f"\nLoaded {len(df)} rows from {df['unit'].nunique()} units")

    # Run engine
    rows = run_engine(df)
    results_df = pd.DataFrame(rows)
    results_df.to_csv(RESULTS_CSV, index=False)
    print(f"✓ Saved: {RESULTS_CSV.name}")

    # Score results
    scored_df = score_results(results_df, rul)
    scored_df.to_csv(SCORED_CSV, index=False)
    print(f"✓ Saved: {SCORED_CSV.name}")

    # Compute summary
    summary = compute_summary(scored_df)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2))
    print(f"✓ Saved: {SUMMARY_JSON.name}")

    # Generate charts
    generate_charts(results_df, scored_df)

    # Print summary
    print_summary(summary, scored_df)
    print(f"\nAll outputs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
