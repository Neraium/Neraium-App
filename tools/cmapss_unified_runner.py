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

    # Confirmed detection fields
    first_raw_alert_cycle: Optional[int] = None
    first_confirmed_alert_cycle: Optional[int] = None
    raw_alert_count_at_confirmation: int = 0
    rolling_instability_at_confirmation: float = 0.0
    confirmation_method: Optional[str] = None  # "persistence" or "accumulation"
    post_baseline_gap: int = 0  # Cycles after baseline finalization before confirmation
    confirmed_detected: bool = False

    # Score diagnostics at confirmation
    drift_score_at_confirmation: float = 0.0  # S(t): structural drift when confirmed
    inevitability_score_at_confirmation: float = 0.0  # I(t): inevitable score when confirmed
    irreversibility_factor_at_confirmation: float = 0.0  # R(t): irreversibility factor when confirmed


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
        inevitability_threshold: float = 0.6,
        progress: bool = True,
        plot: bool = False,
        confirmation_hits: int = 3,
        confirmation_window: int = 5,
        post_baseline_delay: int = 10,
        accumulation_window: int = 5,
        accumulation_threshold: float = 1.75,
        use_inevitability_score: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.baseline_window = baseline_window
        self.min_baseline = min_baseline
        self.structural_drift_threshold = structural_drift_threshold
        self.inevitability_threshold = inevitability_threshold
        self.progress = progress and HAS_TQDM
        self.plot = plot
        self.confirmation_hits = confirmation_hits
        self.confirmation_window = confirmation_window
        self.post_baseline_delay = post_baseline_delay
        self.accumulation_window = accumulation_window
        self.accumulation_threshold = accumulation_threshold
        self.use_inevitability_score = use_inevitability_score
        self.results: Dict[str, DatasetSummary] = {}

    def run(self, datasets: List[str]) -> Dict[str, DatasetSummary]:
        """Run validation across specified datasets."""
        print(f"🔬 Neraium SII Engine — CMAPSS Unified Validation")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Baseline window: {self.baseline_window} cycles (min: {self.min_baseline})")
        print(f"   Drift threshold: {self.structural_drift_threshold}")
        print(f"   Inevitability threshold: {self.inevitability_threshold}")
        print(f"\n   🔧 Confirmation Settings:")
        print(f"      confirmation_hits: {self.confirmation_hits}")
        print(f"      confirmation_window: {self.confirmation_window}")
        print(f"      post_baseline_delay: {self.post_baseline_delay}")
        print(f"      accumulation_window: {self.accumulation_window}")
        print(f"      accumulation_threshold: {self.accumulation_threshold}")
        print(f"      use_inevitability_score: {self.use_inevitability_score}")
        if self.use_inevitability_score:
            print(f"      (irreversibility_factor must be >= {self.inevitability_threshold} to confirm)")
            print(f"      (confirmation requires BOTH persistence/accumulation AND irreversibility)")
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

            # Raw alert tracking
            first_raw_alert_cycle = None
            first_confirmed_alert_cycle = None
            raw_alert_history = {}  # cycle -> is_raw_alert
            drift_score_history = {}  # cycle -> drift_score
            engine_output_history = {}  # cycle -> full output for score diagnostics

            max_instability = 0.0
            warmup_cycles = 0
            baseline_used = 0
            baseline_finalized_cycle = 0
            baseline_was_ready = False

            # Stream each cycle through the same engine instance
            for row in cycles_data:
                sensor_vector = row.to_sensor_vector()
                timestamp = float(row.cycle)

                output = engine.update(sensor_vector, timestamp)
                current_cycle = row.cycle

                # Track warmup
                if output.regime == "WARMUP":
                    warmup_cycles += 1
                elif not baseline_was_ready and engine.baseline_ready:
                    baseline_finalized_cycle = row.cycle
                    baseline_was_ready = True

                # Track max instability
                max_instability = max(max_instability, output.instability_score)

                # Store drift/inevitability score for accumulation calculation
                if self.use_inevitability_score:
                    drift_score_history[current_cycle] = output.structural_inevitability_score
                else:
                    drift_score_history[current_cycle] = output.structural_drift

                # Store full output for diagnostics
                engine_output_history[current_cycle] = output

                # Check for raw alert (after warmup only)
                if output.regime != "WARMUP":
                    is_raw_alert = self._check_raw_alert(output)
                    raw_alert_history[current_cycle] = is_raw_alert

                    if is_raw_alert and first_raw_alert_cycle is None:
                        first_raw_alert_cycle = current_cycle

            # If unit ended before baseline was ready, finalize it
            baseline_used = engine.baseline.sample_count if engine.baseline.is_valid() else 0
            if not baseline_was_ready:
                baseline_finalized_cycle = warmup_cycles

            # Compute confirmed alerts using persistence and accumulation logic
            first_confirmed_alert_cycle = None
            confirmation_method = None
            raw_alert_count_at_confirmation = 0
            rolling_instability_at_confirmation = 0.0
            drift_score_at_confirmation = 0.0
            inevitability_score_at_confirmation = 0.0
            irreversibility_factor_at_confirmation = 0.0

            for cycle in sorted(raw_alert_history.keys()):
                # Check if we can confirm alerts at this cycle
                if cycle < baseline_finalized_cycle + self.post_baseline_delay:
                    continue

                # Check persistence: raw_alert_count in last confirmation_window
                raw_alerts_in_window = sum(
                    1 for c in raw_alert_history.keys()
                    if (cycle - self.confirmation_window < c <= cycle) and raw_alert_history[c]
                )

                # Check accumulation: rolling sum of drift scores
                rolling_instability = sum(
                    drift_score_history.get(c, 0.0)
                    for c in drift_score_history.keys()
                    if (cycle - self.accumulation_window < c <= cycle)
                )

                # Capture scores at confirmation for diagnostics
                cycle_output = engine_output_history.get(cycle)
                if cycle_output:
                    drift_score_at_confirmation = cycle_output.structural_drift
                    inevitability_score_at_confirmation = cycle_output.structural_inevitability_score
                    irreversibility_factor_at_confirmation = cycle_output.irreversibility_factor

                # Irreversibility gate: if using inevitability mode, require R(t) >= threshold
                # This ensures confirmation requires BOTH persistence/accumulation AND irreversibility
                if self.use_inevitability_score and cycle_output:
                    irreversibility_gate_met = cycle_output.irreversibility_factor >= self.inevitability_threshold
                else:
                    irreversibility_gate_met = True  # No gate in legacy mode

                # Determine confirmation (with optional irreversibility gate)
                if irreversibility_gate_met:
                    if raw_alerts_in_window >= self.confirmation_hits:
                        first_confirmed_alert_cycle = cycle
                        confirmation_method = "persistence"
                        raw_alert_count_at_confirmation = raw_alerts_in_window
                        rolling_instability_at_confirmation = rolling_instability
                        break
                    elif rolling_instability >= self.accumulation_threshold:
                        first_confirmed_alert_cycle = cycle
                        confirmation_method = "accumulation"
                        raw_alert_count_at_confirmation = raw_alerts_in_window
                        rolling_instability_at_confirmation = rolling_instability
                        break

            # Determine confirmed detection
            confirmed_detected = (
                first_confirmed_alert_cycle is not None
                and first_confirmed_alert_cycle < failure_cycle
            )

            # Calculate lead time from first confirmed alert
            lead_time = None
            if confirmed_detected:
                lead_time = failure_cycle - first_confirmed_alert_cycle
                # Safety check: if lead_time is negative, mark as missed
                if lead_time < 0:
                    confirmed_detected = False
                    lead_time = None

            # Calculate post_baseline_gap
            post_baseline_gap = 0
            if first_confirmed_alert_cycle is not None:
                post_baseline_gap = first_confirmed_alert_cycle - baseline_finalized_cycle

            # Check if insufficient history
            insufficient_history = not engine.baseline_ready and num_cycles < self.min_baseline

            return UnitDetectionResult(
                unit_id=unit_id,
                dataset=dataset,
                cycles_observed=num_cycles,
                baseline_samples_used=baseline_used,
                failure_cycle=failure_cycle,
                first_alert_cycle=first_raw_alert_cycle,  # Keep raw alert for compatibility
                alert_cycle_type=None,
                alert_regime_at_detection=None,
                lead_time_cycles=lead_time,
                detected=confirmed_detected,  # Now means confirmed_detected
                max_instability_score=max_instability,
                instability_at_alert=0.0,
                warmup_cycles=warmup_cycles,
                was_insufficient_history=insufficient_history,
                # Audit fields (legacy for compatibility)
                alert_source=None,
                first_alert_reason=None,
                baseline_finalized_cycle=baseline_finalized_cycle,
                alert_before_baseline_finalized=False,
                warmup_alert=False,
                structural_drift_score_at_alert=0.0,
                state_at_alert=None,
                urgency_at_alert=None,
                # New confirmed detection fields
                first_raw_alert_cycle=first_raw_alert_cycle,
                first_confirmed_alert_cycle=first_confirmed_alert_cycle,
                raw_alert_count_at_confirmation=raw_alert_count_at_confirmation,
                rolling_instability_at_confirmation=rolling_instability_at_confirmation,
                confirmation_method=confirmation_method,
                post_baseline_gap=post_baseline_gap,
                confirmed_detected=confirmed_detected,
                # Score diagnostics
                drift_score_at_confirmation=drift_score_at_confirmation,
                inevitability_score_at_confirmation=inevitability_score_at_confirmation,
                irreversibility_factor_at_confirmation=irreversibility_factor_at_confirmation,
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
                confirmed_detected=False,
                error_message=str(e)[:100],
            )

    def _check_raw_alert(self, output: SIIEngineOutput) -> bool:
        """Check if raw alert condition met (before confirmation)."""
        # Check regime for instability
        if output.regime in ("TRANSITION", "UNSTABLE", "DEGRADED", "FAILURE"):
            return True

        # Check urgency for alert conditions
        if output.urgency in ("WATCH", "ALERT", "CRITICAL"):
            return True

        # Check structural drift/inevitability threshold based on mode
        if self.use_inevitability_score:
            # Use inevitability score with dedicated threshold
            if output.structural_inevitability_score >= self.inevitability_threshold:
                return True
        else:
            # Use traditional structural drift with drift threshold
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
        """Compute aggregate metrics for dataset using confirmed detections."""
        if summary.per_unit_results:
            # Use confirmed detections only
            lead_times = [
                r.lead_time_cycles
                for r in summary.per_unit_results
                if r.confirmed_detected and r.lead_time_cycles is not None and r.lead_time_cycles > 0
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
        """Compute audit trail statistics using confirmed detections."""
        from collections import Counter

        for result in summary.per_unit_results:
            if not result.confirmed_detected:
                continue

            # Count by confirmation method
            if result.confirmation_method == "persistence":
                if "persistence" not in summary.detections_by_regime:
                    summary.detections_by_regime["persistence"] = 0
                summary.detections_by_regime["persistence"] += 1
            elif result.confirmation_method == "accumulation":
                summary.detections_by_drift += 1

            # Count early confirmed alerts
            if result.first_confirmed_alert_cycle and result.first_confirmed_alert_cycle <= 5:
                summary.alerts_in_first_5_cycles += 1
            if result.first_confirmed_alert_cycle and result.first_confirmed_alert_cycle <= 10:
                summary.alerts_in_first_10_cycles += 1
            if result.first_confirmed_alert_cycle and result.first_confirmed_alert_cycle <= 20:
                summary.alerts_in_first_20_cycles += 1

        # Compute lead times excluding early confirmed alerts
        lead_times_no_early = [
            r.lead_time_cycles
            for r in summary.per_unit_results
            if r.confirmed_detected and r.lead_time_cycles is not None and r.lead_time_cycles > 0
            and (r.first_confirmed_alert_cycle is None or r.first_confirmed_alert_cycle > 20)
        ]
        if lead_times_no_early:
            summary.median_lead_time_excl_early_alerts = float(np.median(lead_times_no_early))

        lead_times_no_prebaseline = [
            r.lead_time_cycles
            for r in summary.per_unit_results
            if r.confirmed_detected and r.lead_time_cycles is not None and r.lead_time_cycles > 0
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
        """Write per-unit results to CSV with audit trail and confirmation diagnostics."""
        with open(filepath, "w") as f:
            f.write(
                "unit_id,cycles_observed,baseline_used,warmup_cycles,failure_cycle,"
                "first_raw_alert_cycle,first_confirmed_alert_cycle,lead_time_cycles,"
                "confirmed_detected,raw_alert_count_at_confirmation,rolling_instability_at_confirmation,"
                "confirmation_method,post_baseline_gap,baseline_finalized_cycle,"
                "drift_score_at_confirmation,inevitability_score_at_confirmation,irreversibility_factor_at_confirmation,"
                "max_instability,insufficient_history,error_message\n"
            )
            for result in summary.per_unit_results:
                f.write(
                    f"{result.unit_id},"
                    f"{result.cycles_observed},"
                    f"{result.baseline_samples_used},"
                    f"{result.warmup_cycles},"
                    f"{result.failure_cycle},"
                    f"{result.first_raw_alert_cycle or '-'},"
                    f"{result.first_confirmed_alert_cycle or '-'},"
                    f"{result.lead_time_cycles or '-'},"
                    f"{result.confirmed_detected},"
                    f"{result.raw_alert_count_at_confirmation},"
                    f"{result.rolling_instability_at_confirmation:.4f},"
                    f"{result.confirmation_method or '-'},"
                    f"{result.post_baseline_gap},"
                    f"{result.baseline_finalized_cycle},"
                    f"{result.drift_score_at_confirmation:.4f},"
                    f"{result.inevitability_score_at_confirmation:.4f},"
                    f"{result.irreversibility_factor_at_confirmation:.4f},"
                    f"{result.max_instability_score:.4f},"
                    f"{result.was_insufficient_history},"
                    f"\"{result.error_message or ''}\"\n"
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
    parser.add_argument(
        "--inevitability-threshold",
        type=float,
        default=0.6,
        help="Structural inevitability threshold when using --use-inevitability-score (default: 0.6)",
    )
    parser.add_argument(
        "--confirmation-hits",
        type=int,
        default=3,
        help="Number of raw alerts required for persistence confirmation (default: 3)",
    )
    parser.add_argument(
        "--confirmation-window",
        type=int,
        default=5,
        help="Cycle window for persistence confirmation (default: 5)",
    )
    parser.add_argument(
        "--post-baseline-delay",
        type=int,
        default=10,
        help="Cycles to wait after baseline finalization before confirming (default: 10)",
    )
    parser.add_argument(
        "--accumulation-window",
        type=int,
        default=5,
        help="Cycle window for accumulation sum (default: 5)",
    )
    parser.add_argument(
        "--accumulation-threshold",
        type=float,
        default=1.75,
        help="Drift accumulation threshold for confirmation (default: 1.75)",
    )
    parser.add_argument(
        "--use-inevitability-score",
        action="store_true",
        help="Use structural inevitability score (S * R) instead of raw drift for confirmation logic",
    )

    args = parser.parse_args()

    try:
        validator = CMAPSSValidator(
            data_dir=args.data_dir,
            output_dir=args.output,
            baseline_window=args.baseline_window,
            min_baseline=args.min_baseline,
            structural_drift_threshold=args.drift_threshold,
            inevitability_threshold=args.inevitability_threshold,
            progress=args.progress,
            plot=args.plot,
            confirmation_hits=args.confirmation_hits,
            confirmation_window=args.confirmation_window,
            post_baseline_delay=args.post_baseline_delay,
            accumulation_window=args.accumulation_window,
            accumulation_threshold=args.accumulation_threshold,
            use_inevitability_score=args.use_inevitability_score,
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
