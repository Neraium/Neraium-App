"""Configuration and path discovery for validation pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ValidationConfig:
    """Configuration for the validation pipeline."""

    fd001_path: Optional[Path] = None
    fd004_path: Optional[Path] = None
    ims_path: Optional[Path] = None
    igrow_path: Optional[Path] = None
    output_dir: Path = Path("validation_output")
    drift_threshold: float = 0.5
    datasets: list[str] = None
    dry_run: bool = False

    def __post_init__(self):
        """Ensure output_dir is a Path."""
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if self.datasets is None:
            self.datasets = ["fd001", "fd004", "ims", "igrow"]

    def get_path(self, dataset: str) -> Optional[Path]:
        """Get the path for a dataset."""
        paths = {
            "fd001": self.fd001_path,
            "fd004": self.fd004_path,
            "ims": self.ims_path,
            "igrow": self.igrow_path,
        }
        return paths.get(dataset)


def discover_local_paths(base_dir: Path = Path.cwd()) -> dict[str, Optional[Path]]:
    """Auto-discover dataset paths in common locations."""
    home = Path.home()
    search_dirs = [
        base_dir,
        base_dir / "data",
        home / "data",
        home / "Downloads",
    ]

    paths = {
        "fd001": None,
        "fd004": None,
        "ims": None,
        "igrow": None,
    }

    patterns = {
        "fd001": ["*FD001*", "fd001*"],
        "fd004": ["*FD004*", "fd004*"],
        "ims": ["*IMS*", "ims*"],
        "igrow": ["*igrow*", "igrow*"],
    }

    for dataset, pattern_list in patterns.items():
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for pattern in pattern_list:
                for match in search_dir.glob(f"{pattern}.csv"):
                    if match.is_file():
                        paths[dataset] = match
                        break
            if paths[dataset]:
                break

    return paths


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run full validation pipeline on local datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect datasets in current directory and ~/data
  python scripts/run_full_validation.py

  # With custom paths
  python scripts/run_full_validation.py \\
    --fd004-path ./FD004_ims_policy_results.csv \\
    --output-dir ./results

  # Dry-run to see what would be processed
  python scripts/run_full_validation.py --dry-run

  # Only specific datasets
  python scripts/run_full_validation.py --datasets fd001 fd004
        """,
    )

    parser.add_argument(
        "--fd001-path",
        type=Path,
        default=None,
        help="Path to FD001 results CSV file.",
    )
    parser.add_argument(
        "--fd004-path",
        type=Path,
        default=None,
        help="Path to FD004 results CSV file.",
    )
    parser.add_argument(
        "--ims-path",
        type=Path,
        default=None,
        help="Path to IMS results CSV file.",
    )
    parser.add_argument(
        "--igrow-path",
        type=Path,
        default=None,
        help="Path to igrow results CSV file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("validation_output"),
        help="Directory for validation output (default: validation_output).",
    )
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.5,
        help="Structural drift score threshold for early signal (default: 0.5).",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["fd001", "fd004", "ims", "igrow"],
        help="Datasets to process (default: all).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without running.",
    )

    return parser.parse_args()


def build_config(args: argparse.Namespace) -> ValidationConfig:
    """Build ValidationConfig from parsed arguments."""
    # Start with auto-discovered paths
    discovered = discover_local_paths()

    # Override with explicit arguments
    if args.fd001_path:
        discovered["fd001"] = args.fd001_path
    if args.fd004_path:
        discovered["fd004"] = args.fd004_path
    if args.ims_path:
        discovered["ims"] = args.ims_path
    if args.igrow_path:
        discovered["igrow"] = args.igrow_path

    return ValidationConfig(
        fd001_path=discovered["fd001"],
        fd004_path=discovered["fd004"],
        ims_path=discovered["ims"],
        igrow_path=discovered["igrow"],
        output_dir=args.output_dir,
        drift_threshold=args.drift_threshold,
        datasets=[d.lower() for d in args.datasets],
        dry_run=args.dry_run,
    )
