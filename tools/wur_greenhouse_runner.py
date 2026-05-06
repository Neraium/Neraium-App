WUR Autonomous Greenhouse Validation Runner for Neraium Advanced SII Engine.

Performs unsupervised telemetry validation on greenhouse climate data using
the AdvancedSIIEngine to detect environmental instability, control drift,
and anomalies. Designed for exploratory and operational monitoring.

Assumes ~5-minute sampling interval:
  - 288 samples ≈ 24 hours
  - 48 samples ≈ 4 hours
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter

import numpy as np
import pandas as pd

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from neraium_core.sii_engine_advanced import AdvancedSIIEngine, AdvancedSIIOutput


@dataclass
class GreenhouseRow:
    timestamp: datetime
    cycle: int
    zone_id: str
    sensors: Dict[str, float]
    sensor_vector: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class ZoneResult:
    zone_id: str
    total_samples: int
    baseline_samples_used: int
    samples_processed: int
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None

    first_alert_timestamp: Optional[datetime] = None
    first_alert_cycle: Optional[int] = None
    alert_source: Optional[str] = None
    alert_reason: Optional[str] = None
    anomalies_detected: int = 0

    max_instability_score: float = 0.0
    instability_at_alert: float = 0.0
    avg_instability_score: float = 0.0

    time_stable: float = 0.0
    time_transition: float = 0.0
    time_unstable: float = 0.0
    time_lock_in: float = 0.0
    time_warmup: float = 0.0

    avg_novelty_score: float = 0.0
    avg_ensemble_agreement: float = 0.0
    most_common_degradation_mode: str = "unknown"

    missingness_rate: float = 0.0
    filled_samples: int = 0

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

    longest_instability_duration: int = 0
    top_contributing_sensors: List[Dict] = field(default_factory=list)
    per_timestep_results: List[Dict] = field(default_factory=list)

    error_message: Optional[str] = None
    was_insufficient_history: bool = False


@dataclass
class ValidationSummary:
    data_source: str
    validation_type: str = "unsupervised_telemetry"
    total_zones: int = 0
    zones_with_anomalies: int = 0
    total_samples_processed: int = 0
    total_anomalies_detected: int = 0
    sampling_interval_minutes: Optional[float] = None
    baseline_window_configured: int = 288
    min_baseline_configured: int = 48
    engine_version: str = "AdvancedSIIEngine"
    execution_timestamp: str = ""

    zone_results: List[ZoneResult] = field(default_factory=list)

    anomalies_per_zone: Dict[str, int] = field(default_factory=dict)
    percent_time_unstable: float = 0.0
    avg_missingness_rate: float = 0.0

    min_instability_duration: Optional[int] = None
    max_instability_duration: Optional[int] = None
    mean_instability_duration: Optional[float] = None
    median_instability_duration: Optional[float] = None

    detections_by_source: Dict[str, int] = field(default_factory=dict)
    alerts_before_baseline: int = 0
    warmup_alerts: int = 0

    notes: List[str] = field(default_factory=list)


