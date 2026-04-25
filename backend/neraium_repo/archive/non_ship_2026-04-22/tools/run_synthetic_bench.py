from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.evaluate_pipeline import run_eval


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    args = p.parse_args()

    rows = pd.read_csv(args.input).to_dict(orient="records")
    _results, summary = run_eval(rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
