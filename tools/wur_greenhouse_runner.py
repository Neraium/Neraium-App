#!/usr/bin/env python3
"""
WUR Autonomous Greenhouse Validation Runner for Neraium Advanced SII Engine.

Performs unsupervised telemetry validation on greenhouse climate data using
the AdvancedSIIEngine to detect environmental instability, control drift,
and anomalies. Designed for exploratory and operational monitoring.

Assumes ~5-minute sampling interval:
  - 288 samples ≈ 24 hours
  - 48 samples ≈ 4 hours

Usage:
  python tools/wur_greenhouse_runner.py \\
    --data-dir path/to/iGrow \\
    --output greenhouse_validation_results \\
    --progress \\
    --baseline-window 288 \\
    --min-baseline 48 \\
    --plot
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import numpy as np
import pandas as pd

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from neraium_core.sii_engine_advanced import AdvancedSIIEngine, AdvancedSIIOutput, DegradationMode


@dataclass
class GreenhouseRow:
    """Parsed greenhouse telemetry row."""
    timestamp: datetime
    cycle: int
    zone_id: str
    sensors: Dict[str, float]  # column_name -> value
    sensor_vector: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class ZoneResult:
    """Detection results for a single zone with audit trail."""
    zone_id: str
    total_samples: int
    baseline_samples_used: int
    samples_processed: int
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None

    # Detection metrics
    first_alert_timestamp: Optional[datetime] = None
    first_alert_cycle: Optional[int] = None
    alert_source: Optional[str] = None
    alert_reason: Optional[str] = None
    anomalies_detected: int = 0

    # Stability metrics
    max_instability_score: float = 0.0
    instability_at_alert: float = 0.0
    avg_instability_score: float = 0.0

    # State distribution
    time_stable: float = 0.0  # percentage
    time_transition: float = 0.0
    time_unstable: float = 0.0
    time_lock_in: float = 0.0
    time_warmup: float = 0.0

    # Advanced metrics
    avg_novelty_score: float = 0.0
    avg_ensemble_agreement: float = 0.0
    most_common_degradation_mode: str = "unknown"

    # Data quality
    missingness_rate: float = 0.0
    filled_samples: int = 0

    # Audit trail fields
    baseline_finalized_timestamp: Optional[datetime] = None
    baseline_finalized_cycle: int = 0
    alert_before_baseline_finalized: bool = False
    warmup_alert: bool = False
    warmup_samples: int = 0
    state_at_alert: str = ""
    urgency_at_alert: str = ""
    structural_drift_at_alert: float = 0.0
    novelty_at_alert: float = 0.0
    top_sensors_at_alert: str = ""

    # Advanced diagnostics
    longest_instability_duration: int = 0
    top_contributing_sensors: List[Dict] = field(default_factory=list)
    per_timestep_results: List[Dict] = field(default_factory=list)

    # Error tracking
    error_message: Optional[str] = None
    was_insufficient_history: bool = False


@dataclass
class ValidationSummary:
    """Overall validation summary with audit trail."""
    data_source: str
    total_zones: int = 0
    total_samples_processed: int = 0
    total_anomalies_detected: int = 0
    sampling_interval_minutes: Optional[float] = None
    baseline_window_configured: int = 288
    min_baseline_configured: int = 48
    engine_version: str = "AdvancedSIIEngine"
    execution_timestamp: str = ""

    zone_results: List[ZoneResult] = field(default_factory=list)

    # Aggregate metrics
    avg_detection_coverage: float = 0.0  # pct of zones with alerts
    total_instability_duration: int = 0
    avg_missingness_rate: float = 0.0

    # Audit aggregates
    detections_by_source: Dict[str, int] = field(default_factory=dict)
    alerts_before_baseline: int = 0
    warmup_alerts: int = 0

    # Validation notes
    validation_type: str = "unsupervised_telemetry"
    notes: List[str] = field(default_factory=list)


class GreenhouseValidator:
    """WUR greenhouse validation runner using Advanced SII Engine."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        baseline_window: int = 288,
        min_baseline: int = 48,
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
        self.plot = plot and HAS_MATPLOTLIB
        self.summary: Optional[ValidationSummary] = None

    def run(self) -> Optional[ValidationSummary]:
        """Run validation on greenhouse data."""
        print(f"🌱 WUR Autonomous Greenhouse Validation")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Baseline window: {self.baseline_window} samples (~24h at 5min)")
        print(f"   Min baseline: {self.min_baseline} samples (~4h at 5min)")
        print()

        # Load greenhouse climate data
        climate_file = self.data_dir / "Greenhouse_climate.csv"
        if not climate_file.exists():
            print(f"   ❌ Climate data not found: {climate_file}")
            return None

        print(f"   📊 Loading climate data from {climate_file.name}...")
        df = self._load_climate_data(climate_file)
        if df is None or df.empty:
            print(f"   ❌ Failed to load climate data")
            return None

        print(f"   ✓ Loaded {len(df):,} rows with {len(df.columns)} columns")

        # Auto-detect structure
        timestamp_col, zone_col, sensor_cols = self._detect_structure(df)
        print(f"   ✓ Timestamp column: {timestamp_col}")
        print(f"   ✓ Zone column: {zone_col if zone_col else 'None (single system)'}")
        print(f"   ✓ Sensor columns: {len(sensor_cols)} detected")
        print()

        # Handle missing values
        df_filled = self._handle_missing_values(df, sensor_cols)
        missingness_rate = (df_filled["_filled"].sum() / len(df_filled)) * 100
        if missingness_rate > 0:
            print(f"   ⚠️  Filled {df_filled['_filled'].sum():,} missing values ({missingness_rate:.1f}%)")

        # Parse zones and data
        zones_data = self._parse_zones(df_filled, timestamp_col, zone_col, sensor_cols)
        print(f"   ✓ Parsed {len(zones_data)} zone(s)")
        print()

        # Infer sampling interval
        sampling_interval = self._infer_sampling_interval(df_filled, timestamp_col)
        if sampling_interval:
            print(f"   ℹ️  Inferred sampling interval: {sampling_interval:.1f} minutes")

        # Create validation summary
        self.summary = ValidationSummary(
            data_source=str(self.data_dir),
            total_zones=len(zones_data),
            baseline_window_configured=self.baseline_window,
            min_baseline_configured=self.min_baseline,
            execution_timestamp=datetime.now().isoformat(),
            sampling_interval_minutes=sampling_interval,
        )

        # Process each zone
        print(f"   🔍 Processing {len(zones_data)} zone(s)...")
        iterator = zones_data.items()
        if self.progress:
            iterator = tqdm(iterator, desc="  Zones", total=len(zones_data), unit="zone")

        for zone_id, rows_data in iterator:
            result = self._process_zone(zone_id, rows_data, sensor_cols)
            self.summary.zone_results.append(result)
            self.summary.total_samples_processed += result.samples_processed
            self.summary.total_anomalies_detected += result.anomalies_detected

        # Compute aggregate metrics
        self._compute_summary_metrics()

        # Write outputs
        self._write_outputs()

        # Print summary
        self._print_summary()

        return self.summary

    def _load_climate_data(self, filepath: Path) -> Optional[pd.DataFrame]:
        """Load greenhouse climate CSV."""
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception as e:
            print(f"   ❌ Error loading {filepath}: {e}")
            return None

    def _detect_structure(self, df: pd.DataFrame) -> Tuple[str, Optional[str], List[str]]:
        """Auto-detect timestamp, zone, and sensor columns."""
        # Find timestamp column
        timestamp_col = None
        for col in ["timestamp", "Timestamp", "datetime", "DateTime", "time", "Time", "Date", "date"]:
            if col in df.columns:
                timestamp_col = col
                break
        if not timestamp_col:
            # Try to find first column that looks like a timestamp
            for col in df.columns:
                if df[col].dtype == "object" and any(x in str(df[col].iloc[0]).lower() for x in [":", "-", "/"]):
                    timestamp_col = col
                    break
        if not timestamp_col:
            timestamp_col = df.columns[0]

        # Find zone column
        zone_col = None
        for col in ["zone", "Zone", "greenhouse", "Greenhouse", "system", "System", "location", "Location"]:
            if col in df.columns:
                zone_col = col
                break

        # Find numeric sensor columns (exclude zone, timestamp, ID columns)
        exclude_cols = {timestamp_col} | ({"_filled"} if "_filled" in df.columns else set())
        if zone_col:
            exclude_cols.add(zone_col)
        exclude_patterns = {"id", "ID", "index", "Index"}

        sensor_cols = [
            col for col in df.columns
            if col not in exclude_cols
            and pd.api.types.is_numeric_dtype(df[col])
            and not any(pattern in col for pattern in exclude_patterns)
        ]

        return timestamp_col, zone_col, sensor_cols

    def _handle_missing_values(self, df: pd.DataFrame, sensor_cols: List[str]) -> pd.DataFrame:
        """Handle missing values in sensor data."""
        df = df.copy()
        df["_filled"] = False

        for col in sensor_cols:
            if col in df.columns:
                mask = df[col].isna()
                if mask.any():
                    # Forward fill, then backfill
                    df[col] = df[col].fillna(method="ffill").fillna(method="bfill")
                    df.loc[mask, "_filled"] = True

        return df

    def _parse_zones(
        self,
        df: pd.DataFrame,
        timestamp_col: str,
        zone_col: Optional[str],
        sensor_cols: List[str],
    ) -> Dict[str, List[GreenhouseRow]]:
        """Parse data into zones."""
        zones_data: Dict[str, List[GreenhouseRow]] = {}

        zones = [df[zone_col].unique().tolist() if zone_col else ["single_system"]]
        if zone_col:
            zones = df[zone_col].unique().tolist()
        else:
            zones = ["single_system"]

        for zone_id in zones:
            zone_df = df if not zone_col else df[df[zone_col] == zone_id]
            rows = []

            for idx, row in zone_df.iterrows():
                try:
                    ts = pd.to_datetime(row[timestamp_col])
                except Exception:
                    ts = datetime.now()

                sensors = {col: float(row[col]) for col in sensor_cols if col in row and pd.notna(row[col])}
                sensor_vector = np.array([sensors.get(col, 0.0) for col in sensor_cols])

                rows.append(
                    GreenhouseRow(
                        timestamp=ts,
                        cycle=idx,
                        zone_id=str(zone_id),
                        sensors=sensors,
                        sensor_vector=sensor_vector,
                    )
                )

            if rows:
                zones_data[str(zone_id)] = rows

        return zones_data

    def _infer_sampling_interval(self, df: pd.DataFrame, timestamp_col: str) -> Optional[float]:
        """Infer sampling interval in minutes."""
        try:
            if len(df) < 2:
                return None

            ts = pd.to_datetime(df[timestamp_col])
            diffs = ts.diff().dropna()
            if len(diffs) > 0:
                median_diff = diffs.median()
                return median_diff.total_seconds() / 60.0
        except Exception:
            pass
        return None

    def _process_zone(
        self,
        zone_id: str,
        rows_data: List[GreenhouseRow],
        sensor_cols: List[str],
    ) -> ZoneResult:
        """Process a single zone through advanced engine."""
        num_samples = len(rows_data)

        result = ZoneResult(
            zone_id=zone_id,
            total_samples=num_samples,
            first_timestamp=rows_data[0].timestamp if rows_data else None,
            last_timestamp=rows_data[-1].timestamp if rows_data else None,
        )

        if num_samples == 0:
            result.error_message = "No data for zone"
            return result

        try:
            # Create engine for this zone
            engine = AdvancedSIIEngine(
                baseline_window=self.baseline_window,
                recent_window=12,
                system_type="generic",
            )

            # Tracking variables
            first_alert_ts = None
            alert_source = None
            alert_reason = None
            instability_at_alert = 0.0
            state_at_alert = ""
            urgency_at_alert = ""
            drift_at_alert = 0.0

            baseline_finalized_ts = None
            baseline_was_ready = False
            alert_before_baseline = False
            is_warmup_alert = False
            warmup_count = 0

            max_instability = 0.0
            instability_scores = []
            novelty_scores = []
            ensemble_agreements = []
            degradation_modes = []
            state_counts = {"STABLE": 0, "TRANSITION": 0, "UNSTABLE": 0, "LOCK_IN": 0, "WARMUP": 0}

            instability_runs = []
            current_run = 0

            # Stream samples
            for idx, row in enumerate(rows_data):
                output = engine.update(row.sensor_vector, float(row.cycle))

                # Track state
                if output.regime in state_counts:
                    state_counts[output.regime] += 1

                if output.regime == "WARMUP":
                    warmup_count += 1
                elif not baseline_was_ready and engine.baseline_ready:
                    baseline_finalized_ts = row.timestamp
                    baseline_was_ready = True
                else:
                    novelty_scores.append(output.novelty_score)
                    ensemble_agreements.append(output.ensemble_agreement)
                    degradation_modes.append(output.degradation_mode.value)

                max_instability = max(max_instability, output.instability_score)
                instability_scores.append(output.instability_score)

                # Track instability runs
                if output.instability_score > 0.3:
                    current_run += 1
                else:
                    if current_run > 0:
                        instability_runs.append(current_run)
                    current_run = 0

                # Check for alert
                if first_alert_ts is None and output.regime != "WARMUP":
                    is_alert = self._check_alert(output)
                    if is_alert:
                        first_alert_ts = row.timestamp
                        first_alert_cycle = row.cycle
                        instability_at_alert = output.instability_score
                        state_at_alert = output.regime
                        urgency_at_alert = output.urgency
                        drift_at_alert = output.structural_drift

                        # Determine alert source
                        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
                            alert_source = "regime"
                            alert_reason = f"regime={output.regime}"
                        elif output.urgency in ("ALERT", "CRITICAL"):
                            alert_source = "urgency"
                            alert_reason = f"urgency={output.urgency}"
                        else:
                            alert_source = "structural_drift"
                            alert_reason = f"drift={output.structural_drift:.4f}"

                        alert_before_baseline = not baseline_was_ready
                        is_warmup_alert = output.regime == "WARMUP"

                # Record per-timestep for high-resolution output
                result.per_timestep_results.append({
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "cycle": row.cycle,
                    "instability_score": float(output.instability_score),
                    "regime": output.regime,
                    "urgency": output.urgency,
                    "structural_drift": float(output.structural_drift),
                    "novelty_score": float(output.novelty_score),
                    "ensemble_agreement": float(output.ensemble_agreement),
                    "degradation_mode": output.degradation_mode.value,
                })

            # Finalize zone result
            result.samples_processed = num_samples
            result.baseline_samples_used = engine.baseline.sample_count if engine.baseline.is_valid() else 0
            result.warmup_samples = warmup_count

            result.first_alert_timestamp = first_alert_ts
            result.alert_source = alert_source
            result.alert_reason = alert_reason
            result.anomalies_detected = 1 if first_alert_ts else 0

            result.max_instability_score = max_instability
            result.instability_at_alert = instability_at_alert
            result.avg_instability_score = float(np.mean(instability_scores)) if instability_scores else 0.0

            result.state_at_alert = state_at_alert
            result.urgency_at_alert = urgency_at_alert
            result.structural_drift_at_alert = drift_at_alert

            # Compute state distribution
            total_non_warmup = sum(state_counts.values()) - state_counts["WARMUP"]
            if total_non_warmup > 0:
                result.time_stable = 100.0 * state_counts["STABLE"] / total_non_warmup
                result.time_transition = 100.0 * state_counts["TRANSITION"] / total_non_warmup
                result.time_unstable = 100.0 * state_counts["UNSTABLE"] / total_non_warmup
                result.time_lock_in = 100.0 * state_counts["LOCK_IN"] / total_non_warmup
            if num_samples > 0:
                result.time_warmup = 100.0 * state_counts["WARMUP"] / num_samples

            # Advanced metrics
            if novelty_scores:
                result.avg_novelty_score = float(np.mean(novelty_scores))
                result.novelty_at_alert = float(novelty_scores[-1]) if novelty_scores else 0.0
            if ensemble_agreements:
                result.avg_ensemble_agreement = float(np.mean(ensemble_agreements))

            if degradation_modes:
                from collections import Counter
                mode_counts = Counter(degradation_modes)
                result.most_common_degradation_mode = mode_counts.most_common(1)[0][0]

            # Longest instability
            if instability_runs:
                result.longest_instability_duration = max(instability_runs)

            # Top contributing sensors (from last output)
            if hasattr(engine, '_last_output') and engine._last_output and engine._last_output.top_sensors:
                result.top_contributing_sensors = [
                    {
                        "sensor_id": s.sensor_id,
                        "contribution": round(float(s.contribution_to_instability), 4),
                        "health_score": round(float(s.health_score), 4),
                    }
                    for s in engine._last_output.top_sensors[:3]
                ]
                result.top_sensors_at_alert = json.dumps(result.top_contributing_sensors)

            # Audit trail
            result.baseline_finalized_timestamp = baseline_finalized_ts
            result.baseline_finalized_cycle = engine.baseline.sample_count if engine.baseline.is_valid() else 0
            result.alert_before_baseline_finalized = alert_before_baseline
            result.warmup_alert = is_warmup_alert

            return result

        except Exception as e:
            result.error_message = str(e)[:100]
            result.was_insufficient_history = num_samples < self.min_baseline
            return result

    def _check_alert(self, output: AdvancedSIIOutput) -> bool:
        """Check if alert condition met."""
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return True
        if output.urgency in ("ALERT", "CRITICAL"):
            return True
        if output.structural_drift >= self.structural_drift_threshold:
            return True
        return False

    def _compute_summary_metrics(self) -> None:
        """Compute aggregate metrics."""
        if not self.summary or not self.summary.zone_results:
            return

        results = self.summary.zone_results

        # Compute coverage
        zones_with_alerts = sum(1 for r in results if r.anomalies_detected > 0)
        self.summary.avg_detection_coverage = (
            100.0 * zones_with_alerts / len(results) if results else 0.0
        )

        # Aggregate instability
        self.summary.total_instability_duration = sum(r.longest_instability_duration for r in results)

        # Aggregate missingness
        self.summary.avg_missingness_rate = (
            np.mean([r.missingness_rate for r in results]) if results else 0.0
        )

        # Audit aggregates
        for result in results:
            if result.alert_source:
                if result.alert_source not in self.summary.detections_by_source:
                    self.summary.detections_by_source[result.alert_source] = 0
                self.summary.detections_by_source[result.alert_source] += 1

            if result.alert_before_baseline_finalized:
                self.summary.alerts_before_baseline += 1
            if result.warmup_alert:
                self.summary.warmup_alerts += 1

        # Add validation notes
        self.summary.notes.append("Unsupervised telemetry validation (no ground truth labels)")
        self.summary.notes.append(f"Processed {len(results)} zone(s) with {self.summary.total_samples_processed:,} samples")
        if self.summary.total_anomalies_detected > 0:
            self.summary.notes.append(f"Detected anomalies in {zones_with_alerts}/{len(results)} zone(s)")

    def _print_summary(self) -> None:
        """Print validation summary."""
        if not self.summary:
            return

        print("\n" + "=" * 70)
        print("📊 GREENHOUSE TELEMETRY VALIDATION SUMMARY")
        print("=" * 70)

        print(f"\nData source: {self.summary.data_source}")
        print(f"Execution: {self.summary.execution_timestamp}")
        print(f"Validation type: {self.summary.validation_type}")
        print()

        print(f"Total zones processed:  {self.summary.total_zones}")
        print(f"Total samples:          {self.summary.total_samples_processed:,}")
        print(f"Anomaly detections:     {self.summary.total_anomalies_detected}")
        print(f"Detection coverage:     {self.summary.avg_detection_coverage:.1f}% of zones")
        print()

        if self.summary.sampling_interval_minutes:
            print(f"Sampling interval:      {self.summary.sampling_interval_minutes:.1f} minutes")
        print(f"Baseline window:        {self.summary.baseline_window_configured} samples")
        print(f"Min baseline:           {self.summary.min_baseline_configured} samples")
        print()

        if self.summary.detections_by_source:
            print("Detections by source:")
            for source, count in self.summary.detections_by_source.items():
                print(f"  {source}: {count}")

        print(f"\nAlerts before baseline finalized: {self.summary.alerts_before_baseline}")
        print(f"Warmup alerts:                   {self.summary.warmup_alerts}")
        print()

        if self.summary.notes:
            print("Notes:")
            for note in self.summary.notes:
                print(f"  • {note}")
        print()

    def _write_outputs(self) -> None:
        """Write results to output directory."""
        if not self.summary:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write summary JSON
        self._write_summary_json()

        # Write per-zone CSV
        self._write_per_zone_csv()

        # Write per-timestep results
        self._write_per_timestep_results()

        # Write plots if requested
        if self.plot:
            self._write_plots()

        print(f"\n✅ Results written to {self.output_dir}")

    def _write_summary_json(self) -> None:
        """Write validation summary as JSON."""
        if not self.summary:
            return

        output = {
            "data_source": self.summary.data_source,
            "validation_type": self.summary.validation_type,
            "execution_timestamp": self.summary.execution_timestamp,
            "sampling_interval_minutes": self.summary.sampling_interval_minutes,
            "total_zones": self.summary.total_zones,
            "total_samples_processed": self.summary.total_samples_processed,
            "total_anomalies_detected": self.summary.total_anomalies_detected,
            "detection_coverage_pct": self.summary.avg_detection_coverage,
            "baseline_window_configured": self.summary.baseline_window_configured,
            "min_baseline_configured": self.summary.min_baseline_configured,
            "engine_version": self.summary.engine_version,
            "detections_by_source": self.summary.detections_by_source,
            "alerts_before_baseline": self.summary.alerts_before_baseline,
            "warmup_alerts": self.summary.warmup_alerts,
            "avg_missingness_rate": round(self.summary.avg_missingness_rate, 4),
            "notes": self.summary.notes,
        }

        with open(self.output_dir / "summary.json", "w") as f:
            json.dump(output, f, indent=2)

    def _write_per_zone_csv(self) -> None:
        """Write per-zone results CSV."""
        if not self.summary or not self.summary.zone_results:
            return

        with open(self.output_dir / "per_zone_results.csv", "w") as f:
            f.write(
                "zone_id,total_samples,samples_processed,baseline_samples_used,warmup_samples,"
                "first_timestamp,last_timestamp,first_alert_timestamp,alert_source,alert_reason,"
                "anomalies_detected,max_instability,avg_instability,instability_at_alert,"
                "state_at_alert,urgency_at_alert,drift_at_alert,novelty_at_alert,"
                "avg_novelty,avg_ensemble_agreement,degradation_mode,"
                "time_stable_pct,time_transition_pct,time_unstable_pct,time_lockin_pct,time_warmup_pct,"
                "longest_instability_duration,baseline_finalized_timestamp,alert_before_baseline,"
                "warmup_alert,error_message,was_insufficient_history\n"
            )

            for result in self.summary.zone_results:
                f.write(
                    f"{result.zone_id},"
                    f"{result.total_samples},"
                    f"{result.samples_processed},"
                    f"{result.baseline_samples_used},"
                    f"{result.warmup_samples},"
                    f"{result.first_timestamp.isoformat() if result.first_timestamp else ''},"
                    f"{result.last_timestamp.isoformat() if result.last_timestamp else ''},"
                    f"{result.first_alert_timestamp.isoformat() if result.first_alert_timestamp else ''},"
                    f"{result.alert_source or ''},"
                    f"{result.alert_reason or ''},"
                    f"{result.anomalies_detected},"
                    f"{result.max_instability_score:.6f},"
                    f"{result.avg_instability_score:.6f},"
                    f"{result.instability_at_alert:.6f},"
                    f"{result.state_at_alert},"
                    f"{result.urgency_at_alert},"
                    f"{result.structural_drift_at_alert:.6f},"
                    f"{result.novelty_at_alert:.6f},"
                    f"{result.avg_novelty_score:.6f},"
                    f"{result.avg_ensemble_agreement:.6f},"
                    f"{result.most_common_degradation_mode},"
                    f"{result.time_stable:.1f},"
                    f"{result.time_transition:.1f},"
                    f"{result.time_unstable:.1f},"
                    f"{result.time_lock_in:.1f},"
                    f"{result.time_warmup:.1f},"
                    f"{result.longest_instability_duration},"
                    f"{result.baseline_finalized_timestamp.isoformat() if result.baseline_finalized_timestamp else ''},"
                    f"{result.alert_before_baseline_finalized},"
                    f"{result.warmup_alert},"
                    f"{result.error_message or ''},"
                    f"{result.was_insufficient_history}\n"
                )

    def _write_per_timestep_results(self) -> None:
        """Write per-timestep results for each zone."""
        if not self.summary or not self.summary.zone_results:
            return

        for result in self.summary.zone_results:
            if not result.per_timestep_results:
                continue

            zone_dir = self.output_dir / result.zone_id
            zone_dir.mkdir(parents=True, exist_ok=True)

            filepath = zone_dir / "timestep_results.csv"
            with open(filepath, "w") as f:
                f.write(
                    "timestamp,cycle,instability_score,regime,urgency,"
                    "structural_drift,novelty_score,ensemble_agreement,degradation_mode\n"
                )
                for record in result.per_timestep_results:
                    f.write(
                        f"{record['timestamp'] or ''},"
                        f"{record['cycle']},"
                        f"{record['instability_score']:.6f},"
                        f"{record['regime']},"
                        f"{record['urgency']},"
                        f"{record['structural_drift']:.6f},"
                        f"{record['novelty_score']:.6f},"
                        f"{record['ensemble_agreement']:.6f},"
                        f"{record['degradation_mode']}\n"
                    )

    def _write_plots(self) -> None:
        """Generate optional visualizations."""
        if not self.summary or not HAS_MATPLOTLIB:
            return

        plots_dir = self.output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        # Summary plot
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Greenhouse Validation Summary", fontsize=16)

        # Detection coverage
        zone_names = [r.zone_id for r in self.summary.zone_results]
        anomalies = [r.anomalies_detected for r in self.summary.zone_results]
        axes[0, 0].bar(zone_names, anomalies)
        axes[0, 0].set_title("Anomalies Detected by Zone")
        axes[0, 0].set_ylabel("Count")

        # Max instability
        max_instabilities = [r.max_instability_score for r in self.summary.zone_results]
        axes[0, 1].bar(zone_names, max_instabilities)
        axes[0, 1].set_title("Max Instability Score by Zone")
        axes[0, 1].set_ylabel("Score")

        # State distribution
        state_data = {
            "Stable": [r.time_stable for r in self.summary.zone_results],
            "Transition": [r.time_transition for r in self.summary.zone_results],
            "Unstable": [r.time_unstable for r in self.summary.zone_results],
            "Lock-in": [r.time_lock_in for r in self.summary.zone_results],
        }
        axes[1, 0].bar(zone_names, state_data["Stable"], label="Stable")
        axes[1, 0].bar(zone_names, state_data["Transition"], bottom=state_data["Stable"], label="Transition")
        axes[1, 0].bar(
            zone_names,
            state_data["Unstable"],
            bottom=[state_data["Stable"][i] + state_data["Transition"][i] for i in range(len(zone_names))],
            label="Unstable",
        )
        axes[1, 0].set_title("State Distribution by Zone (%)")
        axes[1, 0].set_ylabel("Percentage")
        axes[1, 0].legend()

        # Novelty scores
        novelties = [r.avg_novelty_score for r in self.summary.zone_results]
        axes[1, 1].bar(zone_names, novelties)
        axes[1, 1].set_title("Avg Novelty Score by Zone")
        axes[1, 1].set_ylabel("Score")

        plt.tight_layout()
        plt.savefig(plots_dir / "summary.png", dpi=100, bbox_inches="tight")
        plt.close()

        # Per-zone timeseries plots
        for result in self.summary.zone_results:
            if not result.per_timestep_results:
                continue

            fig, axes = plt.subplots(3, 1, figsize=(14, 10))
            fig.suptitle(f"Zone {result.zone_id} - Timeseries Analysis", fontsize=14)

            cycles = [r["cycle"] for r in result.per_timestep_results]
            instability = [r["instability_score"] for r in result.per_timestep_results]
            drift = [r["structural_drift"] for r in result.per_timestep_results]
            novelty = [r["novelty_score"] for r in result.per_timestep_results]

            axes[0].plot(cycles, instability, linewidth=1)
            if result.first_alert_cycle:
                axes[0].axvline(result.first_alert_cycle, color="red", linestyle="--", label="Alert")
            axes[0].set_title("Instability Score Over Time")
            axes[0].set_ylabel("Score")
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            axes[1].plot(cycles, drift, linewidth=1, color="orange")
            axes[1].axhline(self.structural_drift_threshold, color="red", linestyle="--", label="Threshold")
            axes[1].set_title("Structural Drift Over Time")
            axes[1].set_ylabel("Drift")
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

            axes[2].plot(cycles, novelty, linewidth=1, color="green")
            axes[2].set_title("Novelty Score Over Time")
            axes[2].set_ylabel("Novelty")
            axes[2].set_xlabel("Cycle")
            axes[2].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(plots_dir / f"{result.zone_id}_timeseries.png", dpi=100, bbox_inches="tight")
            plt.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WUR Autonomous Greenhouse Validation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/wur_greenhouse_runner.py --data-dir ./iGrow --output results
  python tools/wur_greenhouse_runner.py --data-dir ./iGrow --output results --plot --progress
        """,
    )

    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="Path to iGrow data directory containing Greenhouse_climate.csv",
    )
    parser.add_argument(
        "--output",
        default="greenhouse_validation_results",
        type=Path,
        help="Output directory for results",
    )
    parser.add_argument(
        "--baseline-window",
        default=288,
        type=int,
        help="Baseline window in samples (~24h at 5min interval)",
    )
    parser.add_argument(
        "--min-baseline",
        default=48,
        type=int,
        help="Minimum baseline samples required (~4h at 5min interval)",
    )
    parser.add_argument(
        "--structural-drift-threshold",
        default=0.5,
        type=float,
        help="Structural drift threshold for alert",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bars",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate plots (requires matplotlib)",
    )

    args = parser.parse_args()

    validator = GreenhouseValidator(
        data_dir=args.data_dir,
        output_dir=args.output,
        baseline_window=args.baseline_window,
        min_baseline=args.min_baseline,
        structural_drift_threshold=args.structural_drift_threshold,
        progress=args.progress,
        plot=args.plot,
    )

    summary = validator.run()
    sys.exit(0 if summary else 1)


if __name__ == "__main__":
    main()
