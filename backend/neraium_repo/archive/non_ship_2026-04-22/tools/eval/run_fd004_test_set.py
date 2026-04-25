#!/usr/bin/env python3
r"""FD004 test set runner using TRUE lead time from RUL data.

This script uses the new StructuralDriftDetector with RUL_FD004.txt
to compute TRUE lead time (not degradation proxies).

Usage:
    python run_fd004_test_set.py [--max-units N] [--output-dir DIR] [--rul-path PATH]

Examples:
    # Run full analysis with auto-detected RUL file
    python run_fd004_test_set.py

    # Run on first 50 units
    python run_fd004_test_set.py --max-units 50

    # Specify RUL file location
    python run_fd004_test_set.py --rul-path /path/to/RUL_FD004.txt

    # Custom output directory
    python run_fd004_test_set.py --output-dir ./my_test_results
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from neraium_core.intelligence_stack.config import DetectorConfig
from .test_runner_true_lead_time_fd004 import TrueLeadTimeFD004Runner


def find_fd004_dataset() -> str:
    r"""Locate FD004 training dataset.

    Searches in common locations for train_FD004.txt
    """
    candidates = [
        "data/train_FD004.txt",
        "train_FD004.txt",
        Path(__file__).parent.parent / "data" / "train_FD004.txt",
        Path(__file__).parent.parent / "archive" / "test_data" / "train_FD004.txt",
    ]

    for path_str in candidates:
        path = Path(path_str)
        if path.exists():
            return str(path.resolve())

    raise FileNotFoundError(
        f"Could not find FD004 dataset. Searched:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + f"\n\nPlease provide --path argument or place train_FD004.txt in one of these locations."
    )


def main():
    """Run drift detection on FD004 with TRUE lead time."""
    parser = argparse.ArgumentParser(
        description="FD004 drift detection with TRUE lead time from RUL data"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to FD004 training dataset (auto-detects if not provided)",
    )
    parser.add_argument(
        "--rul-path",
        type=str,
        default=None,
        help="Path to RUL_FD004.txt (auto-detects if not provided)",
    )
    parser.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Limit to first N units",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="fd004_true_lead_time_results",
        help="Output directory (default: fd004_true_lead_time_results)",
    )

    args = parser.parse_args()

    # Find dataset path
    if args.path:
        dataset_path = args.path
        if not Path(dataset_path).exists():
            print(f"Error: Dataset file not found: {dataset_path}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            dataset_path = find_fd004_dataset()
            print(f"✓ Found FD004 dataset: {dataset_path}\n")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Run TRUE lead time evaluation
    try:
        print("=" * 70)
        print("FD004 TRUE LEAD TIME EVALUATION")
        print("Using: StructuralDriftDetector + RUL_FD004.txt")
        print("=" * 70)
        print()

        config = DetectorConfig()
        runner = TrueLeadTimeFD004Runner(detector_config=config, verbose=True)

        print("[1/2] Running drift detection...")
        results, summary = runner.run_fd004_true_lead_time(
            dataset_path=dataset_path,
            rul_path=args.rul_path,
            max_units=args.max_units,
        )

        print("[2/2] Saving results...")
        saved_files = runner.save_results(results, summary, args.output_dir)
        print(f"  ✓ Saved: {saved_files['csv'].name}")
        print(f"  ✓ Saved: {saved_files['json'].name}")

        print(f"\nOutput directory: {Path(args.output_dir).absolute()}\n")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
