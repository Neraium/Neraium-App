#!/usr/bin/env python3
"""Comprehensive drift detection test runner for CMAPSS FD004.

This script:
1. Loads FD004 dataset
2. Runs efficient drift detection using all 5 QIT intelligence components
3. Displays multi-dimensional datapoints
4. Identifies early drift signals
5. Saves results and visualizations

Usage:
    python run_drift_detection_demo.py [--max-units N] [--no-plots] [--output-dir DIR]

Example:
    python run_drift_detection_demo.py --max-units 50 --output-dir ./results
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from .config import DetectorConfig
from .test_runner_drift_detection import EfficientDriftTestRunner, DriftDetectionMetrics
from .test_runner_visualizer import DriftSignalVisualizer
from .evaluation import load_cmapss_dataset


class DriftDetectionDemoRunner:
    """Complete demo orchestration for drift detection."""

    def __init__(self, output_dir: str = "drift_test_results", verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.visualizer = DriftSignalVisualizer()

    def run(
        self,
        dataset_path: str | None = None,
        max_units: int | None = None,
        skip_plots: bool = False,
        sample_units: list[int] | None = None,
    ) -> None:
        """Run the complete drift detection demo.

        Args:
            dataset_path: Path to FD004 test/train data file
            max_units: Limit test to first N units
            skip_plots: Skip visualization generation
            sample_units: Specific units to visualize (if None, sample automatically)
        """
        print("\n" + "=" * 70)
        print("DRIFT DETECTION TEST RUNNER - CMAPSS FD004")
        print("Intelligence Components: Quantum, Information, Free Energy, Topological, Algorithmic")
        print("=" * 70 + "\n")

        # Step 1: Run drift detection
        print("[1/4] Initializing detector...")
        config = DetectorConfig()
        runner = EfficientDriftTestRunner(
            detector_config=config,
            degradation_proxy_fraction=0.1,
            healthy_fraction=0.15,
            verbose=self.verbose,
        )

        print("[2/4] Running drift detection on FD004...")
        start = time.time()
        results, summary = runner.run_fd004(dataset_path=dataset_path, max_units=max_units)
        elapsed = time.time() - start

        # Display summary
        self._print_summary(results, summary, elapsed)

        # Step 2: Save results
        print(f"\n[3/4] Saving results to {self.output_dir}...")
        saved_files = runner.save_results(results, summary, str(self.output_dir))
        print(f"  ✓ Saved: {saved_files['csv'].name}")
        print(f"  ✓ Saved: {saved_files['json'].name}")

        # Step 3: Visualizations
        if not skip_plots:
            print(f"\n[4/4] Generating visualizations...")
            data_dict = load_cmapss_dataset("FD004", train_path=None)

            # Sample units for detailed visualization
            if sample_units is None:
                sample_units = self._select_sample_units(results, max_count=4)

            for idx, unit_id in enumerate(sample_units, 1):
                print(f"  Visualizing unit {unit_id} ({idx}/{len(sample_units)})...", end=" ")
                try:
                    if unit_id not in data_dict:
                        print("(skipped - not in dataset)")
                        continue

                    unit_data = data_dict[unit_id]
                    sensors = unit_data[:, 4:]  # Skip cycle and operating settings

                    # Get scores for this unit
                    detector = runner.detector
                    scores = detector.process_unit(sensors)

                    # Main signal plot
                    plot_path = self.output_dir / f"unit_{unit_id}_signals.png"
                    self.visualizer.plot_unit_signals(
                        unit_id=unit_id,
                        sensor_data=sensors,
                        scores=scores,
                        output_path=str(plot_path),
                    )
                    print(f"✓ signals")

                    # Early warning focus plot
                    if scores.warning_index is not None:
                        ewarn_path = self.output_dir / f"unit_{unit_id}_early_warning.png"
                        self.visualizer.plot_early_warning_signals(
                            unit_id=unit_id,
                            sensor_data=sensors,
                            scores=scores,
                            window=150,
                            output_path=str(ewarn_path),
                        )
                        print(f"✓ early_warning", end="")

                except Exception as e:
                    print(f"(error: {e})")

            print("\n\n✓ Visualization complete")
        else:
            print("\n[4/4] Skipped visualization generation")

        # Summary file
        summary_path = self.output_dir / "RESULTS.txt"
        with open(summary_path, "w") as f:
            f.write(self._format_detailed_results(results, summary, elapsed))
        print(f"\n  ✓ Saved summary: {summary_path.name}")

        print("\n" + "=" * 70)
        print("✓ Drift detection complete")
        print(f"Output directory: {self.output_dir.absolute()}")
        print("=" * 70 + "\n")

    def _print_summary(self, results: list[DriftDetectionMetrics], summary: dict, elapsed: float) -> None:
        """Print a formatted summary of results."""
        valid_alerts = [r for r in results if r.warning_cycle is not None]
        valid_leads = [r.lead_time_cycles for r in valid_alerts if r.lead_time_cycles is not None]
        false_positives = [r for r in results if r.false_positive]

        print("\n" + "─" * 70)
        print("SUMMARY STATISTICS")
        print("─" * 70)
        print(f"Units tested:           {len(results)}/{summary.get('n_units_total', len(results))}")
        print(f"Detection rate:         {summary['detection_rate']:6.1%} ({len(valid_alerts)} units with alerts)")
        print(f"False positive rate:    {summary['false_positive_rate']:6.1%} ({len(false_positives)} units)")

        if valid_leads:
            print(f"\nLead Time Statistics:")
            print(f"  Median:               {np.median(valid_leads):7.0f} cycles")
            print(f"  Mean:                 {np.mean(valid_leads):7.0f} cycles")
            print(f"  Range:                {np.min(valid_leads):.0f} - {np.max(valid_leads):.0f} cycles")
            print(f"  Q1-Q3:                {np.percentile(valid_leads, 25):.0f} - {np.percentile(valid_leads, 75):.0f} cycles")

        print(f"\nDrift Signal Statistics:")
        print(f"  Mean raw drift:       {summary['mean_raw_drift']:7.4f}")
        print(f"  Mean EMA drift:       {summary['mean_ema_drift']:7.4f}")

        print(f"\nComponent Activation Ranking:")
        for component, count in summary["component_activation_ranking"]:
            pct = (count / len(results)) * 100
            print(f"  {component:15s}: {count:3d} units ({pct:5.1f}%)")

        print(f"\nPerformance:")
        print(f"  Elapsed time:         {elapsed:7.2f} seconds")
        print(f"  Throughput:           {summary['throughput_units_per_second']:7.1f} units/sec")
        print("─" * 70)

    def _select_sample_units(
        self,
        results: list[DriftDetectionMetrics],
        max_count: int = 4,
    ) -> list[int]:
        """Select representative units for visualization.

        Selects:
        1. First unit with early detection
        2. First unit with good lead time
        3. First unit with false positive (if any)
        4. First unit overall
        """
        samples = []

        # Early detection (<50 cycles lead time)
        early = [r for r in results if r.lead_time_cycles is not None and r.lead_time_cycles < 50]
        if early:
            samples.append(early[0].unit_id)

        # Good lead time (100-500 cycles)
        good = [r for r in results if r.lead_time_cycles is not None and 100 <= r.lead_time_cycles <= 500]
        if good:
            samples.append(good[len(good) // 2].unit_id)

        # False positive
        fp = [r for r in results if r.false_positive]
        if fp:
            samples.append(fp[0].unit_id)

        # First unit
        if results:
            samples.append(results[0].unit_id)

        return list(dict.fromkeys(samples))[:max_count]

    def _format_detailed_results(
        self,
        results: list[DriftDetectionMetrics],
        summary: dict,
        elapsed: float,
    ) -> str:
        """Format complete results report."""
        lines = [
            "=" * 80,
            "DRIFT DETECTION TEST RESULTS - CMAPSS FD004",
            "=" * 80,
            "",
            "OVERALL SUMMARY",
            "-" * 80,
        ]

        valid_alerts = [r for r in results if r.warning_cycle is not None]
        valid_leads = [r.lead_time_cycles for r in valid_alerts if r.lead_time_cycles is not None]
        false_positives = [r for r in results if r.false_positive]

        lines.extend([
            f"Units tested:           {len(results)}/{summary.get('n_units_total', len(results))}",
            f"Detection rate:         {summary['detection_rate']:6.1%}",
            f"False positive rate:    {summary['false_positive_rate']:6.1%}",
            "",
        ])

        if valid_leads:
            lines.extend([
                "LEAD TIME STATISTICS",
                "-" * 80,
                f"Median lead time:       {np.median(valid_leads):7.0f} cycles",
                f"Mean lead time:         {np.mean(valid_leads):7.0f} cycles",
                f"Min/Max:                {np.min(valid_leads):.0f} / {np.max(valid_leads):.0f} cycles",
                f"Q1-Q3 range:            {np.percentile(valid_leads, 25):.0f} - {np.percentile(valid_leads, 75):.0f} cycles",
                "",
            ])

        lines.extend([
            "SIGNAL STATISTICS",
            "-" * 80,
            f"Mean raw drift score:   {summary['mean_raw_drift']:7.4f}",
            f"Mean EMA drift score:   {summary['mean_ema_drift']:7.4f}",
            "",
            "COMPONENT ACTIVATION RANKING",
            "-" * 80,
        ])

        for component, count in summary["component_activation_ranking"]:
            pct = (count / len(results)) * 100 if len(results) > 0 else 0
            lines.append(f"{component:20s}: {count:3d} units ({pct:5.1f}%)")

        lines.extend([
            "",
            "PERFORMANCE",
            "-" * 80,
            f"Elapsed time:           {elapsed:7.2f} seconds",
            f"Throughput:             {summary['throughput_units_per_second']:7.1f} units/sec",
            "",
            "PER-UNIT RESULTS (First 20)",
            "-" * 80,
            f"{'Unit':>6} {'Cycle':>6} {'Warning':>8} {'Lead':>7} {'FP':>4} {'Raw':>8} {'EMA':>8} {'Dominant':>12}",
            "-" * 80,
        ])

        for r in results[:20]:
            fp_marker = "✓" if r.false_positive else " "
            lead_str = f"{r.lead_time_cycles:.0f}" if r.lead_time_cycles is not None else "N/A"
            warn_str = f"{r.warning_cycle:.0f}" if r.warning_cycle is not None else "N/A"

            lines.append(
                f"{r.unit_id:6d} {r.n_cycles:6d} {warn_str:>8} {lead_str:>7} {fp_marker:>4} "
                f"{r.mean_raw_drift:8.4f} {r.mean_ema_drift:8.4f} {r.dominant_component:>12}"
            )

        lines.extend([
            "=" * 80,
        ])

        return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Drift detection test runner for CMAPSS FD004 with multi-dimensional intelligence signals"
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
        help="Limit test to first N units (default: all)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip visualization generation",
    )
    parser.add_argument(
        "--units",
        type=int,
        nargs="+",
        help="Specific unit IDs to visualize",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="drift_test_results",
        help="Output directory (default: drift_test_results)",
    )

    args = parser.parse_args()

    demo = DriftDetectionDemoRunner(output_dir=args.output_dir, verbose=True)
    try:
        demo.run(
            dataset_path=args.path,
            max_units=args.max_units,
            skip_plots=args.no_plots,
            sample_units=args.units,
        )
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
