#!/usr/bin/env python3
"""Advanced FD004 test runner: handles 6 operating conditions × 2 fault modes.

Usage:
    python run_advanced_fd004_demo.py [--max-units N] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from neraium_core.intelligence_stack.config import DetectorConfig
from .plotting import plot_unit_diagnosis
from tools.eval.test_runner_advanced_fd004 import AdvancedFD004TestRunner, AdvancedDriftMetrics


class AdvancedFD004Demo:
    """Advanced FD004 demo with multi-condition & fault mode analysis."""

    def __init__(self, output_dir: str = "fd004_advanced_results", verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

    def run(self, dataset_path: str | None = None, max_units: int | None = None) -> None:
        """Run complete advanced FD004 analysis."""
        print("\n" + "=" * 80)
        print("ADVANCED DRIFT DETECTION - NASA CMAPSS FD004")
        print("=" * 80)
        print("\nFD004 Complexity:")
        print("  • 249 units in test set (hardest CMAPSS dataset)")
        print("  • 6 operating conditions (non-linear interactions)")
        print("  • 2 fault modes: HPC degradation + Fan degradation")
        print("  • Highly variable degradation rates")
        print("\nDetector Strategy:")
        print("  • 5 intelligence components track different degradation signatures")
        print("  • Operating condition segmentation for condition-aware detection")
        print("  • Fault mode inference from component activation patterns")
        print("  • Per-condition lead time computation")
        print("=" * 80 + "\n")

        if dataset_path:
            print(f"Using dataset: {dataset_path}\n")

        # Run analysis
        print("[1/3] Initializing advanced detector...")
        config = DetectorConfig()
        runner = AdvancedFD004TestRunner(
            detector_config=config,
            degradation_proxy_fraction=0.1,
            healthy_fraction=0.15,
            verbose=self.verbose,
        )

        print("[2/3] Running drift detection on FD004 (249 units)...")
        start = time.time()
        results, summary, per_cycle_data = runner.run_fd004_advanced(dataset_path=dataset_path, max_units=max_units)
        elapsed = time.time() - start

        # Display results
        self._print_detailed_results(results, summary, elapsed)

        # Save results
        print(f"\n[3/3] Saving results to {self.output_dir}...")
        saved_files = runner.save_results(results, summary, per_cycle_data, str(self.output_dir))
        print(f"  ✓ Saved: {saved_files['csv'].name}")
        print(f"  ✓ Saved: {saved_files['cycle_csv'].name}")
        print(f"  ✓ Saved: {saved_files['json'].name}")

        # Generate trajectory plots for units with valid alerts
        self._generate_trajectory_plots(results, per_cycle_data, str(self.output_dir))

        # Summary file
        summary_path = self.output_dir / "ADVANCED_RESULTS.txt"
        with open(summary_path, "w") as f:
            f.write(self._format_detailed_report(results, summary, elapsed))
        print(f"  ✓ Saved: {summary_path.name}")

        print("\n" + "=" * 80)
        print("✓ Advanced FD004 analysis complete")
        print(f"Output directory: {self.output_dir.absolute()}")
        print("=" * 80 + "\n")

    def _print_detailed_results(
        self,
        results: list[AdvancedDriftMetrics],
        summary: dict,
        elapsed: float,
    ) -> None:
        """Print comprehensive results."""
        valid_alerts = [r for r in results if r.warning_cycle is not None]
        valid_leads = [r.lead_time_cycles for r in valid_alerts if r.lead_time_cycles is not None]
        false_positives = [r for r in results if r.false_positive]

        print("\n" + "─" * 80)
        print("RESULTS SUMMARY")
        print("─" * 80)

        # Overall metrics
        print(f"\nOverall Detection Performance:")
        print(f"  Units tested:           {len(results)}/{summary.get('n_units_total', len(results))}")
        print(f"  Detection rate:         {summary['detection_rate']:6.1%} ({len(valid_alerts)} units)")
        print(f"  False positive rate:    {summary['false_positive_rate']:6.1%} ({len(false_positives)} units)")

        # Lead time
        if valid_leads:
            print(f"\nLead Time Statistics:")
            print(f"  Median:                 {np.median(valid_leads):7.0f} cycles")
            print(f"  Mean:                   {np.mean(valid_leads):7.0f} cycles")
            print(f"  Range:                  {np.min(valid_leads):.0f} - {np.max(valid_leads):.0f} cycles")
            print(f"  Quartiles (Q1-Q3):      {np.percentile(valid_leads, 25):.0f} - {np.percentile(valid_leads, 75):.0f}")

        # Fault mode distribution
        print(f"\nInferred Fault Modes (249 units, 2 modes):")
        for mode, count in summary["fault_mode_distribution"].items():
            pct = (count / len(results)) * 100 if len(results) > 0 else 0
            print(f"  {mode:15s}: {count:3d} units ({pct:5.1f}%)")

        # Operating condition performance
        print(f"\nPerformance by Operating Condition (6 conditions):")
        print(f"  Condition │ Detections │ Median Lead Time")
        print(f"  ──────────┼────────────┼──────────────────")
        for cond_id in range(1, 7):
            cond_data = summary["condition_analysis"][cond_id]
            lead_str = f"{cond_data['median_lead_time']:7.0f} cycles" if cond_data["median_lead_time"] else "         N/A"
            print(f"      {cond_id}      │     {cond_data['detection_count']:3d}     │ {lead_str}")

        # Signal characteristics
        print(f"\nSignal Characteristics:")
        print(f"  Mean raw drift:         {summary['mean_raw_drift']:7.4f}")
        print(f"  Mean EMA drift:         {summary['mean_ema_drift']:7.4f}")

        # Performance
        print(f"\nPerformance:")
        print(f"  Total time:             {elapsed:7.2f} seconds")
        print(f"  Throughput:             {summary['throughput_units_per_second']:7.1f} units/second")
        print(f"  Rate:                   ~{(len(results)/elapsed*60):.0f} units/minute")

        print("─" * 80)

    def _generate_trajectory_plots(
        self,
        results: list[AdvancedDriftMetrics],
        per_cycle_data: list,
        output_dir: str,
    ) -> None:
        """Generate trajectory plots for units with valid alerts (up to 10 units)."""
        # Find units with valid alerts
        valid_units = [
            (r, pc) for r, pc in zip(results, per_cycle_data)
            if r.warning_cycle is not None and not r.false_positive
        ]

        if not valid_units:
            print("  [note] No units with valid alerts to plot")
            return

        # Plot up to 10 units with valid alerts
        n_plots = min(10, len(valid_units))
        print(f"\n  Generating trajectory plots for {n_plots} units...")

        plots_dir = Path(output_dir) / "trajectory_plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        for i, (metrics, cycle_data) in enumerate(valid_units[:n_plots]):
            unit_id = metrics.unit_id
            lead_time = metrics.lead_time_cycles or 0
            title_suffix = f"(Unit {unit_id}, Lead Time = {lead_time:.0f} cycles)"

            # Calculate indices for healthy region and degradation onset
            n_cycles = len(cycle_data.cycles)
            healthy_end_index = int(n_cycles * 0.15)
            degradation_index = n_cycles - int(n_cycles * 0.1)

            try:
                plot_path = plots_dir / f"fd004_unit_{unit_id}_trajectory.png"
                plot_unit_diagnosis(
                    unit_id=unit_id,
                    sensor_data=cycle_data.sensor_data,
                    raw_drift=cycle_data.raw_drift,
                    ema_drift=cycle_data.ema_drift,
                    threshold=0.5,  # Approximate threshold; could be refined
                    warning_index=metrics.warning_cycle,
                    healthy_end_index=healthy_end_index,
                    degradation_index=degradation_index,
                    save_path=str(plot_path),
                    title_suffix=title_suffix,
                )
                print(f"    ✓ Plotted: {plot_path.name}")
            except Exception as e:
                print(f"    [warn] Failed to plot unit {unit_id}: {e}")

    def _format_detailed_report(
        self,
        results: list[AdvancedDriftMetrics],
        summary: dict,
        elapsed: float,
    ) -> str:
        """Format comprehensive report."""
        lines = [
            "=" * 90,
            "ADVANCED DRIFT DETECTION ANALYSIS - NASA CMAPSS FD004",
            "=" * 90,
            "",
            "DATASET COMPLEXITY",
            "-" * 90,
            "• 249 units in test set (hardest CMAPSS variant)",
            "• 6 operating conditions with non-linear interactions",
            "• 2 fault modes: HPC degradation + Fan degradation",
            "• Variable degradation rates across units",
            "",
            "DETECTION APPROACH",
            "-" * 90,
            "• 5-component QIT detector (Quantum, Information, Free Energy, Topological, Algorithmic)",
            "• Operating condition segmentation for multi-condition awareness",
            "• Fault mode inference from component activation patterns",
            "• Per-condition lead time computation",
            "• Walk-forward safe reference statistics",
            "",
        ]

        valid_alerts = [r for r in results if r.warning_cycle is not None]
        valid_leads = [r.lead_time_cycles for r in valid_alerts if r.lead_time_cycles is not None]
        false_positives = [r for r in results if r.false_positive]

        lines.extend([
            "OVERALL RESULTS",
            "-" * 90,
            f"Units tested:           {len(results)}/{summary.get('n_units_total', len(results))}",
            f"Detection rate:         {summary['detection_rate']:6.1%}",
            f"False positive rate:    {summary['false_positive_rate']:6.1%}",
            "",
        ])

        if valid_leads:
            lines.extend([
                "LEAD TIME ANALYSIS",
                "-" * 90,
                f"Detections with valid lead time: {len(valid_leads)}/{len(valid_alerts)}",
                f"Median lead time:       {np.median(valid_leads):7.0f} cycles",
                f"Mean lead time:         {np.mean(valid_leads):7.0f} cycles",
                f"Min/Max:                {np.min(valid_leads):.0f} / {np.max(valid_leads):.0f} cycles",
                f"Q1/Q3:                  {np.percentile(valid_leads, 25):.0f} / {np.percentile(valid_leads, 75):.0f} cycles",
                "",
            ])

        lines.extend([
            "FAULT MODE DISTRIBUTION",
            "-" * 90,
        ])
        for mode, count in summary["fault_mode_distribution"].items():
            pct = (count / len(results)) * 100 if len(results) > 0 else 0
            lines.append(f"{mode:20s}: {count:3d} units ({pct:5.1f}%)")

        lines.extend([
            "",
            "OPERATING CONDITION ANALYSIS (6 conditions)",
            "-" * 90,
            f"{'Condition':>10} │ {'Detections':>11} │ {'Median Lead':>12} │ {'Mean Lead':>12}",
            "-" * 90,
        ])
        for cond_id in range(1, 7):
            cond_data = summary["condition_analysis"][cond_id]
            median = f"{cond_data['median_lead_time']:.0f}" if cond_data["median_lead_time"] else "N/A"
            mean = f"{cond_data['mean_lead_time']:.0f}" if cond_data["mean_lead_time"] else "N/A"
            lines.append(f"{cond_id:10d} │ {cond_data['detection_count']:11d} │ {median:>12} │ {mean:>12}")

        lines.extend([
            "",
            "SIGNAL CHARACTERISTICS",
            "-" * 90,
            f"Mean raw drift score:   {summary['mean_raw_drift']:7.4f}",
            f"Mean EMA drift score:   {summary['mean_ema_drift']:7.4f}",
            "",
            "PERFORMANCE METRICS",
            "-" * 90,
            f"Total elapsed time:     {elapsed:7.2f} seconds",
            f"Throughput:             {summary['throughput_units_per_second']:7.1f} units/second",
            f"Per-unit time:          {(elapsed/len(results)*1000):.0f} milliseconds",
            "",
            "PER-UNIT SUMMARY (First 30 units)",
            "-" * 90,
            f"{'Unit':>6} {'Cycles':>7} {'Warn':>7} {'Lead':>7} {'FP':>3} {'Conds':>6} {'Fault Mode':>15} {'Dominant':>12}",
            "-" * 90,
        ])

        for r in results[:30]:
            fp_str = "✓" if r.false_positive else " "
            lead_str = f"{r.lead_time_cycles:.0f}" if r.lead_time_cycles is not None else "N/A"
            warn_str = f"{r.warning_cycle:.0f}" if r.warning_cycle is not None else "N/A"
            conds = ",".join(str(c) for c in r.operating_conditions_present)

            lines.append(
                f"{r.unit_id:6d} {r.n_cycles:7d} {warn_str:>7} {lead_str:>7} {fp_str:>3} {conds:>6} "
                f"{r.inferred_fault_mode:>15} {r.dominant_component:>12}"
            )

        lines.extend([
            "=" * 90,
        ])

        return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Advanced drift detection for FD004 (6 conditions, 2 fault modes)"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to FD004 dataset file (test_FD004.txt or train_FD004.txt)",
    )
    parser.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Limit to first N units (default: all 249)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="fd004_advanced_results",
        help="Output directory (default: fd004_advanced_results)",
    )

    args = parser.parse_args()

    demo = AdvancedFD004Demo(output_dir=args.output_dir, verbose=True)
    try:
        demo.run(dataset_path=args.path, max_units=args.max_units)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
