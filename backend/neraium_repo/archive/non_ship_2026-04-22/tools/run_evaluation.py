from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.ablation import run_ablation_suite
from evaluation.runner import run_evaluation
from evaluation.scenarios import build_benchmark_scenarios


def main() -> None:
    scenarios = build_benchmark_scenarios(seed=13, include_noise_variants=True)
    eval_out = run_evaluation(scenarios=scenarios, output_dir="reports/evaluation")
    ablation_out = run_ablation_suite(scenarios=scenarios, output_dir="reports/evaluation")

    final_report = {
        "scenario_count": len(scenarios),
        "models": sorted(eval_out["aggregate_metrics"].keys()),
        "aggregate_metrics": eval_out["aggregate_metrics"],
        "ablation": ablation_out,
    }
    outpath = Path("reports/evaluation/final_report.json")
    outpath.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(f"Evaluation complete. Final report: {outpath}")


if __name__ == "__main__":
    main()
