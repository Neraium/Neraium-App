"""Efficient drift detection test runner for CMAPSS FD004.

Integrates all intelligence components:
- Quantum detector
- Information detector
- Free energy detector
- Topological detector
- Algorithmic detector

Provides multi-dimensional datapoints for early drift signal detection.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import DetectorConfig
from .detector import StructuralDriftDetector
from .evaluation import load_cmapss_dataset


@dataclass
class DriftDetectionMetrics:
    """Per-unit drift detection results with multi-dimensional signals."""

    unit_id: int
    n_cycles: int
    warning_cycle: Optional[int]
    lead_time_cycles: Optional[int]
    false_positive: bool
    mean_raw_drift: float
    mean_ema_drift: float
    max_raw_drift: float
    max_ema_drift: float
    # Component signals
    quantum_peak: float
    quantum_mean: float
    information_peak: float
    information_mean: float
    free_energy_peak: float
    free_energy_mean: float
    topological_peak: float
    topological_mean: float
    algorithmic_peak: float
    algorithmic_mean: float
    # Alert characteristics
    dominant_component: str
    n_state_changes: int
    first_warning_phase_cycle: Optional[int]


class EfficientDriftTestRunner:
    """Fast, memory-efficient drift detection test runner for CMAPSS."""

    def __init__(
        self,
        detector_config: Optional[DetectorConfig] = None,
        degradation_proxy_fraction: float = 0.1,
        healthy_fraction: float = 0.15,
        verbose: bool = False,
    ):
        """Initialize the test runner.

        Args:
            detector_config: DetectorConfig instance or None for defaults
            degradation_proxy_fraction: Fraction of cycles before failure for degradation onset
            healthy_fraction: Fraction of cycles considered healthy
            verbose: Enable detailed progress output
        """
        self.detector_config = detector_config or DetectorConfig()
        self.degradation_proxy_fraction = float(degradation_proxy_fraction)
        self.healthy_fraction = float(healthy_fraction)
        self.verbose = bool(verbose)
        self.detector = StructuralDriftDetector(self.detector_config)

    def run_fd004(
        self,
        dataset_path: Optional[str] = None,
        max_units: Optional[int] = None,
    ) -> Tuple[List[DriftDetectionMetrics], Dict]:
        """Run efficient drift detection on CMAPSS FD004.

        Args:
            dataset_path: Path to FD004 training data or None to auto-resolve
            max_units: Limit test to first N units (None for all)

        Returns:
            (list of DriftDetectionMetrics, summary dict)
        """
        start_time = time.time()

        # Load dataset
        if self.verbose:
            print("Loading CMAPSS FD004 dataset...")
        data_dict = load_cmapss_dataset("FD004", train_path=dataset_path)

        # Filter units if requested
        units = sorted(list(data_dict.keys()))[:max_units]
        if self.verbose:
            print(f"Processing {len(units)} units ({len(data_dict)} total available)")

        results: List[DriftDetectionMetrics] = []
        component_activations = {
            "quantum": 0,
            "information": 0,
            "free_energy": 0,
            "topological": 0,
            "algorithmic": 0,
        }

        for idx, unit_id in enumerate(units):
            if self.verbose:
                print(f"  [{idx+1}/{len(units)}] Unit {unit_id}...", end=" ")

            unit_data = data_dict[unit_id]
            metrics = self._process_single_unit(unit_id, unit_data)
            results.append(metrics)

            # Track component activation
            component_activations[metrics.dominant_component] += 1
            if self.verbose:
                print(f"warning_cycle={metrics.warning_cycle}, lead_time={metrics.lead_time_cycles}")

        elapsed = time.time() - start_time

        # Compute summary statistics
        summary = self._compute_summary(results, elapsed, len(data_dict), component_activations)

        if self.verbose:
            print(f"\nCompleted in {elapsed:.2f}s")
            print(self._format_summary(summary))

        return results, summary

    def _process_single_unit(self, unit_id: int, unit_data: np.ndarray) -> DriftDetectionMetrics:
        """Process a single unit and compute drift detection metrics.

        Args:
            unit_id: Unit identifier
            unit_data: 2D array of (n_cycles, 24) where columns are:
                       [cycle, op1, op2, op3, s1-s21]

        Returns:
            DriftDetectionMetrics with all component signals
        """
        # Extract sensor columns (skip cycle + 3 operating settings)
        sensors = unit_data[:, 4:]

        # Run detector
        scores = self.detector.process_unit(sensors)

        # Extract component signals
        component_data = {
            k: v for k, v in scores.component_scores.items()
            if k in ["quantum", "information", "free_energy", "topological", "algorithmic"]
        }

        # Compute early warning phase (first time any component activates above floor)
        fusion_floor = self.detector_config.fusion_activation_floor
        first_warning_phase = None
        for t, row_scores in enumerate(zip(*component_data.values())):
            if any(s >= fusion_floor for s in row_scores):
                first_warning_phase = t
                break

        # Degradation onset (walk-forward safe)
        n_cycles = len(sensors)
        degradation_onset = n_cycles - int(n_cycles * self.degradation_proxy_fraction)

        # Check if alert is false positive
        healthy_end = int(n_cycles * self.healthy_fraction)
        false_positive = (
            scores.warning_index is not None
            and scores.warning_index < healthy_end
        )

        # Compute lead time
        lead_time = None
        if scores.warning_index is not None and not false_positive:
            lead_time = degradation_onset - scores.warning_index
            if lead_time < 0:
                lead_time = None  # Alert after failure onset

        return DriftDetectionMetrics(
            unit_id=unit_id,
            n_cycles=n_cycles,
            warning_cycle=scores.warning_index,
            lead_time_cycles=lead_time,
            false_positive=false_positive,
            mean_raw_drift=float(np.mean(scores.raw_drift)),
            mean_ema_drift=float(np.mean(scores.ema_drift)),
            max_raw_drift=float(np.max(scores.raw_drift)),
            max_ema_drift=float(np.max(scores.ema_drift)),
            quantum_peak=float(np.max(component_data["quantum"])),
            quantum_mean=float(np.mean(component_data["quantum"])),
            information_peak=float(np.max(component_data["information"])),
            information_mean=float(np.mean(component_data["information"])),
            free_energy_peak=float(np.max(component_data["free_energy"])),
            free_energy_mean=float(np.mean(component_data["free_energy"])),
            topological_peak=float(np.max(component_data["topological"])),
            topological_mean=float(np.mean(component_data["topological"])),
            algorithmic_peak=float(np.max(component_data["algorithmic"])),
            algorithmic_mean=float(np.mean(component_data["algorithmic"])),
            dominant_component=scores.dominant_alert_component,
            n_state_changes=len(scores.alert_history),
            first_warning_phase_cycle=first_warning_phase,
        )

    def _compute_summary(
        self,
        results: List[DriftDetectionMetrics],
        elapsed: float,
        total_units: int,
        component_activations: Dict[str, int],
    ) -> Dict:
        """Compute summary statistics across all units."""
        valid_alerts = [r for r in results if r.warning_cycle is not None]
        valid_leads = [r.lead_time_cycles for r in valid_alerts if r.lead_time_cycles is not None]
        false_positives = [r for r in results if r.false_positive]

        return {
            "n_units_tested": len(results),
            "n_units_total": total_units,
            "detection_rate": len(valid_alerts) / len(results) if results else 0.0,
            "false_positive_rate": len(false_positives) / len(results) if results else 0.0,
            "mean_lead_time": float(np.mean(valid_leads)) if valid_leads else None,
            "median_lead_time": float(np.median(valid_leads)) if valid_leads else None,
            "min_lead_time": float(np.min(valid_leads)) if valid_leads else None,
            "max_lead_time": float(np.max(valid_leads)) if valid_leads else None,
            "mean_raw_drift": float(np.mean([r.mean_raw_drift for r in results])),
            "mean_ema_drift": float(np.mean([r.mean_ema_drift for r in results])),
            "component_activation_ranking": sorted(
                component_activations.items(),
                key=lambda x: x[1],
                reverse=True,
            ),
            "elapsed_seconds": elapsed,
            "throughput_units_per_second": len(results) / elapsed if elapsed > 0 else 0.0,
        }

    def _format_summary(self, summary: Dict) -> str:
        """Format summary as readable text."""
        lines = [
            "\n" + "=" * 60,
            "DRIFT DETECTION TEST SUMMARY (FD004)",
            "=" * 60,
            f"Units tested: {summary['n_units_tested']}/{summary['n_units_total']}",
            f"Detection rate: {summary['detection_rate']:.1%}",
            f"False positive rate: {summary['false_positive_rate']:.1%}",
        ]

        if summary["median_lead_time"] is not None:
            lines.extend([
                f"Median lead time: {summary['median_lead_time']:.0f} cycles",
                f"Lead time range: {summary['min_lead_time']:.0f} - {summary['max_lead_time']:.0f} cycles",
            ])

        lines.extend([
            f"Mean raw drift: {summary['mean_raw_drift']:.4f}",
            f"Mean EMA drift: {summary['mean_ema_drift']:.4f}",
            "Component activations: " + ", ".join(
                f"{k}={v}" for k, v in summary["component_activation_ranking"]
            ),
            f"Throughput: {summary['throughput_units_per_second']:.1f} units/sec",
            "=" * 60,
        ])
        return "\n".join(lines)

    def save_results(
        self,
        results: List[DriftDetectionMetrics],
        summary: Dict,
        output_dir: str = "drift_test_results",
    ) -> Dict[str, Path]:
        """Save results to CSV and JSON files.

        Args:
            results: List of DriftDetectionMetrics
            summary: Summary dictionary
            output_dir: Output directory path

        Returns:
            Dict mapping file type to Path
        """
        out_path = Path(output_dir)
        out_path.mkdir(exist_ok=True)

        paths = {}

        # Save detailed metrics as CSV
        csv_path = out_path / "fd004_drift_detection_results.csv"
        with open(csv_path, "w") as f:
            if results:
                keys = list(asdict(results[0]).keys())
                f.write(",".join(keys) + "\n")
                for r in results:
                    values = [str(asdict(r)[k]) for k in keys]
                    f.write(",".join(values) + "\n")
        paths["csv"] = csv_path

        # Save summary as JSON
        json_path = out_path / "fd004_drift_detection_summary.json"
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=2)
        paths["json"] = json_path

        return paths


def main():
    """Run the drift detection test runner on FD004 with all components."""
    runner = EfficientDriftTestRunner(verbose=True)
    results, summary = runner.run_fd004(max_units=None)
    runner.save_results(results, summary)


if __name__ == "__main__":
    main()