class GreenhouseValidator:
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
        print("🌱 WUR Autonomous Greenhouse Validation")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Baseline window: {self.baseline_window} samples")
        print(f"   Min baseline: {self.min_baseline} samples")
        print()

        climate_file = self.data_dir / "Greenhouse_climate.csv"
        if not climate_file.exists():
            print(f"   ❌ Climate data not found: {climate_file}")
            return None

        print(f"   📊 Loading climate data from {climate_file.name}...")
        df = self._load_climate_data(climate_file)
        if df is None or df.empty:
            print("   ❌ Failed to load climate data")
            return None

        print(f"   ✓ Loaded {len(df):,} rows with {len(df.columns)} columns")

        timestamp_col, zone_col, sensor_cols = self._detect_structure(df)

        print(f"   ✓ Timestamp column: {timestamp_col}")
        print(f"   ✓ Zone column: {zone_col if zone_col else 'None (single system)'}")
        print(f"   ✓ Sensor columns: {len(sensor_cols)} detected")

        if not sensor_cols:
            print("   ❌ No usable sensor columns detected")
            return None

        print(f"   ✓ Sensors: {', '.join(sensor_cols[:10])}{'...' if len(sensor_cols) > 10 else ''}")
        print()

        df_filled = self._handle_missing_values(df, sensor_cols)
        missingness_rate = (df_filled["_filled"].sum() / len(df_filled)) * 100.0

        if missingness_rate > 0:
            print(f"   ⚠️ Filled {df_filled['_filled'].sum():,} missing values ({missingness_rate:.1f}%)")

        zones_data = self._parse_zones(df_filled, timestamp_col, zone_col, sensor_cols)
        print(f"   ✓ Parsed {len(zones_data)} zone(s)")
        print()

        sampling_interval = self._infer_sampling_interval(df_filled, timestamp_col)
        if sampling_interval:
            print(f"   ℹ️ Inferred sampling interval: {sampling_interval:.1f} minutes")

        self.summary = ValidationSummary(
            data_source=str(self.data_dir),
            total_zones=len(zones_data),
            baseline_window_configured=self.baseline_window,
            min_baseline_configured=self.min_baseline,
            execution_timestamp=datetime.now().isoformat(),
            sampling_interval_minutes=sampling_interval,
        )

        print(f"   🔍 Processing {len(zones_data)} zone(s)...")
        iterator = zones_data.items()
        if self.progress:
            iterator = tqdm(iterator, desc="  Zones", total=len(zones_data), unit="zone")

        for zone_id, rows_data in iterator:
            result = self._process_zone(zone_id, rows_data, sensor_cols)
            self.summary.zone_results.append(result)
            self.summary.total_samples_processed += result.samples_processed
            self.summary.total_anomalies_detected += result.anomalies_detected

        self._compute_summary_metrics()
        self._write_outputs()
        self._print_summary()

        return self.summary

    def _load_climate_data(self, filepath: Path) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_csv(filepath, low_memory=False)

            for col in df.columns:
                if col == "%time":
                    continue
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().sum() > 0:
                    df[col] = converted

            return df

        except Exception as e:
            print(f"   ❌ Error loading {filepath}: {e}")
            return None

    def _detect_structure(self, df: pd.DataFrame) -> Tuple[str, Optional[str], List[str]]:
        timestamp_col = None

        preferred_time_cols = [
            "%time",
            "timestamp",
            "Timestamp",
            "datetime",
            "DateTime",
            "time",
            "Time",
            "Date",
            "date",
        ]

        for col in preferred_time_cols:
            if col in df.columns:
                timestamp_col = col
                break

        if not timestamp_col:
            timestamp_col = df.columns[0]

        zone_col = None
        for col in ["zone", "Zone", "greenhouse", "Greenhouse", "system", "System", "location", "Location"]:
            if col in df.columns:
                zone_col = col
                break

        exclude_cols = {timestamp_col, "_filled"}
        if zone_col:
            exclude_cols.add(zone_col)

        exclude_patterns = [
            "id",
            "index",
            "date",
            "time",
        ]

        sensor_cols = []
        for col in df.columns:
            if col in exclude_cols:
                continue

            lower = str(col).lower()
            if any(pattern in lower for pattern in exclude_patterns):
                continue

            if pd.api.types.is_numeric_dtype(df[col]):
                valid_count = df[col].notna().sum()
                if valid_count > max(10, int(0.05 * len(df))):
                    sensor_cols.append(col)

        return timestamp_col, zone_col, sensor_cols

    def _handle_missing_values(self, df: pd.DataFrame, sensor_cols: List[str]) -> pd.DataFrame:
        df = df.copy()
        df["_filled"] = False

        for col in sensor_cols:
            mask = df[col].isna()
            if mask.any():
                df[col] = df[col].ffill().bfill()
                df.loc[mask, "_filled"] = True

        return df

    def _parse_zones(
        self,
        df: pd.DataFrame,
        timestamp_col: str,
        zone_col: Optional[str],
        sensor_cols: List[str],
    ) -> Dict[str, List[GreenhouseRow]]:
        zones_data: Dict[str, List[GreenhouseRow]] = {}

        if zone_col:
            zones = df[zone_col].dropna().unique().tolist()
        else:
            zones = ["single_system"]

        for zone_id in zones:
            zone_df = df if not zone_col else df[df[zone_col] == zone_id]
            rows = []

            for idx, row in zone_df.iterrows():
                try:
                    ts = pd.to_datetime(row[timestamp_col])
                except Exception:
                    ts = None

                sensors = {}
                for col in sensor_cols:
                    value = row[col]
                    if pd.notna(value):
                        sensors[col] = float(value)

                sensor_vector = np.array([sensors.get(col, 0.0) for col in sensor_cols], dtype=float)

                rows.append(
                    GreenhouseRow(
                        timestamp=ts,
                        cycle=int(idx),
                        zone_id=str(zone_id),
                        sensors=sensors,
                        sensor_vector=sensor_vector,
                    )
                )

            if rows:
                zones_data[str(zone_id)] = rows

        return zones_data

    def _infer_sampling_interval(self, df: pd.DataFrame, timestamp_col: str) -> Optional[float]:
        try:
            if len(df) < 2:
                return None

            ts = pd.to_datetime(df[timestamp_col], errors="coerce").dropna()
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
        num_samples = len(rows_data)

        result = ZoneResult(
            zone_id=zone_id,
            total_samples=num_samples,
            baseline_samples_used=0,
            samples_processed=0,
            first_timestamp=rows_data[0].timestamp if rows_data else None,
            last_timestamp=rows_data[-1].timestamp if rows_data else None,
        )

        if num_samples == 0:
            result.error_message = "No data for zone"
            return result

        try:
            engine = AdvancedSIIEngine(
                baseline_window=self.baseline_window,
                recent_window=12,
                system_type="generic",
            )

            first_alert_ts = None
            first_alert_cycle = None
            alert_source = None
            alert_reason = None

            instability_at_alert = 0.0
            state_at_alert = ""
            urgency_at_alert = ""
            drift_at_alert = 0.0
            novelty_at_alert = 0.0

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

            state_counts = {
                "STABLE": 0,
                "TRANSITION": 0,
                "UNSTABLE": 0,
                "LOCK_IN": 0,
                "WARMUP": 0,
            }

            instability_runs = []
            current_run = 0

            for row in rows_data:
                output: AdvancedSIIOutput = engine.update(row.sensor_vector, float(row.cycle))

                if output.regime in state_counts:
                    state_counts[output.regime] += 1

                if output.regime == "WARMUP":
                    warmup_count += 1
                elif not baseline_was_ready and getattr(engine, "baseline_ready", False):
                    baseline_finalized_ts = row.timestamp
                    baseline_was_ready = True

                max_instability = max(max_instability, float(output.instability_score))
                instability_scores.append(float(output.instability_score))
                novelty_scores.append(float(output.novelty_score))
                ensemble_agreements.append(float(output.ensemble_agreement))
                degradation_modes.append(output.degradation_mode.value)

                if output.instability_score > 0.3:
                    current_run += 1
                else:
                    if current_run > 0:
                        instability_runs.append(current_run)
                    current_run = 0

                if first_alert_ts is None and output.regime != "WARMUP":
                    is_alert = self._check_alert(output)
                    if is_alert:
                        first_alert_ts = row.timestamp
                        first_alert_cycle = row.cycle
                        instability_at_alert = float(output.instability_score)
                        state_at_alert = output.regime
                        urgency_at_alert = output.urgency
                        drift_at_alert = float(output.structural_drift)
                        novelty_at_alert = float(output.novelty_score)

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

                result.per_timestep_results.append(
                    {
                        "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                        "cycle": row.cycle,
                        "instability_score": float(output.instability_score),
                        "regime": output.regime,
                        "urgency": output.urgency,
                        "structural_drift": float(output.structural_drift),
                        "novelty_score": float(output.novelty_score),
                        "ensemble_agreement": float(output.ensemble_agreement),
                        "degradation_mode": output.degradation_mode.value,
                    }
                )

            if current_run > 0:
                instability_runs.append(current_run)

            result.samples_processed = num_samples
            result.baseline_samples_used = getattr(getattr(engine, "baseline", None), "sample_count", self.min_baseline)
            result.warmup_samples = warmup_count

            result.first_alert_timestamp = first_alert_ts
            result.first_alert_cycle = first_alert_cycle
            result.alert_source = alert_source
            result.alert_reason = alert_reason
            result.anomalies_detected = 1 if first_alert_ts else 0

            result.max_instability_score = max_instability
            result.instability_at_alert = instability_at_alert
            result.avg_instability_score = float(np.mean(instability_scores)) if instability_scores else 0.0

            result.state_at_alert = state_at_alert
            result.urgency_at_alert = urgency_at_alert
            result.structural_drift_at_alert = drift_at_alert
            result.novelty_at_alert = novelty_at_alert

            total_non_warmup = sum(state_counts.values()) - state_counts["WARMUP"]
            if total_non_warmup > 0:
                result.time_stable = 100.0 * state_counts["STABLE"] / total_non_warmup
                result.time_transition = 100.0 * state_counts["TRANSITION"] / total_non_warmup
                result.time_unstable = 100.0 * state_counts["UNSTABLE"] / total_non_warmup
                result.time_lock_in = 100.0 * state_counts["LOCK_IN"] / total_non_warmup

            if num_samples > 0:
                result.time_warmup = 100.0 * state_counts["WARMUP"] / num_samples

            result.avg_novelty_score = float(np.mean(novelty_scores)) if novelty_scores else 0.0
            result.avg_ensemble_agreement = float(np.mean(ensemble_agreements)) if ensemble_agreements else 0.0

            if degradation_modes:
                mode_counts = Counter(degradation_modes)
                result.most_common_degradation_mode = mode_counts.most_common(1)[0][0]

            if instability_runs:
                result.longest_instability_duration = max(instability_runs)

            result.baseline_finalized_timestamp = baseline_finalized_ts
            result.baseline_finalized_cycle = result.baseline_samples_used
            result.alert_before_baseline_finalized = alert_before_baseline
            result.warmup_alert = is_warmup_alert

            return result

        except Exception as e:
            result.error_message = str(e)[:200]
            result.was_insufficient_history = num_samples < self.min_baseline
            result.samples_processed = 0
            result.baseline_samples_used = 0
            return result

    def _check_alert(self, output: AdvancedSIIOutput) -> bool:
        if output.regime in ("TRANSITION", "UNSTABLE", "LOCK_IN"):
            return True
        if output.urgency in ("ALERT", "CRITICAL"):
            return True
        if output.structural_drift >= self.structural_drift_threshold:
            return True
        return False

    def _compute_summary_metrics(self) -> None:
        if not self.summary or not self.summary.zone_results:
            return

        results = self.summary.zone_results

        zones_with_alerts = sum(1 for r in results if r.anomalies_detected > 0)
        self.summary.zones_with_anomalies = zones_with_alerts

        for result in results:
            self.summary.anomalies_per_zone[result.zone_id] = result.anomalies_detected

        total_time_unstable = sum(r.time_unstable + r.time_lock_in for r in results)
        total_time = sum(
            r.time_stable + r.time_transition + r.time_unstable + r.time_lock_in
            for r in results
        )

        if total_time > 0:
            self.summary.percent_time_unstable = 100.0 * total_time_unstable / total_time

        durations = [r.longest_instability_duration for r in results if r.longest_instability_duration > 0]
        if durations:
            self.summary.min_instability_duration = min(durations)
            self.summary.max_instability_duration = max(durations)
            self.summary.mean_instability_duration = float(np.mean(durations))
            self.summary.median_instability_duration = float(np.median(durations))

        self.summary.avg_missingness_rate = float(np.mean([r.missingness_rate for r in results])) if results else 0.0

        for result in results:
            if result.alert_source:
                self.summary.detections_by_source[result.alert_source] = (
                    self.summary.detections_by_source.get(result.alert_source, 0) + 1
                )

            if result.alert_before_baseline_finalized:
                self.summary.alerts_before_baseline += 1
            if result.warmup_alert:
                self.summary.warmup_alerts += 1

        self.summary.notes.append("Unsupervised telemetry validation with no ground truth labels")
        self.summary.notes.append(
            f"Processed {len(results)} zone(s) with {self.summary.total_samples_processed:,} samples"
        )

        if self.summary.total_anomalies_detected > 0:
            self.summary.notes.append(f"Detected anomalies in {zones_with_alerts}/{len(results)} zone(s)")

    def _print_summary(self) -> None:
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
        print(f"Zones with anomalies:   {self.summary.zones_with_anomalies}")
        print(f"Total samples:          {self.summary.total_samples_processed:,}")
        print(f"Total anomalies:        {self.summary.total_anomalies_detected}")
        print()

        if self.summary.sampling_interval_minutes:
            print(f"Sampling interval:      {self.summary.sampling_interval_minutes:.1f} minutes")
        print(f"Baseline window:        {self.summary.baseline_window_configured} samples")
        print(f"Min baseline:           {self.summary.min_baseline_configured} samples")
        print()

        print("System Stability:")
        print(f"  Time unstable/lock-in: {self.summary.percent_time_unstable:.1f}%")

        if self.summary.min_instability_duration is not None:
            print(
                "  Instability duration:  "
                f"min={self.summary.min_instability_duration}, "
                f"max={self.summary.max_instability_duration}, "
                f"mean={self.summary.mean_instability_duration:.1f}, "
                f"median={self.summary.median_instability_duration:.1f}"
            )

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
        if not self.summary:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_summary_json()
        self._write_per_zone_csv()
        self._write_per_timestep_results()

        if self.plot:
            self._write_plots()

        print(f"\n✅ Results written to {self.output_dir}")

    def _write_summary_json(self) -> None:
        if not self.summary:
            return

        instability_stats = {}
        if self.summary.min_instability_duration is not None:
            instability_stats = {
                "min_samples": self.summary.min_instability_duration,
                "max_samples": self.summary.max_instability_duration,
                "mean_samples": round(self.summary.mean_instability_duration, 1),
                "median_samples": round(self.summary.median_instability_duration, 1),
            }

        output = {
            "data_source": self.summary.data_source,
            "validation_type": self.summary.validation_type,
            "execution_timestamp": self.summary.execution_timestamp,
            "sampling_interval_minutes": self.summary.sampling_interval_minutes,
            "total_zones": self.summary.total_zones,
            "zones_with_anomalies": self.summary.zones_with_anomalies,
            "total_samples_processed": self.summary.total_samples_processed,
            "total_anomalies_detected": self.summary.total_anomalies_detected,
            "anomalies_per_zone": self.summary.anomalies_per_zone,
            "percent_time_unstable": round(self.summary.percent_time_unstable, 1),
            "instability_duration_stats": instability_stats,
            "baseline_window_configured": self.summary.baseline_window_configured,
            "min_baseline_configured": self.summary.min_baseline_configured,
            "engine_version": self.summary.engine_version,
            "detections_by_source": self.summary.detections_by_source,
            "audit": {
                "alerts_before_baseline": self.summary.alerts_before_baseline,
                "warmup_alerts": self.summary.warmup_alerts,
                "avg_missingness_rate": round(self.summary.avg_missingness_rate, 4),
            },
            "notes": self.summary.notes,
        }

        with open(self.output_dir / "summary.json", "w") as f:
            json.dump(output, f, indent=2)

    def _write_per_zone_csv(self) -> None:
        if not self.summary or not self.summary.zone_results:
            return

        with open(self.output_dir / "per_zone_results.csv", "w") as f:
            f.write(
                "zone_id,total_samples,samples_processed,baseline_samples_used,warmup_samples,"
                "first_timestamp,last_timestamp,first_alert_timestamp,first_alert_cycle,"
                "alert_source,alert_reason,anomalies_detected,max_instability,avg_instability,"
                "instability_at_alert,state_at_alert,urgency_at_alert,drift_at_alert,novelty_at_alert,"
                "avg_novelty,avg_ensemble_agreement,degradation_mode,time_stable_pct,"
                "time_transition_pct,time_unstable_pct,time_lockin_pct,time_warmup_pct,"
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
                    f"{result.first_alert_cycle if result.first_alert_cycle is not None else ''},"
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
                        f"{record['timestamp']},"
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
        if not self.summary or not HAS_MATPLOTLIB:
            return

        plots_dir = self.output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        zone_names = [r.zone_id for r in self.summary.zone_results]
        anomalies = [r.anomalies_detected for r in self.summary.zone_results]
        max_instabilities = [r.max_instability_score for r in self.summary.zone_results]

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("Greenhouse Validation Summary", fontsize=16)

        axes[0].bar(zone_names, anomalies)
        axes[0].set_title("Anomalies Detected by Zone")
        axes[0].set_ylabel("Count")

        axes[1].bar(zone_names, max_instabilities)
        axes[1].set_title("Max Instability Score by Zone")
        axes[1].set_ylabel("Score")

        plt.tight_layout()
        plt.savefig(plots_dir / "summary.png", dpi=100, bbox_inches="tight")
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="WUR Autonomous Greenhouse Validation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", default="greenhouse_validation_results", type=Path)
    parser.add_argument("--baseline-window", default=288, type=int)
    parser.add_argument("--min-baseline", default=48, type=int)
    parser.add_argument("--structural-drift-threshold", default=0.5, type=float)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--plot", action="store_true")

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
