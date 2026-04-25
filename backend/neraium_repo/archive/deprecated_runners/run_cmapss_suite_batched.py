import time
from pathlib import Path

import numpy as np
import pandas as pd

from neraium_core.alignment import StructuralEngine

DATA_DIR = Path(r"C:\Users\Owner\Desktop\CMAPSSData")
DATASETS = ["FD001", "FD002", "FD003", "FD004"]


def _first_cycle_at_or_above(profile: pd.Series, threshold: float) -> int | None:
    hits = profile[profile >= threshold]
    if hits.empty:
        return None
    return int(hits.index.min())


def _oscillation_stats(profile: pd.Series) -> tuple[float, float]:
    values = profile.to_numpy(dtype=float)
    if values.size <= 2:
        return 0.0, 0.0

    diff = np.diff(values)
    nonzero = diff[np.abs(diff) > 1e-12]
    if nonzero.size <= 1:
        flip_ratio = 0.0
    else:
        signs = np.sign(nonzero)
        flips = int(np.sum(signs[1:] != signs[:-1]))
        flip_ratio = float(flips / (len(signs) - 1))

    mean_step = float(np.mean(np.abs(diff))) if diff.size else 0.0
    return flip_ratio, mean_step


def _print_fd001_interpretation_note(timeline_df: pd.DataFrame, unit_summary_df: pd.DataFrame) -> None:
    if timeline_df.empty:
        print("FD001 interpretation note: unavailable (no timeline rows).")
        return

    by_cycle = timeline_df.groupby("cycle", as_index=True).agg(
        structural_drift_score=("structural_drift_score", "mean"),
        relational_instability_score=("relational_instability_score", "mean"),
    )

    structural_threshold = max(0.15, float(by_cycle["structural_drift_score"].quantile(0.70)))
    relational_threshold = max(0.15, float(by_cycle["relational_instability_score"].quantile(0.70)))

    first_structural_cycle = _first_cycle_at_or_above(by_cycle["structural_drift_score"], structural_threshold)
    first_relational_cycle = _first_cycle_at_or_above(by_cycle["relational_instability_score"], relational_threshold)

    total_lead_time = None
    if first_structural_cycle is not None:
        lead = unit_summary_df["last_cycle"] - first_structural_cycle
        total = lead[lead > 0].sum()
        total_lead_time = int(total) if total > 0 else 0

    fd001_flip_ratio, fd001_mean_step = _oscillation_stats(by_cycle["structural_drift_score"])

    fd004_comparison_path = Path("FD004_by_unit_results.csv")
    smoother_vs_fd004 = None
    if fd004_comparison_path.exists():
        try:
            fd004_df = pd.read_csv(fd004_comparison_path)
            fd004_df.columns = [c.lower() for c in fd004_df.columns]
            required_cols = {"cycle", "structural_drift_score"}
            if required_cols.issubset(fd004_df.columns):
                fd004_cycle_profile = fd004_df.groupby("cycle")["structural_drift_score"].mean().sort_index()
                fd004_flip_ratio, fd004_mean_step = _oscillation_stats(fd004_cycle_profile)
                smoother_vs_fd004 = (fd001_flip_ratio < fd004_flip_ratio) and (fd001_mean_step <= fd004_mean_step)
        except Exception as err:
            print(
                "- FD004 smoothness comparison warning: "
                f"could not parse {fd004_comparison_path} ({err})."
            )

    print("\nFD001 INTERPRETATION NOTE")
    print("- first cycle of meaningful structural drift:", first_structural_cycle)
    print("- first cycle of meaningful relational instability:", first_relational_cycle)
    print("- total lead time before failure (if threshold crossed):", total_lead_time)
    if smoother_vs_fd004 is None:
        print("- FD004 smoothness comparison: unavailable (missing or incompatible FD004 comparison data).")
    else:
        print("- drift profile smoother than FD004 (oscillation-based):", "yes" if smoother_vs_fd004 else "no")

