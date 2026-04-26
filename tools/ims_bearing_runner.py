#!/usr/bin/env python3
"""
IMS Bearing Degradation Detection Runner for Neraium SII Engine.

Validates SII Engine on NASA IMS bearing vibration dataset.
Extracts time-domain features from vibration files and detects
structural instability using persistence and accumulation logic.

Features extracted per timestep:
- RMS (root mean square)
- Peak
- Kurtosis
- Crest factor
- Standard deviation
- Skewness

Usage:
  python tools/ims_bearing_runner.py \\
    --data-dir /path/to/ims/data \\
    --output results/ims_bearings \\
    --baseline-window 25 \\
    --drift-threshold 0.35 \\
    --use-inevitability-score \\
    --progress

IMS Data Format:
  Expected directory structure:
    data_dir/
      bearing1/
        2004.10.22.18.51.46
        2004.10.22.19.25.35
        ...
      bearing2/
        2004.10.22.18.51.46
        ...

  Each file contains vibration samples (one per line).
  Can be single column (single sensor) or multiple columns (4 bearing channels).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import numpy as np
from scipy import signal, stats

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from neraium_core.sii_engine_unified import SIIEngine, SIIEngineOutput


@dataclass
class IMSBearingResult:
    """Detection results for a single bearing."""
    bearing_name: str
    total_files: int
    baseline_files: int
    first_raw_alert_timestep: Optional[int] = None
    first_confirmed_alert_timestep: Optional[int] = None
    confirmed_detected: bool = False
    lead_time_steps: Optional[int] = None
    max_instability_score: float = 0.0
    unstable_percentage: float = 0.0
    confirmation_method: Optional[str] = None

    # Diagnostics
    first_drift_spike: float = 0.0
    final_instability: float = 0.0
    irreversibility_at_detection: float = 0.0
    error_message: Optional[str] = None


@dataclass
class IMSRunnerSummary:
    """Summary statistics for IMS runner."""
    total_bearings: int = 0
    bearings_detected: int = 0
    bearings_undetected: int = 0
    bearings_error: int = 0
    mean_lead_time: Optional[float] = None
    median_lead_time: Optional[float] = None
    detection_rate: float = 0.0
    runner_mode: str = "unsupervised"  # "unsupervised" or "known-failure"
    baseline_window: int = 25
    drift_threshold: float = 0.35
    confirmation_hits: int = 3
    confirmation_window: int = 5
    post_baseline_delay: int = 10
    use_inevitability_score: bool = False
    per_bearing_results: List[IMSBearingResult] = field(default_factory=list)


class IMSBearingRunner:
    """IMS Bearing degradation detection runner."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        baseline_window: int = 25,
        min_baseline: int = 10,
        drift_threshold: float = 0.35,
        inevitability_threshold: float = 0.5,
        confirmation_hits: int = 3,
        confirmation_window: int = 5,
        post_baseline_delay: int = 10,
        accumulation_window: int = 5,
        accumulation_threshold: float = 1.75,
        use_inevitability_score: bool = False,
        progress: bool = True,
        failure_index: Optional[int] = None,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.baseline_window = baseline_window
        self.min_baseline = min_baseline
        self.drift_threshold = drift_threshold
        self.inevitability_threshold = inevitability_threshold
        self.confirmation_hits = confirmation_hits
        self.confirmation_window = confirmation_window
        self.post_baseline_delay = post_baseline_delay
        self.accumulation_window = accumulation_window
        self.accumulation_threshold = accumulation_threshold
        self.use_inevitability_score = use_inevitability_score
        self.progress = progress and HAS_TQDM
        self.failure_index = failure_index

        # Determine mode
        self.runner_mode = "known-failure" if failure_index is not None else "unsupervised"

    def run(self) -> IMSRunnerSummary:
        """Run validation across all bearings in data directory."""
        print(f"🔬 Neraium SII Engine — IMS Bearing Degradation Detection")
        print(f"   Data directory: {self.data_dir}")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Runner mode: {self.runner_mode}")
        print(f"   Baseline window: {self.baseline_window} files (min: {self.min_baseline})")
        print(f"   Drift threshold: {self.drift_threshold}")
        print(f"\n   🔧 Confirmation Settings:")
        print(f"      confirmation_hits: {self.confirmation_hits}")
        print(f"      confirmation_window: {self.confirmation_window}")
        print(f"      post_baseline_delay: {self.post_baseline_delay}")
        print(f"      accumulation_window: {self.accumulation_window}")
        print(f"      accumulation_threshold: {self.accumulation_threshold}")
        print(f"      use_inevitability_score: {self.use_inevitability_score}")
        if self.use_inevitability_score:
            print(f"      (irreversibility_factor must be >= {self.inevitability_threshold} to confirm)")
        if self.runner_mode == "known-failure":
            print(f"      failure_index: {self.failure_index}")
        print()

        # Find all bearing directories
        bearing_dirs = sorted([d for d in self.data_dir.iterdir() if d.is_dir()])

        if not bearing_dirs:
            print(f"   ⚠️  No bearing directories found in {self.data_dir}")
            return IMSRunnerSummary()

        summary = IMSRunnerSummary(
            total_bearings=len(bearing_dirs),
            runner_mode=self.runner_mode,
            baseline_window=self.baseline_window,
            drift_threshold=self.drift_threshold,
            confirmation_hits=self.confirmation_hits,
            confirmation_window=self.confirmation_window,
            post_baseline_delay=self.post_baseline_delay,
            use_inevitability_score=self.use_inevitability_score,
        )

        iterator = bearing_dirs
        if self.progress:
            iterator = tqdm(
                iterator,
                desc="Processing bearings",
                total=len(bearing_dirs),
                unit="bearing",
            )

        for bearing_dir in iterator:
            result = self._process_bearing(bearing_dir)
            summary.per_bearing_results.append(result)

            if result.error_message:
                summary.bearings_error += 1
            elif result.confirmed_detected:
                summary.bearings_detected += 1
            else:
                summary.bearings_undetected += 1

        # Compute aggregate metrics
        self._compute_summary_metrics(summary)

        # Write outputs
        self._write_outputs(summary)
        self._print_summary(summary)

        return summary

    def _process_bearing(self, bearing_dir: Path) -> IMSBearingResult:
        """Process a single bearing directory."""
        bearing_name = bearing_dir.name

        try:
            # List all files (sorted by name, which should correspond to time order)
            files = sorted([f for f in bearing_dir.glob("*") if f.is_file()])

            if not files:
                return IMSBearingResult(
                    bearing_name=bearing_name,
                    total_files=0,
                    baseline_files=0,
                    error_message="No data files found",
                )

            # Determine failure index
            failure_idx = self.failure_index if self.failure_index else len(files)

            # Create engine
            engine = SIIEngine(baseline_window=self.baseline_window, recent_window=12)

            first_raw_alert_idx = None
            first_confirmed_alert_idx = None
            raw_alert_history = {}  # idx -> is_raw_alert
            drift_score_history = {}  # idx -> drift_score
            engine_output_history = {}  # idx -> full output

            max_instability = 0.0
            baseline_finalized_idx = 0
            baseline_ready = False

            # Process each file
            for idx, filepath in enumerate(files):
                try:
                    # Extract features from vibration file
                    features = self._extract_features(filepath)

                    if features is None or len(features) == 0:
                        continue

                    # Update engine
                    output = engine.update(features, timestamp=float(idx))
                    engine_output_history[idx] = output

                    # Track max instability
                    max_instability = max(max_instability, output.instability_score)

                    # Track baseline finalization
                    if not baseline_ready and engine.baseline_ready:
                        baseline_finalized_idx = idx
                        baseline_ready = True

                    # Store drift/inevitability score for accumulation
                    if self.use_inevitability_score:
                        drift_score_history[idx] = output.structural_inevitability_score
                    else:
                        drift_score_history[idx] = output.structural_drift

                    # Check for raw alert
                    is_raw_alert = self._check_raw_alert(output)
                    raw_alert_history[idx] = is_raw_alert

                    if is_raw_alert and first_raw_alert_idx is None:
                        first_raw_alert_idx = idx

                except Exception as e:
                    continue

            # Compute confirmation with irreversibility gate
            first_confirmed_alert_idx = None
            confirmation_method = None
            irreversibility_at_detection = 0.0

            for idx in sorted(raw_alert_history.keys()):
                # Post-baseline delay check
                if idx < baseline_finalized_idx + self.post_baseline_delay:
                    continue

                # Persistence check
                raw_alerts_in_window = sum(
                    1 for i in raw_alert_history.keys()
                    if (idx - self.confirmation_window < i <= idx) and raw_alert_history[i]
                )

                # Accumulation check
                rolling_instability = sum(
                    drift_score_history.get(i, 0.0)
                    for i in drift_score_history.keys()
                    if (idx - self.accumulation_window < i <= idx)
                )

                # Irreversibility gate
                cycle_output = engine_output_history.get(idx)
                if self.use_inevitability_score and cycle_output:
                    irreversibility_gate_met = cycle_output.irreversibility_factor >= self.inevitability_threshold
                    irreversibility_at_detection = cycle_output.irreversibility_factor
                else:
                    irreversibility_gate_met = True

                # Determine confirmation
                if irreversibility_gate_met:
                    if raw_alerts_in_window >= self.confirmation_hits:
                        first_confirmed_alert_idx = idx
                        confirmation_method = "persistence"
                        break
                    elif rolling_instability >= self.accumulation_threshold:
                        first_confirmed_alert_idx = idx
                        confirmation_method = "accumulation"
                        break

            # Determine detection
            confirmed_detected = first_confirmed_alert_idx is not None

            # Calculate lead time
            lead_time = None
            if confirmed_detected and self.runner_mode == "known-failure":
                lead_time = failure_idx - first_confirmed_alert_idx
                if lead_time < 0:
                    confirmed_detected = False
                    lead_time = None

            # Calculate unstable percentage
            unstable_count = sum(1 for v in raw_alert_history.values() if v)
            unstable_pct = 100.0 * unstable_count / max(len(raw_alert_history), 1)

            return IMSBearingResult(
                bearing_name=bearing_name,
                total_files=len(files),
                baseline_files=self.baseline_window if baseline_ready else 0,
                first_raw_alert_timestep=first_raw_alert_idx,
                first_confirmed_alert_timestep=first_confirmed_alert_idx,
                confirmed_detected=confirmed_detected,
                lead_time_steps=lead_time,
                max_instability_score=max_instability,
                unstable_percentage=unstable_pct,
                confirmation_method=confirmation_method,
                first_drift_spike=drift_score_history.get(first_raw_alert_idx, 0.0) if first_raw_alert_idx else 0.0,
                final_instability=output.instability_score if 'output' in locals() else 0.0,
                irreversibility_at_detection=irreversibility_at_detection,
            )

        except Exception as e:
            return IMSBearingResult(
                bearing_name=bearing_name,
                total_files=0,
                baseline_files=0,
                confirmed_detected=False,
                error_message=str(e)[:100],
            )

    def _extract_features(self, filepath: Path) -> Optional[np.ndarray]:
        """Extract time-domain features from a vibration file."""
        try:
            # Load vibration data
            data = np.loadtxt(filepath, dtype=float)

            if data.size == 0:
                return None

            # Handle 1D or 2D data
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            # Extract features from each channel and average
            features = []

            for channel in range(data.shape[1]):
                channel_data = data[:, channel]

                # RMS
                rms = float(np.sqrt(np.mean(channel_data**2)))
                features.append(rms)

                # Peak
                peak = float(np.max(np.abs(channel_data)))
                features.append(peak)

                # Kurtosis
                kurtosis = float(stats.kurtosis(channel_data))
                features.append(np.clip(kurtosis, -10, 10))  # Bound kurtosis

                # Crest factor
                crest = peak / (rms + 1e-9)
                features.append(np.clip(crest, 0, 50))  # Bound crest factor

                # Standard deviation
                std = float(np.std(channel_data))
                features.append(std)

                # Skewness
                skewness = float(stats.skew(channel_data))
                features.append(np.clip(skewness, -10, 10))  # Bound skewness

            return np.array(features, dtype=float)

        except Exception as e:
            return None

    def _check_raw_alert(self, output: SIIEngineOutput) -> bool:
        """Check if raw alert condition is met."""
        # Check regime
        if output.regime in ("TRANSITION", "UNSTABLE", "DEGRADED", "FAILURE"):
            return True

        # Check urgency
        if output.urgency in ("WATCH", "ALERT", "CRITICAL"):
            return True

        # Check threshold
        if self.use_inevitability_score:
            if output.structural_inevitability_score >= self.inevitability_threshold:
                return True
        else:
            if output.structural_drift >= self.drift_threshold:
                return True

        return False

    def _compute_summary_metrics(self, summary: IMSRunnerSummary) -> None:
        """Compute aggregate metrics."""
        summary.detection_rate = (
            100.0 * summary.bearings_detected / summary.total_bearings
            if summary.total_bearings > 0
            else 0.0
        )

        if summary.runner_mode == "known-failure":
            lead_times = [
                r.lead_time_steps
                for r in summary.per_bearing_results
                if r.lead_time_steps is not None and r.lead_time_steps > 0
            ]
            if lead_times:
                summary.mean_lead_time = float(np.mean(lead_times))
                summary.median_lead_time = float(np.median(lead_times))

    def _write_outputs(self, summary: IMSRunnerSummary) -> None:
        """Write results to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write summary JSON
        summary_data = {
            "total_bearings": summary.total_bearings,
            "bearings_detected": summary.bearings_detected,
            "bearings_undetected": summary.bearings_undetected,
            "bearings_error": summary.bearings_error,
            "detection_rate": summary.detection_rate,
            "runner_mode": summary.runner_mode,
            "baseline_window": summary.baseline_window,
            "drift_threshold": summary.drift_threshold,
            "confirmation_hits": summary.confirmation_hits,
            "use_inevitability_score": summary.use_inevitability_score,
        }

        if summary.mean_lead_time is not None:
            summary_data["mean_lead_time_steps"] = summary.mean_lead_time
            summary_data["median_lead_time_steps"] = summary.median_lead_time

        with open(self.output_dir / "summary.json", "w") as f:
            json.dump(summary_data, f, indent=2)

        # Write per-bearing CSV
        with open(self.output_dir / "per_bearing_results.csv", "w") as f:
            f.write(
                "bearing_name,total_files,baseline_files,"
                "first_raw_alert_timestep,first_confirmed_alert_timestep,"
                "confirmed_detected,lead_time_steps,max_instability_score,"
                "unstable_percentage,confirmation_method,"
                "first_drift_spike,final_instability,irreversibility_at_detection,"
                "error_message\n"
            )
            for result in summary.per_bearing_results:
                f.write(
                    f"{result.bearing_name},"
                    f"{result.total_files},"
                    f"{result.baseline_files},"
                    f"{result.first_raw_alert_timestep or '-'},"
                    f"{result.first_confirmed_alert_timestep or '-'},"
                    f"{result.confirmed_detected},"
                    f"{result.lead_time_steps or '-'},"
                    f"{result.max_instability_score:.4f},"
                    f"{result.unstable_percentage:.1f},"
                    f"{result.confirmation_method or '-'},"
                    f"{result.first_drift_spike:.4f},"
                    f"{result.final_instability:.4f},"
                    f"{result.irreversibility_at_detection:.4f},"
                    f"\"{result.error_message or ''}\"\n"
                )

        print(f"\n✅ Results written to {self.output_dir}")

    def _print_summary(self, summary: IMSRunnerSummary) -> None:
        """Print summary to console."""
        print("\n" + "=" * 70)
        print("📊 IMS BEARING DETECTION SUMMARY")
        print("=" * 70)
        print(f"\nTotal bearings: {summary.total_bearings}")
        print(f"  Detected: {summary.bearings_detected} ({summary.detection_rate:.1f}%)")
        print(f"  Undetected: {summary.bearings_undetected}")
        print(f"  Errors: {summary.bearings_error}")

        if summary.runner_mode == "known-failure" and summary.mean_lead_time:
            print(f"\nLead time (timesteps):")
            print(f"  Mean: {summary.mean_lead_time:.1f}")
            print(f"  Median: {summary.median_lead_time:.1f}")

        print()


def main():
    """Parse arguments and run IMS bearing detection."""
    parser = argparse.ArgumentParser(
        description="IMS bearing degradation detection using Neraium SII Engine"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Path to directory containing bearing subdirectories",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ims_results"),
        help="Output directory (default: ims_results)",
    )
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=25,
        help="Baseline window size (default: 25)",
    )
    parser.add_argument(
        "--min-baseline",
        type=int,
        default=10,
        help="Minimum baseline samples (default: 10)",
    )
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.35,
        help="Drift threshold for alert (default: 0.35)",
    )
    parser.add_argument(
        "--confirmation-hits",
        type=int,
        default=3,
        help="Raw alerts for persistence confirmation (default: 3)",
    )
    parser.add_argument(
        "--confirmation-window",
        type=int,
        default=5,
        help="Confirmation window size (default: 5)",
    )
    parser.add_argument(
        "--post-baseline-delay",
        type=int,
        default=10,
        help="Delay after baseline before confirming (default: 10)",
    )
    parser.add_argument(
        "--accumulation-window",
        type=int,
        default=5,
        help="Accumulation window size (default: 5)",
    )
    parser.add_argument(
        "--accumulation-threshold",
        type=float,
        default=1.75,
        help="Accumulation threshold (default: 1.75)",
    )
    parser.add_argument(
        "--use-inevitability-score",
        action="store_true",
        help="Use irreversibility gating for confirmation",
    )
    parser.add_argument(
        "--inevitability-threshold",
        type=float,
        default=0.5,
        help="Irreversibility gate threshold (default: 0.5)",
    )
    parser.add_argument(
        "--failure-index",
        type=int,
        default=None,
        help="Known failure index for lead time calculation (enables known-failure mode)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar",
    )

    args = parser.parse_args()

    try:
        runner = IMSBearingRunner(
            data_dir=args.data_dir,
            output_dir=args.output,
            baseline_window=args.baseline_window,
            min_baseline=args.min_baseline,
            drift_threshold=args.drift_threshold,
            inevitability_threshold=args.inevitability_threshold,
            confirmation_hits=args.confirmation_hits,
            confirmation_window=args.confirmation_window,
            post_baseline_delay=args.post_baseline_delay,
            accumulation_window=args.accumulation_window,
            accumulation_threshold=args.accumulation_threshold,
            use_inevitability_score=args.use_inevitability_score,
            progress=args.progress,
            failure_index=args.failure_index,
        )
        results = runner.run()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
