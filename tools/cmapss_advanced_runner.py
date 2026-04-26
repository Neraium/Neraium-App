#!/usr/bin/env python3
"""
Advanced CMAPSS Validation Runner for Neraium Advanced SII Engine.

Integrates AdvancedSIIEngine with comprehensive detection metrics:
- Multi-scale drift analysis
- Novelty detection
- RUL estimation with confidence bounds
- Feature attribution (top sensors)
- Degradation mode classification
- Early warning indicators
- Ensemble agreement
- Cost-benefit analysis

Usage:
  python tools/cmapss_advanced_runner.py \\
    --data-dir /path/to/CMAPSSData \\
    --datasets FD001 FD002 FD003 FD004 \\
    --output validation_out_advanced \\
    --progress \\
    --system-type generic \\
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

from neraium_core.sii_engine_advanced import AdvancedSIIEngine, AdvancedSIIOutput, DegradationMode


@dataclass
class CMAPSSRow:
    """Parsed CMAPSS data row."""
    unit_id: int
    cycle: int
    setting_1: float
    setting_2: float
    setting_3: float
    sensors: List[float] = field(default_factory=list)

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
            sensors=values[5:26],
        )

    def to_sensor_vector(self) -> np.ndarray:
        """Convert to sensor vector for engine processing."""
        return np.array(self.sensors, dtype=float)


@dataclass
class AdvancedUnitResult:
    """Detection results with advanced metrics and audit trail for a single unit."""
    unit_id: int
    dataset: str
    cycles_observed: int
    baseline_samples_used: int
    failure_cycle: int
    first_alert_cycle: Optional[int] = None
    alert_cycle_type: Optional[str] = None
    alert_regime_at_detection: Optional[str] = None
    lead_time_cycles: Optional[int] = None
    detected: bool = False
    max_instability_score: float = 0.0
    instability_at_alert: float = 0.0
    warmup_cycles: int = 0
    error_message: Optional[str] = None
    was_insufficient_history: bool = False

    # Advanced metrics
    novelty_score: float = 0.0
    is_novel: bool = False
    degradation_mode: str = "unknown"
    top_sensors_str: str = ""  # JSON string of top 3 sensors
    rul_median_cycles: Optional[int] = None
    rul_p90_cycles: Optional[int] = None
    ensemble_agreement: float = 1.0
    maintenance_cost: float = 0.0
    failure_cost: float = 0.0
    recommended_action: str = ""

    # Audit trail fields
    alert_source: Optional[str] = None
    first_alert_reason: Optional[str] = None
    baseline_finalized_cycle: int = 0
    alert_before_baseline_finalized: bool = False
    warmup_alert: bool = False
    novelty_score_at_alert: float = 0.0
    ensemble_agreement_at_alert: float = 1.0
    degradation_mode_at_alert: str = "unknown"
    top_sensors_at_alert: str = ""  # JSON string
    rul_estimate_at_alert: str = ""  # JSON string


@dataclass
class AdvancedDatasetSummary:
    """Summary statistics for a dataset with advanced metrics and audit trail."""
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
    engine_version: str = "AdvancedSIIEngine"
    per_unit_results: List[AdvancedUnitResult] = field(default_factory=list)

    # Advanced metrics aggregates
    avg_novelty_score: float = 0.0
    novel_units_count: int = 0
    avg_ensemble_agreement: float = 0.0
    most_common_degradation_mode: str = ""

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


class AdvancedCMAPSSValidator:
    """Advanced CMAPSS validation runner using Advanced SII Engine."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        system_type: str = "generic",
        baseline_window: int = 50,
        min_baseline: int = 10,
        structural_drift_threshold: float = 0.5,
        progress: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.system_type = system_type
        self.baseline_window = baseline_window
        self.min_baseline = min_baseline
        self.structural_drift_threshold = structural_drift_threshold
        self.progress = progress and HAS_TQDM
        self.results: Dict[str, AdvancedDatasetSummary] = {}

    def run(self, datasets: List[str]) -> Dict[str, AdvancedDatasetSummary]:
        """Run validation across specified datasets."""
        print(f"🚀 Neraium Advanced SII Engine — CMAPSS Validation")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   System type: {self.system_type}")
        print(f"   Baseline window: {self.baseline_window} cycles (min: {self.min_baseline})")
        print()

        all_results = {}
        for dataset in datasets:
            print(f"📊 Processing dataset {dataset}...")
            summary = self._validate_dataset(dataset)
            all_results[dataset] = summary
            self.results[dataset] = summary
            self._print_dataset_summary(summary)
            print()

        self._write_outputs(all_results)
        self._print_combined_summary(all_results)

        return all_results

    def _validate_dataset(self, dataset: str) -> AdvancedDatasetSummary:
        """Validate a single dataset."""
        test_file = self.data_dir / f"test_{dataset}.txt"
        rul_file = self.data_dir / f"RUL_{dataset}.txt"

        if not test_file.exists() or not rul_file.exists():
            print(f"   ⚠️  Files not found: {test_file.name}, {rul_file.name}")
            return AdvancedDatasetSummary(
                dataset=dataset,
                units_total=0,
                baseline_window_configured=self.baseline_window,
                min_baseline_configured=self.min_baseline,
            )

        rul_map = self._load_rul_file(rul_file)
        units_data = self._load_test_file(test_file)

        summary = AdvancedDatasetSummary(
            dataset=dataset,
            units_total=len(units_data),
            baseline_window_configured=self.baseline_window,
            min_baseline_configured=self.min_baseline,
        )

        iterator = units_data.items()
        if self.progress:
            iterator = tqdm(
                iterator,
                desc=f"  {dataset}",
                total=len(units_data),
                unit="unit",
                leave=True,
            )

        for unit_id, cycles_data in iterator:
            result = self._process_unit(
                dataset=dataset,
                unit_id=unit_id,
                cycles_data=cycles_data,
                rul_value=rul_map.get(unit_id),
            )
            summary.per_unit_results.append(result)

            if result.error_message:
                summary.units_engine_error += 1
            elif result.was_insufficient_history:
                summary.units_insufficient_history += 1
            elif result.detected:
                summary.units_detected += 1
            else:
                summary.units_missed += 1

        self._compute_summary_metrics(summary)
        return summary

    def _process_unit(
        self,
        dataset: str,
        unit_id: int,
        cycles_data: List[CMAPSSRow],
        rul_value: Optional[int],
    ) -> AdvancedUnitResult:
        """Process a single unit through advanced engine."""
        if rul_value is None:
            rul_value = 0

        num_cycles = len(cycles_data)
        last_cycle = max(c.cycle for c in cycles_data)
        failure_cycle = last_cycle + rul_value

        try:
            # Create advanced engine per unit
            engine = AdvancedSIIEngine(
                baseline_window=self.baseline_window,
                recent_window=12,
                system_type=self.system_type,
            )

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
            alert_before_baseline = False
            is_warmup_alert = False

            last_output: Optional[AdvancedSIIOutput] = None
            alert_output: Optional[AdvancedSIIOutput] = None
            novelty_scores = []
            ensemble_agreements = []
            degradation_modes = []

            # Stream each cycle
            for row in cycles_data:
                sensor_vector = row.to_sensor_vector()
                timestamp = float(row.cycle)

                output = engine.update(sensor_vector, timestamp)
                last_output = output

                if output.regime == "WARMUP":
                    warmup_cycles += 1
                elif not baseline_was_ready and engine.baseline_ready:
                    baseline_finalized_cycle = row.cycle
                    baseline_was_ready = True
                else:
                    # Track advanced metrics
                    novelty_scores.append(output.novelty_score)
                    ensemble_agreements.append(output.ensemble_agreement)
                    degradation_modes.append(output.degradation_mode.value)

                max_instability = max(max_instability, output.instability_score)

                # Check for alert
                if first_alert_cycle is None and output.regime != "WARMUP":
                    is_alert = self._check_alert(output)
                    if is_alert:
                        first_alert_cycle = row.cycle
                        instability_at_alert = output.instability_score
                        alert_regime = output.regime
                        alert_cycle_type = self._get_alert_type(output)
                        alert_output = output  # Capture full output at alert time

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

                        # Check if alert came before baseline was finalized
                        alert_before_baseline = not baseline_was_ready
                        is_warmup_alert = output.regime == "WARMUP"

            baseline_used = engine.baseline.sample_count if engine.baseline.is_valid() else 0
            if not baseline_was_ready:
                baseline_finalized_cycle = warmup_cycles

            detected = first_alert_cycle is not None and first_alert_cycle < failure_cycle
            insufficient_history = not engine.baseline_ready and num_cycles < self.min_baseline

            lead_time = None
            if detected:
                lead_time = failure_cycle - first_alert_cycle

            # Extract advanced metrics
            novelty_score = float(np.mean(novelty_scores)) if novelty_scores else 0.0
            is_novel = novelty_score > 0.3
            ensemble_agreement = float(np.mean(ensemble_agreements)) if ensemble_agreements else 1.0

            # Most common degradation mode
            degradation_mode = "unknown"
            if degradation_modes:
                from collections import Counter
                mode_counts = Counter(degradation_modes)
                degradation_mode = mode_counts.most_common(1)[0][0]

            # Top sensors JSON
            top_sensors_str = ""
            rul_median = None
            rul_p90 = None
            maintenance_cost = 0.0
            failure_cost = 0.0
            recommended_action = ""

            # Audit metrics at alert time
            novelty_at_alert = 0.0
            ensemble_at_alert = 1.0
            mode_at_alert = "unknown"
            sensors_at_alert = ""
            rul_at_alert = ""

            if last_output and last_output.top_sensors:
                sensors_data = [
                    {
                        "sensor_id": s.sensor_id,
                        "contribution": round(float(s.contribution_to_instability), 4),
                        "health_score": round(float(s.health_score), 4),
                    }
                    for s in last_output.top_sensors[:3]
                ]
                top_sensors_str = json.dumps(sensors_data)

                if last_output.rul:
                    rul_median = last_output.rul.median_cycles
                    rul_p90 = last_output.rul.p90_cycles

                maintenance_cost = float(last_output.maintenance_cost)
                failure_cost = float(last_output.failure_cost)
                recommended_action = last_output.recommended_action

            # Capture metrics at alert time for audit trail
            if alert_output:
                novelty_at_alert = float(alert_output.novelty_score)
                ensemble_at_alert = float(alert_output.ensemble_agreement)
                mode_at_alert = alert_output.degradation_mode.value

                if alert_output.top_sensors:
                    sensors_alert_data = [
                        {
                            "sensor_id": s.sensor_id,
                            "contribution": round(float(s.contribution_to_instability), 4),
                            "health_score": round(float(s.health_score), 4),
                        }
                        for s in alert_output.top_sensors[:3]
                    ]
                    sensors_at_alert = json.dumps(sensors_alert_data)

                if alert_output.rul:
                    rul_alert_data = {
                        "median": alert_output.rul.median_cycles,
                        "p90": alert_output.rul.p90_cycles,
                        "confidence": round(float(alert_output.rul.confidence), 4),
                    }
                    rul_at_alert = json.dumps(rul_alert_data)

            return AdvancedUnitResult(
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
                novelty_score=novelty_score,
                is_novel=is_novel,
                degradation_mode=degradation_mode,
                top_sensors_str=top_sensors_str,
                rul_median_cycles=rul_median,
                rul_p90_cycles=rul_p90,
                ensemble_agreement=ensemble_agreement,
                maintenance_cost=maintenance_cost,
                failure_cost=failure_cost,
                recommended_action=recommended_action,
                # Audit fields
                alert_source=alert_source,
                first_alert_reason=alert_reason,
                baseline_finalized_cycle=baseline_finalized_cycle,
                alert_before_baseline_finalized=alert_before_baseline,
                warmup_alert=is_warmup_alert,
                novelty_score_at_alert=novelty_at_alert,
                ensemble_agreement_at_alert=ensemble_at_alert,
                degradation_mode_at_alert=mode_at_alert,
                top_sensors_at_alert=sensors_at_alert,
                rul_estimate_at_alert=rul_at_alert,
            )

        except Exception as e:
            import traceback
            return AdvancedUnitResult(
                unit_id=unit_id,
                dataset=dataset,
                cycles_observed=num_cycles,
                baseline_samples_used=0,
                failure_cycle=failure_cycle,
                detected=False,
                error_message=str(e)[:100],
            )

    def _check_alert(self, output: AdvancedSIIOutput) -> bool:
        """Check if alert condition met."""
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return True
        if output.urgency in ("ALERT", "CRITICAL"):
            return True
        if output.structural_drift >= self.structural_drift_threshold:
            return True
        return False

    def _get_alert_type(self, output: AdvancedSIIOutput) -> str:
        """Determine which alert mechanism triggered."""
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return "regime"
        if output.urgency in ("ALERT", "CRITICAL"):
            return "urgency"
        return "structural_drift"

    def _compute_summary_metrics(self, summary: AdvancedDatasetSummary) -> None:
        """Compute aggregate metrics."""
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

            # Advanced metrics aggregates
            novelty_scores = [r.novelty_score for r in summary.per_unit_results]
            if novelty_scores:
                summary.avg_novelty_score = float(np.mean(novelty_scores))

            summary.novel_units_count = sum(1 for r in summary.per_unit_results if r.is_novel)

            agreement_scores = [r.ensemble_agreement for r in summary.per_unit_results]
            if agreement_scores:
                summary.avg_ensemble_agreement = float(np.mean(agreement_scores))

            # Most common degradation mode
            from collections import Counter
            modes = [r.degradation_mode for r in summary.per_unit_results if r.degradation_mode != "unknown"]
            if modes:
                mode_counts = Counter(modes)
                summary.most_common_degradation_mode = mode_counts.most_common(1)[0][0]

            # Compute audit summary
            self._compute_audit_summary(summary)

    def _compute_audit_summary(self, summary: AdvancedDatasetSummary) -> None:
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
        """Load RUL file."""
        rul_map = {}
        with open(rul_file, "r") as f:
            for unit_id, line in enumerate(f, start=1):
                rul_map[unit_id] = int(float(line.strip()))
        return rul_map

    def _load_test_file(self, test_file: Path) -> Dict[int, List[CMAPSSRow]]:
        """Load test file and group by unit."""
        units_data = {}
        with open(test_file, "r") as f:
            for line in f:
                row = CMAPSSRow.parse(line)
                if row.unit_id not in units_data:
                    units_data[row.unit_id] = []
                units_data[row.unit_id].append(row)
        return units_data

    def _print_dataset_summary(self, summary: AdvancedDatasetSummary) -> None:
        """Print dataset summary."""
        print(f"\n   📈 {summary.dataset} Results:")
        print(f"      Total units: {summary.units_total}")
        print(f"      Detected: {summary.units_detected}/{summary.units_total} ({summary.detection_coverage_pct:.1f}%)")
        print(f"      Missed: {summary.units_missed}")
        print(f"      Insufficient history: {summary.units_insufficient_history}")
        print(f"      Engine errors: {summary.units_engine_error}")

        if summary.median_lead_time_cycles is not None:
            print(f"      Lead time: {summary.mean_lead_time_cycles:.1f}±{summary.median_lead_time_cycles:.1f} cycles")
            print(f"                (min: {summary.min_lead_time_cycles}, max: {summary.max_lead_time_cycles})")

        print(f"      Avg novelty score: {summary.avg_novelty_score:.4f}")
        print(f"      Novel units detected: {summary.novel_units_count}/{summary.units_total}")
        print(f"      Avg ensemble agreement: {summary.avg_ensemble_agreement:.4f}")
        if summary.most_common_degradation_mode:
            print(f"      Most common mode: {summary.most_common_degradation_mode}")

    def _print_combined_summary(self, all_results: Dict[str, AdvancedDatasetSummary]) -> None:
        """Print combined summary."""
        print("\n" + "=" * 70)
        print("📊 ADVANCED VALIDATION SUMMARY")
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

        all_lead_times = []
        for summary in all_results.values():
            all_lead_times.extend(
                [r.lead_time_cycles for r in summary.per_unit_results
                 if r.lead_time_cycles is not None and r.lead_time_cycles > 0]
            )

        if all_lead_times:
            print(f"\nOverall lead time:       {np.mean(all_lead_times):.1f} cycles (median: {np.median(all_lead_times):.1f})")
            print(f"                         (range: {int(np.min(all_lead_times))}-{int(np.max(all_lead_times))} cycles)")

        # Advanced aggregates
        all_novelty = [r.novelty_score for s in all_results.values() for r in s.per_unit_results]
        all_agreements = [r.ensemble_agreement for s in all_results.values() for r in s.per_unit_results]

        if all_novelty:
            print(f"\nAvg novelty score:       {np.mean(all_novelty):.4f}")
        if all_agreements:
            print(f"Avg ensemble agreement:  {np.mean(all_agreements):.4f}")

        print()

    def _write_outputs(self, all_results: Dict[str, AdvancedDatasetSummary]) -> None:
        """Write results to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for dataset, summary in all_results.items():
            dataset_dir = self.output_dir / dataset
            dataset_dir.mkdir(parents=True, exist_ok=True)

            self._write_per_unit_csv(dataset_dir / "per_unit_results.csv", summary)
            self._write_summary_json(dataset_dir / "summary.json", summary)

        self._write_combined_csv(self.output_dir / "all_datasets_summary.csv", all_results)
        self._write_combined_json(self.output_dir / "all_datasets_summary.json", all_results)

        print(f"\n✅ Results written to {self.output_dir}")

    def _write_per_unit_csv(self, filepath: Path, summary: AdvancedDatasetSummary) -> None:
        """Write per-unit CSV with advanced metrics and audit trail."""
        with open(filepath, "w") as f:
            f.write(
                "unit_id,cycles_observed,baseline_used,warmup_cycles,failure_cycle,"
                "first_alert_cycle,alert_type,alert_regime,lead_time_cycles,detected,"
                "max_instability,instability_at_alert,novelty_score,is_novel,"
                "degradation_mode,top_sensors,rul_median,rul_p90,ensemble_agreement,"
                "maintenance_cost,failure_cost,recommended_action,insufficient_history,error_message,"
                "alert_source,first_alert_reason,baseline_finalized_cycle,"
                "alert_before_baseline,warmup_alert,novelty_at_alert,ensemble_at_alert,"
                "mode_at_alert,sensors_at_alert,rul_at_alert\n"
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
                    f"{result.novelty_score:.4f},"
                    f"{result.is_novel},"
                    f"{result.degradation_mode},"
                    f"\"{result.top_sensors_str}\","
                    f"{result.rul_median_cycles or '-'},"
                    f"{result.rul_p90_cycles or '-'},"
                    f"{result.ensemble_agreement:.4f},"
                    f"{result.maintenance_cost:.2f},"
                    f"{result.failure_cost:.2f},"
                    f"\"{result.recommended_action}\","
                    f"{result.was_insufficient_history},"
                    f"\"{result.error_message or ''}\","
                    f"{result.alert_source or '-'},"
                    f"\"{result.first_alert_reason or ''}\","
                    f"{result.baseline_finalized_cycle},"
                    f"{result.alert_before_baseline_finalized},"
                    f"{result.warmup_alert},"
                    f"{result.novelty_score_at_alert:.4f},"
                    f"{result.ensemble_agreement_at_alert:.4f},"
                    f"{result.degradation_mode_at_alert},"
                    f"\"{result.top_sensors_at_alert}\","
                    f"\"{result.rul_estimate_at_alert}\"\n"
                )

    def _write_summary_json(self, filepath: Path, summary: AdvancedDatasetSummary) -> None:
        """Write dataset summary JSON with audit trail."""
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
            "avg_novelty_score": summary.avg_novelty_score,
            "novel_units_count": summary.novel_units_count,
            "avg_ensemble_agreement": summary.avg_ensemble_agreement,
            "most_common_degradation_mode": summary.most_common_degradation_mode,
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
        self, filepath: Path, all_results: Dict[str, AdvancedDatasetSummary]
    ) -> None:
        """Write combined summary CSV."""
        with open(filepath, "w") as f:
            f.write(
                "dataset,units_total,units_detected,units_missed,units_insufficient,"
                "units_error,coverage_pct,median_lead_time,mean_lead_time,min_lead_time,"
                "max_lead_time,avg_novelty,novel_count,avg_ensemble_agreement,"
                "most_common_mode\n"
            )
            for dataset in sorted(all_results.keys()):
                s = all_results[dataset]
                f.write(
                    f"{dataset},"
                    f"{s.units_total},"
                    f"{s.units_detected},"
                    f"{s.units_missed},"
                    f"{s.units_insufficient_history},"
                    f"{s.units_engine_error},"
                    f"{s.detection_coverage_pct:.1f},"
                    f"{s.median_lead_time_cycles or '-'},"
                    f"{s.mean_lead_time_cycles or '-'},"
                    f"{s.min_lead_time_cycles or '-'},"
                    f"{s.max_lead_time_cycles or '-'},"
                    f"{s.avg_novelty_score:.4f},"
                    f"{s.novel_units_count},"
                    f"{s.avg_ensemble_agreement:.4f},"
                    f"{s.most_common_degradation_mode}\n"
                )

    def _write_combined_json(
        self, filepath: Path, all_results: Dict[str, AdvancedDatasetSummary]
    ) -> None:
        """Write combined summary JSON."""
        summaries = []
        for dataset in sorted(all_results.keys()):
            s = all_results[dataset]
            summaries.append({
                "dataset": dataset,
                "units_total": s.units_total,
                "units_detected": s.units_detected,
                "units_missed": s.units_missed,
                "units_insufficient_history": s.units_insufficient_history,
                "units_engine_error": s.units_engine_error,
                "detection_coverage_pct": s.detection_coverage_pct,
                "median_lead_time_cycles": s.median_lead_time_cycles,
                "mean_lead_time_cycles": s.mean_lead_time_cycles,
                "min_lead_time_cycles": s.min_lead_time_cycles,
                "max_lead_time_cycles": s.max_lead_time_cycles,
                "avg_novelty_score": s.avg_novelty_score,
                "novel_units_count": s.novel_units_count,
                "avg_ensemble_agreement": s.avg_ensemble_agreement,
                "most_common_degradation_mode": s.most_common_degradation_mode,
            })

        total_units = sum(s.units_total for s in all_results.values())
        total_detected = sum(s.units_detected for s in all_results.values())
        overall_coverage = 100.0 * total_detected / total_units if total_units > 0 else 0.0

        data = {
            "total_units": total_units,
            "total_detected": total_detected,
            "overall_coverage_pct": overall_coverage,
            "datasets": summaries,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Advanced CMAPSS Validation Runner with Enhanced SII Engine"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing CMAPSS data files",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["FD001", "FD002", "FD003", "FD004"],
        help="Datasets to validate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation_out_advanced"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--system-type",
        type=str,
        default="generic",
        help="System type for adaptive thresholds",
    )
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=50,
        help="Baseline window size",
    )
    parser.add_argument(
        "--min-baseline",
        type=int,
        default=10,
        help="Minimum baseline samples",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        default=True,
        help="Show progress bars",
    )

    args = parser.parse_args()

    validator = AdvancedCMAPSSValidator(
        data_dir=args.data_dir,
        output_dir=args.output,
        system_type=args.system_type,
        baseline_window=args.baseline_window,
        min_baseline=args.min_baseline,
        progress=args.progress,
    )

    try:
        results = validator.run(args.datasets)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