def load_train_dataset(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"train_{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    df = df.dropna(axis=1).copy()

    n_cols = df.shape[1]
    expected_sensor_count = n_cols - 5  # unit, cycle, os1, os2, os3
    df.columns = (
        ["unit", "cycle", "os1", "os2", "os3"]
        + [f"s{i}" for i in range(1, expected_sensor_count + 1)]
    )
    return df

def run_dataset(name: str) -> dict:
    print(f"\n{'='*70}")
    print(f"RUNNING {name}")
    print(f"{'='*70}")

    df = load_train_dataset(name)
    units = sorted(df["unit"].unique())
    total_units = len(units)
    total_rows = len(df)

    print(f"rows loaded: {total_rows}")
    print(f"units loaded: {total_units}")

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

    results = []
    timeline_rows = []
    t0 = time.time()

    for idx, unit in enumerate(units, start=1):
        unit_df = df[df["unit"] == unit].sort_values("cycle")

        first_alert_cycle = None
        first_watch_cycle = None
        last_cycle = int(unit_df["cycle"].max())

        for row in unit_df.itertuples(index=False):
            sensor_values = {
                "os1": float(row.os1),
                "os2": float(row.os2),
                "os3": float(row.os3),
            }

            for i in range(1, len(unit_df.columns) - 4):
                key = f"s{i}"
                if hasattr(row, key):
                    sensor_values[key] = float(getattr(row, key))

            frame = {
                "timestamp": float(row.cycle),
                "site_id": name,
                "asset_id": f"{name}_unit_{int(row.unit)}",
                "sensor_values": sensor_values,
            }

            out = engine.process_frame(frame)

            policy_watch = bool(out.get("policy_watch", False))
            policy_alert = bool(out.get("policy_alert", False))
            state = out.get("policy_state", out.get("state"))

            if first_watch_cycle is None and (policy_watch or state == "WATCH"):
                first_watch_cycle = int(row.cycle)

            if first_alert_cycle is None and (policy_alert or state == "ALERT"):
                first_alert_cycle = int(row.cycle)

            timeline_rows.append(
                {
                    "unit": int(unit),
                    "cycle": int(row.cycle),
                    "structural_drift_score": float(out.get("structural_drift_score", 0.0) or 0.0),
                    "relational_instability_score": float(out.get("relational_instability_score", 0.0) or 0.0),
                }
            )

        results.append({
            "dataset": name,
            "unit": int(unit),
            "last_cycle": last_cycle,
            "first_watch_cycle": first_watch_cycle,
            "first_alert_cycle": first_alert_cycle,
            "has_watch": first_watch_cycle is not None,
            "has_alert": first_alert_cycle is not None,
        })

        elapsed = time.time() - t0
        rate = idx / elapsed if elapsed > 0 else 0.0
        print(
            f"[{name}] processed unit {idx}/{total_units} | "
            f"alerts so far: {sum(r['has_alert'] for r in results)} | "
            f"{rate:.2f} units/sec | elapsed {elapsed:.1f}s",
            flush=True
        )

    res = pd.DataFrame(results)

    summary = {
        "dataset": name,
        "units": int(len(res)),
        "watch_coverage": float(res["has_watch"].mean()),
        "alert_coverage": float(res["has_alert"].mean()),
        "mean_first_watch_cycle": float(res.loc[res["has_watch"], "first_watch_cycle"].mean()) if res["has_watch"].any() else None,
        "mean_first_alert_cycle": float(res.loc[res["has_alert"], "first_alert_cycle"].mean()) if res["has_alert"].any() else None,
        "misses": int((~res["has_alert"]).sum()),
    }

    out_csv = Path(f"{name}_suite_unit_summary.csv")
    res.to_csv(out_csv, index=False)

    print(f"\n{name} SUMMARY")
    print(f"watch coverage: {summary['watch_coverage']:.4f}")
    print(f"alert coverage: {summary['alert_coverage']:.4f}")
    print(f"mean first watch cycle: {summary['mean_first_watch_cycle']}")
    print(f"mean first alert cycle: {summary['mean_first_alert_cycle']}")
    print(f"misses: {summary['misses']}")
    print(f"saved -> {out_csv}")

    if name == "FD001":
        _print_fd001_interpretation_note(pd.DataFrame(timeline_rows), res)

    return summary

all_summaries = []

for ds in DATASETS:
    try:
        all_summaries.append(run_dataset(ds))
    except Exception as e:
        print(f"\nERROR on {ds}: {e}")

suite_df = pd.DataFrame(all_summaries)
suite_df.to_csv("cmapss_suite_results_batched.csv", index=False)

print(f"\n{'='*70}")
print("CMAPSS SUITE RESULTS")
print(f"{'='*70}")
if not suite_df.empty:
    print(suite_df.to_string(index=False))
print("\nsaved -> cmapss_suite_results_batched.csv")
