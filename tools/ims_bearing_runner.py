#!/usr/bin/env python3
"""
Production IMS Bearing Runner using SIIEngine with Irreversibility Gating.

Validates the updated SIIEngine on NASA IMS bearing dataset:
- Discovers IMS timestamp files recursively
- Extracts per-channel vibration features (RMS, std, peak, kurtosis, skewness, crest factor)
- Processes through unified SIIEngine pipeline
- Applies dual-gate detection (instability AND irreversibility)
- Outputs comprehensive validation results

Usage:
  python tools/ims_bearing_runner.py \\
    --data-dir /path/to/IMS_extracted \\
    --output results/ims_validation \\
    --baseline-window 100 \\
    --drift-threshold 0.55 \\
    --irreversibility-threshold 0.5 \\
    --confirmation-hits 5 \\
    --confirmation-window 10 \\
    --progress

Requirements:
- SIIEngine from neraium_core.sii_engine_unified
- numpy
- pandas
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from neraium_core.sii_engine_unified import SIIEngine, SIIEngineOutput


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class IMSTimestep:
    """Single IMS timestamp with extracted features."""
    bearing_name: str
    timestep: int
    file_name: str
    timestamp: float
    features: Dict[str, float]  # Channel-wise RMS values


@dataclass
class IMSDetectionResult:
    """Detection result for a single bearing."""
    bearing_name: str
    total_files: int
    baseline_files: int
    first_instability_timestep: Optional[int] = None
    first_irreversible_timestep: Optional[int] = None
    first_confirmed_alert_timestep: Optional[int] = None
    instability_at_detection: float = 0.0
    irreversibility_at_detection: float = 0.0
    velocity_at_detection: float = 0.0
    acceleration_at_detection: float = 0.0
    regime_at_detection: str = "UNKNOWN"
    urgency_at_detection: str = "UNKNOWN"
    unstable_percentage: float = 0.0
    irreversible_percentage: float = 0.0
    max_instability: float = 0.0
    max_irreversibility: float = 0.0
    error_message: Optional[str] = None

    def to_csv_row(self) -> Dict:
        """Convert to CSV row."""
        return {
            "bearing_name": self.bearing_name,
            "total_files": self.total_files,
            "baseline_files": self.baseline_files,
            "first_instability_timestep": self.first_instability_timestep or "",
            "first_irreversible_timestep": self.first_irreversible_timestep or "",
            "first_confirmed_alert_timestep": self.first_confirmed_alert_timestep or "",
            "instability_at_detection": f"{self.instability_at_detection:.6f}",
            "irreversibility_at_detection": f"{self.irreversibility_at_detection:.6f}",
            "velocity_at_detection": f"{self.velocity_at_detection:.6f}",
            "acceleration_at_detection": f"{self.acceleration_at_detection:.6f}",
            "regime_at_detection": self.regime_at_detection,
            "urgency_at_detection": self.urgency_at_detection,
            "unstable_percentage": f"{self.unstable_percentage:.2f}",
            "irreversible_percentage": f"{self.irreversible_percentage:.2f}",
            "max_instability": f"{self.max_instability:.6f}",
            "max_irreversibility": f"{self.max_irreversibility:.6f}",
            "error_message": self.error_message or "",
        }


@dataclass
class TimestepResult:
    """Per-timestep results."""
    bearing_name: str
    timestep: int
    file_name: str
    instability: float
    velocity: float
    acceleration: float
    irreversibility: float
    regime: str
    urgency: str
    raw_instability_gate: bool
    raw_irreversibility_gate: bool
    confirmed_alert: bool

    def to_csv_row(self) -> Dict:
        """Convert to CSV row."""
        return {
            "bearing_name": self.bearing_name,
            "timestep": self.timestep,
            "file_name": self.file_name,
            "instability": f"{self.instability:.6f}",
            "velocity": f"{self.velocity:.6f}",
            "acceleration": f"{self.acceleration:.6f}",
            "irreversibility": f"{self.irreversibility:.6f}",
            "regime": self.regime,
            "urgency": self.urgency,
            "raw_instability_gate": str(self.raw_instability_gate),
            "raw_irreversibility_gate": str(self.raw_irreversibility_gate),
            "confirmed_alert": str(self.confirmed_alert),
        }


# ============================================================================
# IMS DATA LOADER
# ============================================================================

class IMSDataLoader:
    """Loads and discovers IMS bearing data."""

    @staticmethod
    def discover_timestamp_files(data_dir: Path, debug: bool = False) -> Dict[str, List[Path]]:
        """
        Recursively discover IMS timestamp files.

        Files are:
        - Timestamp format: YYYY.MM.DD.HH.MM.SS (e.g., 2003.10.31.22.11.44)
        - Or standard data formats: .txt, .csv, .dat
        - Not .rar, .pdf, or __MACOSX
        - Not starting with ._

        Args:
            data_dir: Root directory to scan
            debug: Print debug information about file discovery

        Returns:
            Dict mapping bearing_name to sorted list of file paths
        """
        bearings: Dict[str, List[Path]] = {}
        timestamp_pattern = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
        data_extensions = {".txt", ".csv", ".dat"}

        print(f"Starting discovery in: {data_dir}")
        all_files = list(data_dir.rglob("*"))
        print(f"Total items scanned: {len(all_files)}")

        accepted_files = []
        scanned_count = 0

        for item in sorted(all_files):
            scanned_count += 1
            debug_msg = None

            # Skip directories and special files
            if item.is_dir():
                if debug and scanned_count <= 20:
                    debug_msg = f"[SKIP DIR] {item.name}"
                continue

            if item.name.startswith("._"):
                if debug and scanned_count <= 20:
                    debug_msg = f"[SKIP ._] {item.name}"
                continue

            if "__MACOSX" in str(item):
                if debug and scanned_count <= 20:
                    debug_msg = f"[SKIP MACOSX] {item.name}"
                continue

            if item.suffix.lower() in [".rar", ".pdf"]:
                if debug and scanned_count <= 20:
                    debug_msg = f"[SKIP {item.suffix}] {item.name}"
                continue

            file_name = item.name
            bearing_name = item.parent.name

            # Check if it matches timestamp pattern OR has data extension
            is_timestamp = timestamp_pattern.match(file_name)
            is_data_file = item.suffix.lower() in data_extensions

            if is_timestamp or is_data_file:
                if bearing_name not in bearings:
                    bearings[bearing_name] = []
                bearings[bearing_name].append(item)
                accepted_files.append(item)

                if debug and scanned_count <= 20:
                    pattern_match = "TIMESTAMP" if is_timestamp else f"DATA({item.suffix})"
                    debug_msg = f"[ACCEPT {pattern_match}] {file_name}"
            else:
                if debug and scanned_count <= 20:
                    debug_msg = f"[REJECT] {file_name}"

            if debug_msg:
                print(f"  {debug_msg}")

        print(f"Accepted data files: {len(accepted_files)}")
        if accepted_files:
            print(f"First accepted file: {accepted_files[0].name}")
            print(f"Last accepted file: {accepted_files[-1].name}")

        # Sort files chronologically by filename
        for bearing_name in bearings:
            bearings[bearing_name].sort(key=lambda p: p.name)

        return bearings

    @staticmethod
    def load_timestamp_file(file_path: Path) -> Optional[np.ndarray]:
        """
        Load a single timestamp file with vibration data.

        Expected format: whitespace-separated columns (channels)
        Returns: shape (num_samples, num_channels)
        """
        try:
            data = np.loadtxt(file_path, dtype=float)
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            return data
        except (ValueError, OSError, RuntimeError):
            return None


# ============================================================================
# FEATURE EXTRACTION
# ============================================================================

class FeatureExtractor:
    """Extracts vibration features from raw data."""

    @staticmethod
    def safe_kurtosis(x: np.ndarray) -> float:
        """Compute kurtosis (excess kurtosis)."""
        if len(x) < 4:
            return 0.0
        mean = np.mean(x)
        std = np.std(x)
        if std < 1e-12:
            return 0.0
        return float(np.mean(((x - mean) / std) ** 4) - 3)

    @staticmethod
    def safe_skewness(x: np.ndarray) -> float:
        """Compute skewness."""
        if len(x) < 3:
            return 0.0
        mean = np.mean(x)
        std = np.std(x)
        if std < 1e-12:
            return 0.0
        return float(np.mean(((x - mean) / std) ** 3))

    @staticmethod
    def safe_crest_factor(x: np.ndarray) -> float:
        """Compute crest factor (peak / RMS)."""
        rms = np.sqrt(np.mean(x ** 2))
        if rms < 1e-12:
            return 0.0
        return float(np.max(np.abs(x)) / rms)

    @staticmethod
    def extract_per_channel(data: np.ndarray) -> Dict[str, float]:
        """
        Extract features per channel.

        Returns:
            Dict with channel aggregates (RMS, std, peak, kurtosis, skewness, crest_factor)
        """
        if data is None or data.shape[0] == 0:
            return {}

        features = {}

        # Aggregate all channels
        flat = data.flatten()
        if len(flat) > 0:
            features["rms"] = float(np.sqrt(np.mean(flat ** 2)))
            features["std"] = float(np.std(flat))
            features["peak"] = float(np.max(np.abs(flat)))
            features["kurtosis"] = FeatureExtractor.safe_kurtosis(flat)
            features["skewness"] = FeatureExtractor.safe_skewness(flat)
            features["crest_factor"] = FeatureExtractor.safe_crest_factor(flat)

        return features


# ============================================================================
# RUNNER
# ============================================================================

class IMSBearingRunner:
    """Main IMS validation runner."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        baseline_window: int = 100,
        drift_threshold: float = 0.55,
        irreversibility_threshold: float = 0.5,
        confirmation_hits: int = 5,
        confirmation_window: int = 10,
        post_baseline_delay: int = 50,
        progress: bool = False,
        debug_discovery: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.baseline_window = baseline_window
        self.drift_threshold = drift_threshold
        self.irreversibility_threshold = irreversibility_threshold
        self.confirmation_hits = confirmation_hits
        self.confirmation_window = confirmation_window
        self.post_baseline_delay = post_baseline_delay
        self.progress = progress
        self.debug_discovery = debug_discovery

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Tuple[List[IMSDetectionResult], Dict[str, any]]:
        """
        Run validation on all discovered bearings.

        Returns:
            (results, summary_stats)
        """
        bearings = IMSDataLoader.discover_timestamp_files(self.data_dir, debug=self.debug_discovery)

        if not bearings:
            print("ERROR: No data files found. Check --data-dir.")
            return [], {}

        print(f"Found {len(bearings)} bearing(s)")

        results = []
        timestep_results = []
        iterator = bearings.items()

        if self.progress and HAS_TQDM:
            iterator = tqdm(iterator, desc="Processing bearings", unit="bearing")

        for bearing_name, files in iterator:
            result, timesteps = self._process_bearing(bearing_name, files)
            results.append(result)
            timestep_results.extend(timesteps)

        # Compute summary
        summary = self._compute_summary(results)

        # Export results
        self._export_results(results, timestep_results, summary)

        return results, summary

    def _process_bearing(
        self, bearing_name: str, files: List[Path]
    ) -> Tuple[IMSDetectionResult, List[TimestepResult]]:
        """Process a single bearing."""
        result = IMSDetectionResult(
            bearing_name=bearing_name,
            total_files=len(files),
            baseline_files=self.baseline_window,
        )

        timestep_results = []
        engine = SIIEngine(
            baseline_window=self.baseline_window,
            recent_window=self.baseline_window,
        )

        instability_gate_hits = []  # Track confirmed detections
        irreversibility_gate_hits = []

        for timestep, file_path in enumerate(files):
            try:
                # Load and extract features
                data = IMSDataLoader.load_timestamp_file(file_path)
                if data is None:
                    continue

                features = FeatureExtractor.extract_per_channel(data)
                if not features:
                    continue

                # Convert features to sensor vector
                sensor_vector = np.array(
                    [
                        features.get("rms", 0.0),
                        features.get("std", 0.0),
                        features.get("peak", 0.0),
                        features.get("kurtosis", 0.0),
                        features.get("skewness", 0.0),
                        features.get("crest_factor", 0.0),
                    ],
                    dtype=float,
                )

                # Process through engine
                output = engine.update(sensor_vector, float(timestep))

                # Track max values
                result.max_instability = max(
                    result.max_instability, output.instability_score
                )
                result.max_irreversibility = max(
                    result.max_irreversibility, output.irreversibility
                )

                # Check gates
                instability_gate = output.instability_score >= self.drift_threshold
                irreversibility_gate = output.irreversibility >= self.irreversibility_threshold

                if instability_gate:
                    instability_gate_hits.append(timestep)
                    if result.first_instability_timestep is None:
                        result.first_instability_timestep = timestep

                if irreversibility_gate:
                    irreversibility_gate_hits.append(timestep)
                    if result.first_irreversible_timestep is None:
                        result.first_irreversible_timestep = timestep

                # Check for confirmed alert (both gates AND post-baseline-delay)
                confirmed_alert = False
                if (
                    instability_gate
                    and irreversibility_gate
                    and timestep >= self.baseline_window + self.post_baseline_delay
                ):
                    # Count hits in recent window
                    window_start = max(
                        0, timestep - self.confirmation_window + 1
                    )
                    recent_instability = sum(
                        1
                        for t in instability_gate_hits
                        if window_start <= t <= timestep
                    )
                    recent_irreversibility = sum(
                        1
                        for t in irreversibility_gate_hits
                        if window_start <= t <= timestep
                    )

                    if (
                        recent_instability >= self.confirmation_hits
                        and recent_irreversibility >= self.confirmation_hits
                    ):
                        confirmed_alert = True
                        if result.first_confirmed_alert_timestep is None:
                            result.first_confirmed_alert_timestep = timestep
                            result.instability_at_detection = output.instability_score
                            result.irreversibility_at_detection = output.irreversibility
                            result.velocity_at_detection = output.drift_velocity
                            result.acceleration_at_detection = output.acceleration
                            result.regime_at_detection = output.regime
                            result.urgency_at_detection = output.urgency

                # Record timestep result
                timestep_results.append(
                    TimestepResult(
                        bearing_name=bearing_name,
                        timestep=timestep,
                        file_name=file_path.name,
                        instability=output.instability_score,
                        velocity=output.drift_velocity,
                        acceleration=output.acceleration,
                        irreversibility=output.irreversibility,
                        regime=output.regime,
                        urgency=output.urgency,
                        raw_instability_gate=instability_gate,
                        raw_irreversibility_gate=irreversibility_gate,
                        confirmed_alert=confirmed_alert,
                    )
                )

            except Exception as e:
                result.error_message = str(e)
                continue

        # Compute percentages
        if timestep_results:
            total_timesteps = len(timestep_results)
            unstable_count = sum(
                1 for tr in timestep_results if tr.raw_instability_gate
            )
            irreversible_count = sum(
                1 for tr in timestep_results if tr.raw_irreversibility_gate
            )
            result.unstable_percentage = 100.0 * unstable_count / total_timesteps
            result.irreversible_percentage = (
                100.0 * irreversible_count / total_timesteps
            )

        return result, timestep_results

    def _compute_summary(self, results: List[IMSDetectionResult]) -> Dict[str, any]:
        """Compute summary statistics."""
        summary = {
            "total_bearings": len(results),
            "detected_bearings": sum(
                1 for r in results if r.first_confirmed_alert_timestep is not None
            ),
            "mean_instability": np.mean(
                [r.max_instability for r in results if r.max_instability > 0]
            ),
            "mean_irreversibility": np.mean(
                [r.max_irreversibility for r in results if r.max_irreversibility > 0]
            ),
            "mean_unstable_percentage": np.mean(
                [r.unstable_percentage for r in results]
            ),
            "mean_irreversible_percentage": np.mean(
                [r.irreversible_percentage for r in results]
            ),
        }
        return summary

    def _export_results(
        self,
        results: List[IMSDetectionResult],
        timestep_results: List[TimestepResult],
        summary: Dict[str, any],
    ) -> None:
        """Export results to CSV and JSON."""
        # Export per_bearing_results.csv
        bearing_csv = self.output_dir / "per_bearing_results.csv"
        with open(bearing_csv, "w", newline="") as f:
            fieldnames = [
                "bearing_name",
                "total_files",
                "baseline_files",
                "first_instability_timestep",
                "first_irreversible_timestep",
                "first_confirmed_alert_timestep",
                "instability_at_detection",
                "irreversibility_at_detection",
                "velocity_at_detection",
                "acceleration_at_detection",
                "regime_at_detection",
                "urgency_at_detection",
                "unstable_percentage",
                "irreversible_percentage",
                "max_instability",
                "max_irreversibility",
                "error_message",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_csv_row())

        print(f"Exported {bearing_csv}")

        # Export per_timestep_results.csv
        if timestep_results:
            timestep_csv = self.output_dir / "per_timestep_results.csv"
            with open(timestep_csv, "w", newline="") as f:
                fieldnames = [
                    "bearing_name",
                    "timestep",
                    "file_name",
                    "instability",
                    "velocity",
                    "acceleration",
                    "irreversibility",
                    "regime",
                    "urgency",
                    "raw_instability_gate",
                    "raw_irreversibility_gate",
                    "confirmed_alert",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in timestep_results:
                    writer.writerow(result.to_csv_row())

            print(f"Exported {timestep_csv}")

        # Export summary.json
        summary_json = self.output_dir / "summary.json"
        with open(summary_json, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"Exported {summary_json}")

    def print_summary(self, results: List[IMSDetectionResult], summary: Dict) -> None:
        """Print summary to stdout."""
        print("\n" + "=" * 80)
        print("IMS BEARING VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total bearings: {summary.get('total_bearings', 0)}")
        print(f"Detected bearings: {summary.get('detected_bearings', 0)}")
        print(f"Mean instability: {summary.get('mean_instability', 0):.6f}")
        print(f"Mean irreversibility: {summary.get('mean_irreversibility', 0):.6f}")
        print(f"Mean unstable %: {summary.get('mean_unstable_percentage', 0):.2f}%")
        print(f"Mean irreversible %: {summary.get('mean_irreversible_percentage', 0):.2f}%")
        print("=" * 80 + "\n")


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Production IMS Bearing Runner with Irreversibility Gating"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Path to IMS data directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/ims_validation"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=100,
        help="Number of samples for baseline period",
    )
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.55,
        help="Threshold for instability detection",
    )
    parser.add_argument(
        "--irreversibility-threshold",
        type=float,
        default=0.5,
        help="Threshold for irreversibility detection",
    )
    parser.add_argument(
        "--confirmation-hits",
        type=int,
        default=5,
        help="Number of hits required in window for confirmation",
    )
    parser.add_argument(
        "--confirmation-window",
        type=int,
        default=10,
        help="Window size for counting confirmation hits",
    )
    parser.add_argument(
        "--post-baseline-delay",
        type=int,
        default=50,
        help="Delay after baseline before allowing detection",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar",
    )
    parser.add_argument(
        "--debug-discovery",
        action="store_true",
        help="Print first 20 scanned files and acceptance/rejection reasons",
    )

    args = parser.parse_args()

    runner = IMSBearingRunner(
        data_dir=args.data_dir,
        output_dir=args.output,
        baseline_window=args.baseline_window,
        drift_threshold=args.drift_threshold,
        irreversibility_threshold=args.irreversibility_threshold,
        confirmation_hits=args.confirmation_hits,
        confirmation_window=args.confirmation_window,
        post_baseline_delay=args.post_baseline_delay,
        progress=args.progress,
        debug_discovery=args.debug_discovery,
    )

    results, summary = runner.run()
    runner.print_summary(results, summary)


if __name__ == "__main__":
    main()
