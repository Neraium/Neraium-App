from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from neraium_core.proof_package import run_proof_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neraium canonical multi-scenario proof package.")
    parser.add_argument("--output-dir", default="reports/proof_package")
    args = parser.parse_args()

    summary = run_proof_package(Path(args.output_dir))
    print(f"Generated proof package with {summary['scenario_count']} scenarios.")
    artifacts = summary.get("artifacts") or {}
    for label, path in artifacts.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
