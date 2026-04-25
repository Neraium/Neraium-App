#!/usr/bin/env python3
"""FD004 Frontier Stack Evaluation: Compare baseline vs. upgraded Intelligence Stack.

This script runs the full FD004 evaluation on all 248 units and generates:
1. Summary statistics (detection rate, FPR, median/mean true lead time)
2. Comparison table: baseline vs. frontier stack
3. Per-unit ablation diagnostics showing which signals fire first

Run: python3 fd004_frontier_evaluation.py
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from neraium_core.intelligence_stack.config import DetectorConfig
from neraium_core.intelligence_stack.detector import StructuralDriftDetector
from neraium_core.intelligence_stack.evaluation import load_cmapss_dataset


@dataclass
class TrueLeadTimeMetrics:
    """Metrics using true lead time from RUL data."""

    unit_id: int
    n_cycles: int
    rul: int
    true_failure_cycle: int
    warning_cycle: Optional[int]
    true_lead_time: Optional[int]
    false_positive: bool
    covered: bool

    # Diagnostic: which signal fires first
    first_structural_signal_cycle: Optional[int] = None
    first_acceleration_cycle: Optional[int] = None
    first_relational_cycle: Optional[int] = None
    first_regime_instability_cycle: Optional[int] = None


def load_rul_data() -> Dict[int, int]:
    """Load RUL data from RUL_FD004.txt file."""
    candidates = [
        Path("RUL_FD004.txt"),
        Path("data") / "RUL_FD004.txt",
        Path(__file__).parent / "data" / "RUL_FD004.txt",
        Path(__file__).parent / "archive" / "test_data" / "RUL_FD004.txt",
    ]

    for cand in candidates:
        if cand.exists():
            rul_dict = {}
            with open(cand) as f:
                for unit_id, line in enumerate(f, start=1):
                    rul_dict[unit_id] = int(line.strip())
            return rul_dict

    raise FileNotFoundError("Cannot find RUL_FD004.txt. Tried: " + ", ".join(str(c) for c in candidates))


def process_unit_true_lead_time(
    unit_id: int,
    unit_data: np.ndarray,
    rul: int,
    detector: StructuralDriftDetector,
) -> TrueLeadTimeMetrics:
    """Process a single unit using TRUE lead time."""
    # Extract sensor data (columns 4-24 are sensors)
    sensors = unit_data[:, 4:]

    n_cycles = len(sensors)
    last_cycle = int(unit_data[-1, 0])  # Get cycle number from first column
    true_failure_cycle = last_cycle + rul

    # Run detector
    scores = detector.process_unit(sensors)

    warning_cycle = scores.warning_index

    # Define false positive: alert in first 15% of data (healthy region)
    healthy_end = int(len(sensors) * 0.15)
    false_positive = warning_cycle is not None and warning_cycle < healthy_end
    covered = warning_cycle is not None

    # Compute TRUE lead time
    true_lead_time = None
    if warning_cycle is not None and not false_positive:
        true_lead_time = true_failure_cycle - warning_cycle
        if true_lead_time < 0:
            true_lead_time = None

    # Diagnostic: track first signal arrival
    first_structural = None
    first_accel = None
    first_relational = None
    first_regime = None

    if scores.diagnostic_timeline:
        for diag in scores.diagnostic_timeline:
            if first_structural is None and diag["structural_geometry"] > 0.3:
                first_structural = diag["cycle"]
            if first_accel is None and diag["acceleration_confidence"] > 0.3:
                first_accel = diag["cycle"]
            if first_relational is None and diag["relational_instability"] > 0.3:
                first_relational = diag["cycle"]
            if first_regime is None and diag["regime_instability"] > 0.3:
                first_regime = diag["cycle"]
            if all(x is not None for x in [first_structural, first_accel, first_relational, first_regime]):
                break

    return TrueLeadTimeMetrics(
        unit_id=unit_id,
        n_cycles=n_cycles,
        rul=rul,
        true_failure_cycle=true_failure_cycle,
        warning_cycle=warning_cycle,
        true_lead_time=true_lead_time,
        false_positive=false_positive,
        covered=covered,
        first_structural_signal_cycle=first_structural,
        first_acceleration_cycle=first_accel,
        first_relational_cycle=first_relational,
        first_regime_instability_cycle=first_regime,
    )


def compute_summary(results: List[TrueLeadTimeMetrics]) -> Dict:
    """Compute aggregate statistics."""
    n_total = len(results)
    covered = [r for r in results if r.covered]
    fps = [r for r in results if r.false_positive]
    detected = [r for r in results if r.covered and not r.false_positive]

    detection_rate = len(covered) / n_total if n_total > 0 else 0.0
    fpr = len(fps) / n_total if n_total > 0 else 0.0

    leads = [r.true_lead_time for r in detected if r.true_lead_time is not None]

    if leads:
        mean_lead = float(np.mean(leads))
        median_lead = float(np.median(leads))
        min_lead = float(np.min(leads))
        max_lead = float(np.max(leads))
        q1 = float(np.percentile(leads, 25))
        q3 = float(np.percentile(leads, 75))
    else:
        mean_lead = median_lead = min_lead = max_lead = q1 = q3 = 0.0

    return {
        "units_tested": n_total,
        "units_covered": len(covered),
        "units_detected_no_fp": len(detected),
        "detection_rate": detection_rate,
        "false_positive_rate": fpr,
        "mean_true_lead_time": mean_lead,
        "median_true_lead_time": median_lead,
        "min_true_lead_time": min_lead,
        "max_true_lead_time": max_lead,
        "q1_true_lead_time": q1,
        "q3_true_lead_time": q3,
        "units_with_fp": len(fps),
    }


def run_evaluation(detector_config: DetectorConfig, label: str = "unnamed") -> Tuple[List[TrueLeadTimeMetrics], Dict]:
    """Run full FD004 evaluation."""
    print(f"\n{'='*70}")
    print(f"Running {label} evaluation...")
    print(f"{'='*70}")

    start_time = time.time()

    # Load data
    print("Loading FD004 dataset and RUL data...")
    # Try to find the dataset path
    dataset_path = None
    candidates = [
        "train_FD004.txt",
        "data/train_FD004.txt",
        "archive/test_data/train_FD004.txt",
    ]
    for cand in candidates:
        if Path(cand).exists():
            dataset_path = cand
            break

    if dataset_path:
        data_dict = load_cmapss_dataset("FD004", train_path=dataset_path)
    else:
        data_dict = load_cmapss_dataset("FD004")

    rul_dict = load_rul_data()

    units = sorted([uid for uid in data_dict.keys() if uid in rul_dict])
    print(f"Processing {len(units)} units with RUL data\n")

    # Create detector
    detector = StructuralDriftDetector(detector_config)

    # Process units
    results: List[TrueLeadTimeMetrics] = []
    for idx, unit_id in enumerate(units, start=1):
        if idx % 50 == 0:
            print(f"  [{idx}/{len(units)}] Processing unit {unit_id}...")

        unit_data = data_dict[unit_id]
        rul = rul_dict[unit_id]

        metrics = process_unit_true_lead_time(unit_id, unit_data, rul, detector)
        results.append(metrics)

    elapsed = time.time() - start_time

    # Compute summary
    summary = compute_summary(results)
    summary["elapsed_time"] = elapsed
    summary["detector_label"] = label

    # Print summary
    print(f"\n{label.upper()} RESULTS:")
    print(f"  Units tested: {summary['units_tested']}")
    print(f"  Detection rate: {summary['detection_rate']:.1%}")
    print(f"  False positive rate: {summary['false_positive_rate']:.1%}")
    print(f"  Median true lead time: {summary['median_true_lead_time']:.0f} cycles")
    print(f"  Mean true lead time: {summary['mean_true_lead_time']:.1f} cycles")
    print(f"  Min/Max lead time: {summary['min_true_lead_time']:.0f} / {summary['max_true_lead_time']:.0f} cycles")
    print(f"  Q1/Q3: {summary['q1_true_lead_time']:.0f} / {summary['q3_true_lead_time']:.0f} cycles")
    print(f"  Elapsed time: {elapsed:.1f}s")

    return results, summary


def save_detailed_results(results: List[TrueLeadTimeMetrics], label: str) -> None:
    """Save per-unit results to CSV for analysis."""
    filename = f"fd004_{label}_detailed_results.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "unit_id",
                "n_cycles",
                "rul",
                "true_failure_cycle",
                "warning_cycle",
                "true_lead_time",
                "false_positive",
                "covered",
                "first_structural_signal",
                "first_acceleration",
                "first_relational",
                "first_regime_instability",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow({
                "unit_id": r.unit_id,
                "n_cycles": r.n_cycles,
                "rul": r.rul,
                "true_failure_cycle": r.true_failure_cycle,
                "warning_cycle": r.warning_cycle,
                "true_lead_time": r.true_lead_time,
                "false_positive": r.false_positive,
                "covered": r.covered,
                "first_structural_signal": r.first_structural_signal_cycle,
                "first_acceleration": r.first_acceleration_cycle,
                "first_relational": r.first_relational_cycle,
                "first_regime_instability": r.first_regime_instability_cycle,
            })
    print(f"Detailed results saved to {filename}")


def save_comparison_table(summaries: Dict[str, Dict]) -> None:
    """Save comparison table to CSV."""
    filename = "fd004_frontier_comparison.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "variant",
                "detection_rate",
                "false_positive_rate",
                "median_true_lead_time",
                "mean_true_lead_time",
                "min_true_lead_time",
                "max_true_lead_time",
                "q1_true_lead_time",
                "q3_true_lead_time",
                "improvement_median",
                "improvement_mean",
            ],
        )
        writer.writeheader()

        # Calculate baseline for improvements
        baseline_summary = summaries.get("baseline", {})
        baseline_median = baseline_summary.get("median_true_lead_time", 0)
        baseline_mean = baseline_summary.get("mean_true_lead_time", 0)

        for variant, summary in summaries.items():
            improvement_median = 0
            improvement_mean = 0

            if baseline_median > 0:
                improvement_median = ((summary.get("median_true_lead_time", 0) - baseline_median) / baseline_median) * 100
            if baseline_mean > 0:
                improvement_mean = ((summary.get("mean_true_lead_time", 0) - baseline_mean) / baseline_mean) * 100

            writer.writerow({
                "variant": variant,
                "detection_rate": f"{summary.get('detection_rate', 0):.1%}",
                "false_positive_rate": f"{summary.get('false_positive_rate', 0):.1%}",
                "median_true_lead_time": f"{summary.get('median_true_lead_time', 0):.0f}",
                "mean_true_lead_time": f"{summary.get('mean_true_lead_time', 0):.1f}",
                "min_true_lead_time": f"{summary.get('min_true_lead_time', 0):.0f}",
                "max_true_lead_time": f"{summary.get('max_true_lead_time', 0):.0f}",
                "q1_true_lead_time": f"{summary.get('q1_true_lead_time', 0):.0f}",
                "q3_true_lead_time": f"{summary.get('q3_true_lead_time', 0):.0f}",
                "improvement_median": f"{improvement_median:+.1f}%",
                "improvement_mean": f"{improvement_mean:+.1f}%",
            })

    print(f"Comparison table saved to {filename}")


if __name__ == "__main__":
    print("="*70)
    print("FD004 FRONTIER STACK EVALUATION")
    print("Comparing baseline vs. upgraded Intelligence Stack")
    print("="*70)

    summaries = {}
    all_results = {}

    # Run baseline evaluation (current config)
    baseline_config = DetectorConfig()
    baseline_results, baseline_summary = run_evaluation(baseline_config, "baseline")
    summaries["baseline"] = baseline_summary
    all_results["baseline"] = baseline_results
    save_detailed_results(baseline_results, "baseline")

    # Run frontier evaluation (AGGRESSIVE structural-only detection)
    # The frontier stack fires based on structural evidence alone,
    # without requiring amplitude confirmation. This enables early detection
    # at the cost of possibly slight loss of precision.
    frontier_config = DetectorConfig()
    # Make frontier more aggressive: lower thresholds, earlier firing
    frontier_config.threshold_std = 1.8  # Lower than baseline (2.5)
    frontier_config.persistence = 2  # Faster confirmation than baseline (5)
    frontier_results, frontier_summary = run_evaluation(frontier_config, "frontier")
    summaries["frontier"] = frontier_summary
    all_results["frontier"] = frontier_results
    save_detailed_results(frontier_results, "frontier")

    # Save comparison table
    save_comparison_table(summaries)

    # Print final comparison
    print("\n" + "="*70)
    print("COMPARISON: BASELINE vs. FRONTIER")
    print("="*70)
    print(f"\n{'Metric':<35} {'Baseline':>15} {'Frontier':>15} {'Improvement':>15}")
    print("-" * 80)

    baseline = summaries["baseline"]
    frontier = summaries["frontier"]

    metrics = [
        ("Detection Rate", "detection_rate", lambda x: f"{x:.1%}"),
        ("False Positive Rate", "false_positive_rate", lambda x: f"{x:.1%}"),
        ("Median True Lead Time", "median_true_lead_time", lambda x: f"{x:.0f} cycles"),
        ("Mean True Lead Time", "mean_true_lead_time", lambda x: f"{x:.1f} cycles"),
        ("Q1 True Lead Time", "q1_true_lead_time", lambda x: f"{x:.0f} cycles"),
        ("Q3 True Lead Time", "q3_true_lead_time", lambda x: f"{x:.0f} cycles"),
    ]

    for name, key, fmt in metrics:
        baseline_val = baseline.get(key, 0)
        frontier_val = frontier.get(key, 0)

        # Calculate improvement
        if key == "false_positive_rate":
            # Lower is better
            if baseline_val > 0:
                improvement = ((baseline_val - frontier_val) / baseline_val) * 100
                improvement_str = f"{improvement:+.1f}% (lower)"
            else:
                improvement_str = "same"
        elif "lead_time" in key:
            # Higher is better
            if baseline_val > 0:
                improvement = ((frontier_val - baseline_val) / baseline_val) * 100
                improvement_str = f"{improvement:+.1f}% (higher)"
            else:
                improvement_str = "N/A"
        else:
            # Higher is better
            if baseline_val > 0:
                improvement = ((frontier_val - baseline_val) / baseline_val) * 100
                improvement_str = f"{improvement:+.1f}%"
            else:
                improvement_str = "N/A"

        print(f"{name:<35} {fmt(baseline_val):>15} {fmt(frontier_val):>15} {improvement_str:>15}")

    print("\n" + "="*70)
    print("SUCCESS CRITERIA:")
    print("="*70)

    baseline_median = baseline.get("median_true_lead_time", 0)
    frontier_median = frontier.get("median_true_lead_time", 0)
    baseline_fpr = baseline.get("false_positive_rate", 0)
    frontier_fpr = frontier.get("false_positive_rate", 0)
    baseline_dr = baseline.get("detection_rate", 0)
    frontier_dr = frontier.get("detection_rate", 0)

    print(f"\n✓ Target median lead time 110-130 cycles:")
    print(f"  Baseline: {baseline_median:.0f} cycles")
    print(f"  Frontier: {frontier_median:.0f} cycles")
    if frontier_median >= 110:
        print(f"  STATUS: ✓ ACHIEVED" if frontier_median <= 130 else f"  STATUS: EXCEEDED TARGET (good!)")
    else:
        print(f"  STATUS: Not yet achieved (need +{110-frontier_median:.0f} cycles)")

    print(f"\n✓ Maintain 0% false positives:")
    print(f"  Baseline FPR: {baseline_fpr:.1%}")
    print(f"  Frontier FPR: {frontier_fpr:.1%}")
    print(f"  STATUS: {'✓ ACHIEVED' if frontier_fpr == 0.0 else 'NOT ACHIEVED'}")

    print(f"\n✓ Maintain high detection rate:")
    print(f"  Baseline: {baseline_dr:.1%}")
    print(f"  Frontier: {frontier_dr:.1%}")
    print(f"  STATUS: {'✓ MAINTAINED' if frontier_dr >= baseline_dr else 'DEGRADED'}")

    print("\n" + "="*70)
