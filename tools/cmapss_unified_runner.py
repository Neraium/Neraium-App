#!/usr/bin/env python3
"""
Unified CMAPSS Validation Runner for Neraium SII Engine.

Measures early instability detection across NASA CMAPSS datasets FD001-FD004.
Properly handles short histories and provides comprehensive diagnostics.

Core metrics:
- first_alert_cycle: When engine first detects instability
- failure_cycle: Last observed cycle + RUL
- lead_time_cycles: failure_cycle - first_alert_cycle
- detection_coverage: Units detected / total units
- Diagnostics: insufficient_history, engine_errors, etc.

Usage:
  python tools/cmapss_unified_runner.py \\
    --data-dir /path/to/CMAPSSData \\
    --datasets FD001 FD002 FD003 FD004 \\
    --output validation_out \\
    --progress \\
    --baseline-window 50 \\
    --min-baseline 10
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import numpy as np

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from neraium_core.sii_engine_unified import SIIEngine, SIIEngineOutput


@dataclass
class CMAPSSRow:
    """Parsed CMAPSS data row."""
    unit_id: int
    cycle: int
    setting_1: float
    setting_2: float
    setting_3: float
    sensors: List[float] = field(default_factory=list)  # s1 through s21 (21 sensors)

    @staticmethod
    def parse(line: str) -> "CMAPSSRow":
        """Parse a single line from CMAPSS test file."""
        values = [float(x) for x in line.strip().split()]
        return CMAPSSRow(
            unit_id=int(values[0]),
            cycle=int(values[1]),
            setting_1=values[2],
            setting_2=values[3],
            setting_3=values[4],
            sensors=values[5:26],  # 21 sensors (s1-s21)
        )

    def to_sensor_vector(self) -> np.ndarray:
        """Convert to sensor vector for engine processing."""
        return np.array(self.sensors, dtype=float)


@dataclass
class UnitDetectionResult:
    """Detection results for a single test unit with audit trail."""
    unit_id: int
    dataset: str
    cycles_observed: int
    baseline_samples_used: int
    failure_cycle: int
    first_alert_cycle: Optional[int] = None
    alert_cycle_type: Optional[str] = None  # "regime", "urgency", "structural_drift"
    alert_regime_at_detection: Optional[str] = None
    lead_time_cycles: Optional[int] = None
    detected: bool = False
    max_instability_score: float = 0.0
    instability_at_alert: float = 0.0
    warmup_cycles: int = 0
    error_message: Optional[str] = None
    was_insufficient_history: bool = False

    # Audit trail fields
    alert_source: Optional[str] = None  # "regime", "urgency", or "structural_drift"
    first_alert_reason: Optional[str] = None  # Detailed reason (e.g., "regime=TRANSITION")
    baseline_finalized_cycle: int = 0  # Cycle when baseline was complete
    alert_before_baseline_finalized: bool = False  # Alert came before baseline ready?
    warmup_alert: bool = False  # Alert came during warmup?
    structural_drift_score_at_alert: float = 0.0  # Drift score when alert triggered
    state_at_alert: Optional[str] = None  # Full regime/urgency state at alert
    urgency_at_alert: Optional[str] = None  # Urgency level when alert triggered


@dataclass
class DatasetSummary:
    """Summary statistics for a dataset with audit trail."""
    dataset: str
    units_total: int = 0
    units_detected: int = 0
    units_missed: int = 0
    units_insufficient_history: int = 0
    units_engine_error: int = 0
    detection_coverage_pct: float = 0.0
    median_lead_time_cycles: Optional[float] = None
    mean_lead_time_cycles: Optional[float] = None
    min_lead_time_cycles: Optional[int] = None
    max_lead_time_cycles: Optional[int] = None
    baseline_window_configured: int = 50
    min_baseline_configured: int = 10
    engine_version: str = "SIIEngine Unified"
    per_unit_results: List[UnitDetectionResult] = field(default_factory=list)

    # Audit summary fields
    detections_by_regime: Dict[str, int] = field(default_factory=dict)
    detections_by_urgency: Dict[str, int] = field(default_factory=dict)
    detections_by_drift: int = 0
    alerts_in_first_5_cycles: int = 0
    alerts_in_first_10_cycles: int = 0
    alerts_in_first_20_cycles: int = 0
    alerts_before_baseline_finalized: int = 0
    warmup_alerts: int = 0
    median_lead_time_excl_early_alerts: Optional[float] = None
    median_lead_time_excl_prebaseline: Optional[float] = None


class CMAPSSValidator:
    """Unified CMAPSS validation runner using SII Engine."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        baseline_window: int = 50,
        min_baseline: int = 10,
        structural_drift_threshold: float = 0.5,
        progress: bool = True,
        plot: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.baseline_window = baseline_window
        self.min_baseline = min_baseline
        self.structural_drift_threshold = structural_drift_threshold
        self.progress = progress and HAS_TQDM
        self.plot = plot
        self.results: Dict[str, DatasetSummary] = {}

    def run(self, datasets: List[str]) -> Dict[str, DatasetSummary]:
        """Run validation across specified datasets."""
        print(f"🔬 Neraium SII Engine — CMAPSS Unified Validation")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Baseline window: {self.baseline_window} cycles (min: {self.min_baseline})")
        print(f"   Drift threshold: {self.structural_drift_threshold}")
        print()

        all_results = {}
        for dataset in datasets:
            print(f"📊 Processing dataset {dataset}...")
            summary = self._validate_dataset(dataset)
            all_results[dataset] = summary
            self.results[dataset] = summary
            self._print_dataset_summary(summary)
            print()

        # Write outputs
        self._write_outputs(all_results)
        self._print_combined_summary(all_results)

        return all_results

    def _validate_dataset(self, dataset: str) -> DatasetSummary:
        """Validate a single dataset (FD001-FD004)."""
        test_file = self.data_dir / f"test_{dataset}.txt"
        rul_file = self.data_dir / f"RUL_{dataset}.txt"

        if not test_file.exists() or not rul_file.exists():
            print(f"   ⚠️  Files not found: {test_file.name}, {rul_file.name}")
            return DatasetSummary(
                dataset=dataset,
                units_total=0,
                baseline_window_configured=self.baseline_window,
                min_baseline_configured=self.min_baseline,
            )

        # Load RUL values
        rul_map = self._load_rul_file(rul_file)

        # Load test data and group by unit
        units_data = self._load_test_file(test_file)

        summary = DatasetSummary(
            dataset=dataset,
            units_total=len(units_data),
            baseline_window_configured=self.baseline_window,
            min_baseline_configured=self.min_baseline,
        )

        # Create progress bar
        iterator = units_data.items()
        if self.progress:
            iterator = tqdm(
                iterator,
                desc=f"  {dataset}",
                total=len(units_data),
                unit="unit",
                leave=True,
            )

        # Process each unit
        for unit_id, cycles_data in iterator:
            result = self._process_unit(
                dataset=dataset,
                unit_id=unit_id,
                cycles_data=cycles_data,
                rul_value=rul_map.get(unit_id),
            )
            summary.per_unit_results.append(result)

            # Count outcomes
            if result.error_message:
                summary.units_engine_error += 1
            elif result.was_insufficient_history:
                summary.units_insufficient_history += 1
            elif result.detected:
                summary.units_detected += 1
            else:
                summary.units_missed += 1

        # Compute aggregate metrics
        self._compute_summary_metrics(summary)

        return summary

    def _process_unit(
        self,
        dataset: str,
        unit_id: int,
        cycles_data: List[CMAPSSRow],
        rul_value: Optional[int],
    ) -> UnitDetectionResult:
        """Process a single unit through the engine (one instance per unit)."""
        if rul_value is None:
            rul_value = 0

        num_cycles = len(cycles_data)

        # Calculate failure cycle
        last_cycle = max(c.cycle for c in cycles_data)
        failure_cycle = last_cycle + rul_value

        try:
            # Create one engine per unit
            engine = SIIEngine(baseline_window=self.baseline_window, recent_window=12)

            first_alert_cycle = None
            alert_cycle_type = None
            alert_regime = None
            alert_source = None
            alert_reason = None
            max_instability = 0.0
            instability_at_alert = 0.0
            warmup_cycles = 0
            baseline_used = 0
            baseline_finalized_cycle = 0
            baseline_was_ready = False
            drift_at_alert = 0.0
            urgency_at_alert = None
            alert_before_baseline = False
            is_warmup_alert = False

            # Stream each cycle through the same engine instance
            for row in cycles_data:
                sensor_vector = row.to_sensor_vector()
                timestamp = float(row.cycle)

                output = engine.update(sensor_vector, timestamp)

                # Track warmup
                if output.regime == "WARMUP":
                    warmup_cycles += 1
                elif not baseline_was_ready and engine.baseline_ready:
                    # Record when baseline was finalized
                    baseline_finalized_cycle = row.cycle
                    baseline_was_ready = True

                # Track max instability
                max_instability = max(max_instability, output.instability_score)

                # Check for alert (only after warmup, strict priority)
                if first_alert_cycle is None and output.regime != "WARMUP":
                    is_alert = self._check_alert(output)
                    if is_alert:
                        first_alert_cycle = row.cycle
                        instability_at_alert = output.instability_score
                        alert_regime = output.regime
                        alert_cycle_type = self._get_alert_type(output)
                        drift_at_alert = output.structural_drift
                        urgency_at_alert = output.urgency

                        # Determine alert source for audit
                        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
                            alert_source = "regime"
                            alert_reason = f"regime={output.regime}"
                        elif output.urgency in ("ALERT", "CRITICAL"):
                            alert_source = "urgency"
                            alert_reason = f"urgency={output.urgency}"
                        else:
                            alert_source = "structural_drift"
                            alert_reason = f"drift={output.structural_drift:.4f}"

                        # Check if this alert came before baseline was finalized
                        alert_before_baseline = not baseline_was_ready
                        is_warmup_alert = output.regime == "WARMUP"

            # If unit ended before baseline was ready, finalize it
            baseline_used = engine.baseline.sample_count if engine.baseline.is_valid() else 0
            if not baseline_was_ready:
                baseline_finalized_cycle = warmup_cycles

            # Determine if unit was detected
            detected = first_alert_cycle is not None and first_alert_cycle < failure_cycle

            # Check if insufficient history
            insufficient_history = not engine.baseline_ready and num_cycles < self.min_baseline

            # Calculate lead time
            lead_time = None
            if detected:
                lead_time = failure_cycle - first_alert_cycle

            return UnitDetectionResult(
                unit_id=unit_id,
                dataset=dataset,
                cycles_observed=num_cycles,
                baseline_samples_used=baseline_used,
                failure_cycle=failure_cycle,
                first_alert_cycle=first_alert_cycle,
                alert_cycle_type=alert_cycle_type,
                alert_regime_at_detection=alert_regime,
                lead_time_cycles=lead_time,
                detected=detected,
                max_instability_score=max_instability,
                instability_at_alert=instability_at_alert,
                warmup_cycles=warmup_cycles,
                was_insufficient_history=insufficient_history,
                # Audit fields
                alert_source=alert_source,
                first_alert_reason=alert_reason,
                baseline_finalized_cycle=baseline_finalized_cycle,
                alert_before_baseline_finalized=alert_before_baseline,
                warmup_alert=is_warmup_alert,
                structural_drift_score_at_alert=drift_at_alert,
                state_at_alert=alert_regime,
                urgency_at_alert=urgency_at_alert,
            )

        except Exception as e:
            # Capture any engine errors but continue
            return UnitDetectionResult(
                unit_id=unit_id,
                dataset=dataset,
                cycles_observed=num_cycles,
                baseline_samples_used=0,
                failure_cycle=failure_cycle,
                detected=False,
                error_message=str(e)[:100],
            )

    def _check_alert(self, output: SIIEngineOutput) -> bool:
        """Check if alert condition met (strict priority)."""
        # Priority 1: Regime indicating instability
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return True

        # Priority 2: Urgency indicating alert
        if output.urgency in ("ALERT", "CRITICAL"):
            return True

        # Priority 3: Structural drift threshold fallback (documented)
        if output.structural_drift >= self.structural_drift_threshold:
            return True

        return False

    def _get_alert_type(self, output: SIIEngineOutput) -> str:
        """Determine which alert mechanism triggered."""
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return "regime"
        if output.urgency in ("ALERT", "CRITICAL"):
            return "urgency"
        return "structural_drift"

    def _compute_summary_metrics(self, summary: DatasetSummary) -> None:
        """Compute aggregate metrics for dataset including audit trail."""
        if summary.per_unit_results:
            lead_times = [
                r.lead_time_cycles
                for r in summary.per_unit_results
                if r.lead_time_cycles is not None and r.lead_time_cycles > 0
            ]

            if lead_times:
                summary.median_lead_time_cycles = float(np.median(lead_times))
                summary.mean_lead_time_cycles = float(np.mean(lead_times))
                summary.min_lead_time_cycles = int(np.min(lead_times))
                summary.max_lead_time_cycles = int(np.max(lead_times))

            summary.detection_coverage_pct = (
                100.0 * summary.units_detected / summary.units_total
                if summary.units_total > 0
                else 0.0
            )

            # Compute audit summary
            self._compute_audit_summary(summary)

    def _compute_audit_summary(self, summary: DatasetSummary) -> None:
        """Compute audit trail statistics."""
        from collections import Counter

        for result in summary.per_unit_results:
            if not result.detected:
                continue

            # Count by alert source
            if result.alert_source == "regime":
                if result.state_at_alert not in summary.detections_by_regime:
                    summary.detections_by_regime[result.state_at_alert] = 0
                summary.detections_by_regime[result.state_at_alert] += 1
            elif result.alert_source == "urgency":
                if result.urgency_at_alert not in summary.detections_by_urgency:
                    summary.detections_by_urgency[result.urgency_at_alert] = 0
                summary.detections_by_urgency[result.urgency_at_alert] += 1
            elif result.alert_source == "structural_drift":
                summary.detections_by_drift += 1

            # Count early alerts
            if result.first_alert_cycle and result.first_alert_cycle <= 5:
                summary.alerts_in_first_5_cycles += 1
            if result.first_alert_cycle and result.first_alert_cycle <= 10:
                summary.alerts_in_first_10_cycles += 1
            if result.first_alert_cycle and result.first_alert_cycle <= 20:
                summary.alerts_in_first_20_cycles += 1

            # Count suspicious alerts
            if result.alert_before_baseline_finalized:
                summary.alerts_before_baseline_finalized += 1
            if result.warmup_alert:
                summary.warmup_alerts += 1

        # Compute lead times excluding early/suspicious alerts
        lead_times_no_early = [
            r.lead_time_cycles
            for r in summary.per_unit_results
            if r.lead_time_cycles is not None and r.lead_time_cycles > 0
            and (r.first_alert_cycle is None or r.first_alert_cycle > 20)
        ]
        if lead_times_no_early:
            summary.median_lead_time_excl_early_alerts = float(np.median(lead_times_no_early))

        lead_times_no_prebaseline = [
            r.lead_time_cycles
            for r in summary.per_unit_results
            if r.lead_time_cycles is not None and r.lead_time_cycles > 0
            and not r.alert_before_baseline_finalized
        ]
        if lead_times_no_prebaseline:
            summary.median_lead_time_excl_prebaseline = float(np.median(lead_times_no_prebaseline))

    def _load_rul_file(self, rul_file: Path) -> Dict[int, int]:
        """Load RUL file and map unit_id -> RUL value."""
        rul_map = {}
        with open(rul_file, "r") as f:
            for unit_id, line in enumerate(f, start=1):
                rul_map[unit_id] = int(float(line.strip()))
        return rul_map

    def _load_test_file(self, test_file: Path) -> Dict[int, List[CMAPSSRow]]:
        """Load test file and group by unit_id."""
        units_data = {}
        with open(test_file, "r") as f:
            for line in f:
                row = CMAPSSRow.parse(line)
                if row.unit_id not in units_data:
                    units_data[row.unit_id] = []
                units_data[row.unit_id].append(row)
        return units_data

    def _print_dataset_summary(self, summary: DatasetSummary) -> None:
        """Print summary for dataset to console."""
        print(f"\n   📈 {summary.dataset} Results:")
        print(f"      Total units: {summary.units_total}")
        print(f"      Detected: {summary.units_detected}/{summary.units_total} ({summary.detection_coverage_pct:.1f}%)")
        print(f"      Missed: {summary.units_missed}")
        print(f"      Insufficient history: {summary.units_insufficient_history}")
        print(f"      Engine errors: {summary.units_engine_error}")

        if summary.median_lead_time_cycles is not None:
            print(f"      Lead time: {summary.mean_lead_time_cycles:.1f}±{summary.median_lead_time_cycles:.1f} cycles")
            print(f"                (min: {summary.min_lead_time_cycles}, max: {summary.max_lead_time_cycles})")

    def _print_combined_summary(self, all_results: Dict[str, DatasetSummary]) -> None:
        """Print combined summary across all datasets."""
        print("\n" + "=" * 70)
        print("📊 COMBINED SUMMARY")
        print("=" * 70)

        total_units = sum(s.units_total for s in all_results.values())
        total_detected = sum(s.units_detected for s in all_results.values())
        total_insufficient = sum(s.units_insufficient_history for s in all_results.values())
        total_errors = sum(s.units_engine_error for s in all_results.values())
        overall_coverage = 100.0 * total_detected / total_units if total_units > 0 else 0.0

        print(f"\nTotal units:              {total_units}")
        print(f"  Detected:              {total_detected} ({overall_coverage:.1f}%)")
        print(f"  Missed:                {total_units - total_detected - total_insufficient - total_errors}")
        print(f"  Insufficient history:  {total_insufficient}")
        print(f"  Engine errors:         {total_errors}")

        # All lead times
        all_lead_times = []
        for summary in all_results.values():
            all_lead_times.extend(
                [r.lead_time_cycles for r in summary.per_unit_results if r.lead_time_cycles is not None and r.lead_time_cycles > 0]
            )

        if all_lead_times:
            print(f"\nOverall lead time:       {np.mean(all_lead_times):.1f} cycles (median: {np.median(all_lead_times):.1f})")
            print(f"                         (range: {int(np.min(all_lead_times))}-{int(np.max(all_lead_times))} cycles)")

        print()

    def _write_outputs(self, all_results: Dict[str, DatasetSummary]) -> None:
        """Write results to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Per-dataset outputs
        for dataset, summary in all_results.items():
            dataset_dir = self.output_dir / dataset
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Write per-unit CSV
            self._write_per_unit_csv(dataset_dir / "per_unit_results.csv", summary)

            # Write summary JSON
            self._write_summary_json(dataset_dir / "summary.json", summary)

        # Combined summaries
        self._write_combined_csv(self.output_dir / "all_datasets_summary.csv", all_results)
        self._write_combined_json(self.output_dir / "all_datasets_summary.json", all_results)

        print(f"\n✅ Results written to {self.output_dir}")

    def _write_per_unit_csv(self, filepath: Path, summary: DatasetSummary) -> None:
        """Write per-unit results to CSV with audit trail."""
        with open(filepath, "w") as f:
            f.write(
                "unit_id,cycles_observed,baseline_used,warmup_cycles,failure_cycle,"
                "first_alert_cycle,alert_type,alert_regime,lead_time_cycles,detected,"
                "max_instability,instability_at_alert,insufficient_history,error_message,"
                "alert_source,first_alert_reason,baseline_finalized_cycle,"
                "alert_before_baseline,warmup_alert,drift_at_alert,state_at_alert,urgency_at_alert\n"
            )
            for result in summary.per_unit_results:
                f.write(
                    f"{result.unit_id},"
                    f"{result.cycles_observed},"
                    f"{result.baseline_samples_used},"
                    f"{result.warmup_cycles},"
                    f"{result.failure_cycle},"
                    f"{result.first_alert_cycle or '-'},"
                    f"{result.alert_cycle_type or '-'},"
                    f"{result.alert_regime_at_detection or '-'},"
                    f"{result.lead_time_cycles or '-'},"
                    f"{result.detected},"
                    f"{result.max_instability_score:.4f},"
                    f"{result.instability_at_alert:.4f},"
                    f"{result.was_insufficient_history},"
                    f"\"{result.error_message or ''}\","
                    f"{result.alert_source or '-'},"
                    f"\"{result.first_alert_reason or ''}\","
                    f"{result.baseline_finalized_cycle},"
                    f"{result.alert_before_baseline_finalized},"
                    f"{result.warmup_alert},"
                    f"{result.structural_drift_score_at_alert:.4f},"
                    f"{result.state_at_alert or '-'},"
                    f"{result.urgency_at_alert or '-'}\n"
                )

    def _write_summary_json(self, filepath: Path, summary: DatasetSummary) -> None:
        """Write dataset summary to JSON."""
        data = {
            "dataset": summary.dataset,
            "units_total": summary.units_total,
            "units_detected": summary.units_detected,
            "units_missed": summary.units_missed,
            "units_insufficient_history": summary.units_insufficient_history,
            "units_engine_error": summary.units_engine_error,
            "detection_coverage_pct": summary.detection_coverage_pct,
            "median_lead_time_cycles": summary.median_lead_time_cycles,
            "mean_lead_time_cycles": summary.mean_lead_time_cycles,
            "min_lead_time_cycles": summary.min_lead_time_cycles,
            "max_lead_time_cycles": summary.max_lead_time_cycles,
            "baseline_window_configured": summary.baseline_window_configured,
            "min_baseline_configured": summary.min_baseline_configured,
            "engine_version": summary.engine_version,
            # Audit summary
            "audit": {
                "detections_by_regime": summary.detections_by_regime,
                "detections_by_urgency": summary.detections_by_urgency,
                "detections_by_drift_threshold": summary.detections_by_drift,
                "alerts_in_first_5_cycles": summary.alerts_in_first_5_cycles,
                "alerts_in_first_10_cycles": summary.alerts_in_first_10_cycles,
                "alerts_in_first_20_cycles": summary.alerts_in_first_20_cycles,
                "alerts_before_baseline_finalized": summary.alerts_before_baseline_finalized,
                "warmup_alerts": summary.warmup_alerts,
                "median_lead_time_excl_early_alerts": summary.median_lead_time_excl_early_alerts,
                "median_lead_time_excl_prebaseline": summary.median_lead_time_excl_prebaseline,
            }
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def _write_combined_csv(
        self, filepath: Path, all_results: Dict[str, DatasetSummary]
    ) -> None:
        """Write combined summary to CSV."""
        with open(filepath, "w") as f:
            f.write(
                "dataset,units_total,units_detected,units_missed,units_insufficient,"
                "units_error,coverage_pct,median_lead_time,mean_lead_time,min_lead_time,"
                "max_lead_time\n"
            )
            for dataset in sorted(all_results.keys()):
                summary = all_results[dataset]
                f.write(
                    f"{dataset},"
                    f"{summary.units_total},"
                    f"{summary.units_detected},"
                    f"{summary.units_missed},"
                    f"{summary.units_insufficient_history},"
                    f"{summary.units_engine_error},"
                    f"{summary.detection_coverage_pct:.1f},"
                    f"{summary.median_lead_time_cycles or '-'},"
                    f"{summary.mean_lead_time_cycles or '-'},"
                    f"{summary.min_lead_time_cycles or '-'},"
                    f"{summary.max_lead_time_cycles or '-'}\n"
                )

    def _write_combined_json(
        self, filepath: Path, all_results: Dict[str, DatasetSummary]
    ) -> None:
        """Write combined summary to JSON."""
        summaries = {}
        for dataset, summary in all_results.items():
            summaries[dataset] = {
                "units_total": summary.units_total,
                "units_detected": summary.units_detected,
                "units_missed": summary.units_missed,
                "units_insufficient_history": summary.units_insufficient_history,
                "units_engine_error": summary.units_engine_error,
                "detection_coverage_pct": summary.detection_coverage_pct,
                "median_lead_time_cycles": summary.median_lead_time_cycles,
                "mean_lead_time_cycles": summary.mean_lead_time_cycles,
                "min_lead_time_cycles": summary.min_lead_time_cycles,
                "max_lead_time_cycles": summary.max_lead_time_cycles,
                "baseline_window_configured": summary.baseline_window_configured,
                "min_baseline_configured": summary.min_baseline_configured,
            }

        with open(filepath, "w") as f:
            json.dump(summaries, f, indent=2)


def main():
    """Parse arguments and run validation."""
    parser = argparse.ArgumentParser(
        description="Unified CMAPSS validation runner for Neraium SII Engine"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Path to directory containing CMAPSS test/RUL files",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["FD001", "FD002", "FD003", "FD004"],
        help="Datasets to validate (default: FD001 FD002 FD003 FD004)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation_out"),
        help="Output directory (default: validation_out)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar (requires tqdm)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate per-unit drift/alert plots (optional)",
    )
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=50,
        help="Baseline window size for engine (default: 50)",
    )
    parser.add_argument(
        "--min-baseline",
        type=int,
        default=10,
        help="Minimum baseline samples required (default: 10)",
    )
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.5,
        help="Structural drift threshold for alert (default: 0.5)",
    )

    args = parser.parse_args()

    try:
        validator = CMAPSSValidator(
            data_dir=args.data_dir,
            output_dir=args.output,
            baseline_window=args.baseline_window,
            min_baseline=args.min_baseline,
            structural_drift_threshold=args.drift_threshold,
            progress=args.progress,
            plot=args.plot,
        )
        results = validator.run(args.datasets)
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
