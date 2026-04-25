from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neraium_core.intelligence_stack.config import DetectorConfig
from neraium_core.intelligence_stack.detector import StructuralDriftDetector
from neraium_core.intelligence_stack.evaluation import load_cmapss_dataset
from neraium_core.intelligence_stack.sii_ml import create_siiml


@dataclass(frozen=True)
class PathMetrics:
    path_name: str
    units_evaluated: int
    coverage: float
    false_positive_rate: float
    mean_lead: float
    score: float


def _warning_index_from_siiml_outputs(outputs: list[dict[str, Any]]) -> int | None:
    for idx, out in enumerate(outputs):
        state = str(out.get("state", "")).strip().lower()
        if state in {"caution", "critical"}:
            return idx
    return None


def _warning_index_from_structural_detector(raw_unit_data: np.ndarray, config: DetectorConfig) -> int | None:
    detector = StructuralDriftDetector(config)
    scores = detector.process_unit(raw_unit_data)
    return scores.warning_index


def _compute_aggregate(
    warning_by_unit: dict[int, int | None],
    lengths_by_unit: dict[int, int],
    config: DetectorConfig,
    path_name: str,
) -> PathMetrics:
    if not warning_by_unit:
        return PathMetrics(
            path_name=path_name,
            units_evaluated=0,
            coverage=0.0,
            false_positive_rate=0.0,
            mean_lead=0.0,
            score=-9999.0,
        )

    covered = 0
    false_positives = 0
    leads: list[float] = []

    for unit_id, warning_index in warning_by_unit.items():
        n_cycles = lengths_by_unit[unit_id]
        healthy_end = max(config.min_reference_samples, int(n_cycles * config.healthy_fraction))
        degradation_onset = n_cycles - max(1, int(n_cycles * config.degradation_proxy_fraction))

        if warning_index is None:
            continue

        covered += 1
        if warning_index < healthy_end:
            false_positives += 1
        leads.append(float(degradation_onset - warning_index))

    n = len(warning_by_unit)
    coverage = covered / n
    fpr = false_positives / n
    mean_lead = float(np.mean(leads)) if leads else 0.0
    score = (
        mean_lead * config.score_lead_weight
        + coverage * config.score_coverage_weight
        - fpr * config.score_fpr_penalty
    )

    return PathMetrics(
        path_name=path_name,
        units_evaluated=n,
        coverage=coverage,
        false_positive_rate=fpr,
        mean_lead=mean_lead,
        score=score,
    )


def _format_table(rows: list[PathMetrics]) -> str:
    headers = ["path", "units", "coverage", "false_positive_rate", "mean_lead", "score"]
    body = [
        [
            r.path_name,
            str(r.units_evaluated),
            f"{r.coverage:.4f}",
            f"{r.false_positive_rate:.4f}",
            f"{r.mean_lead:.2f}",
            f"{r.score:.2f}",
        ]
        for r in rows
    ]

    widths = [len(h) for h in headers]
    for line in body:
        for i, cell in enumerate(line):
            widths[i] = max(widths[i], len(cell))

    def _fmt(line: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(line))

    sep = "-+-".join("-" * w for w in widths)
    output = [_fmt(headers), sep]
    output.extend(_fmt(line) for line in body)
    return "\n".join(output)


def run_fd004_path_comparison(
    *,
    train_path: str | None = None,
    output_dir: str,
    subset_units: int = 20,
    max_cycles_per_unit: int | None = None,
    healthy_fraction: float = 0.35,
    degradation_proxy_fraction: float = 0.30,
    min_reference_samples: int = 20,
    siiml_preset: str = "balanced",
) -> dict[str, Any]:
    config = DetectorConfig(
        dataset="FD004",
        healthy_fraction=healthy_fraction,
        degradation_proxy_fraction=degradation_proxy_fraction,
        min_reference_samples=min_reference_samples,
    )

    unit_data = load_cmapss_dataset("FD004", train_path=train_path)
    selected_units = sorted(unit_data)[:subset_units]

    siiml_warning_by_unit: dict[int, int | None] = {}
    platform_warning_by_unit: dict[int, int | None] = {}
    lengths_by_unit: dict[int, int] = {}

    for unit_id in selected_units:
        raw = np.asarray(unit_data[unit_id], dtype=float)
        if config.exclude_operating_settings:
            raw = raw[:, 3:]

        if max_cycles_per_unit is not None and max_cycles_per_unit > 0:
            raw = raw[:max_cycles_per_unit]

        n_cycles = len(raw)
        if n_cycles < 2 * min_reference_samples:
            continue

        lengths_by_unit[unit_id] = n_cycles
        sensors = [f"s{i+1}" for i in range(raw.shape[1])]
        baseline_end = max(min_reference_samples, int(n_cycles * healthy_fraction))
        baseline = raw[:baseline_end]

        siiml = create_siiml(sensors=sensors, baseline_data=baseline, preset=siiml_preset)
        siiml_outputs = [
            siiml.assess(
                {sensor: float(raw[t, s_idx]) for s_idx, sensor in enumerate(sensors)},
                current_cycle_index=t,
                total_cycles=n_cycles,
            )
            for t in range(n_cycles)
        ]
        siiml_warning_by_unit[unit_id] = _warning_index_from_siiml_outputs(siiml_outputs)

        platform_warning_by_unit[unit_id] = _warning_index_from_structural_detector(raw, config)

    siiml_metrics = _compute_aggregate(siiml_warning_by_unit, lengths_by_unit, config, "sii_ml_checkpoint")
    platform_metrics = _compute_aggregate(platform_warning_by_unit, lengths_by_unit, config, "full_platform")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_path = output_path / "fd004_path_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "units_evaluated", "coverage", "false_positive_rate", "mean_lead", "score"],
        )
        writer.writeheader()
        for row in (siiml_metrics, platform_metrics):
            writer.writerow(
                {
                    "path": row.path_name,
                    "units_evaluated": row.units_evaluated,
                    "coverage": round(row.coverage, 6),
                    "false_positive_rate": round(row.false_positive_rate, 6),
                    "mean_lead": round(row.mean_lead, 6),
                    "score": round(row.score, 6),
                }
            )

    table = _format_table([siiml_metrics, platform_metrics])
    summary = {
        "config": {
            "train_path": str(train_path),
            "subset_units": subset_units,
            "max_cycles_per_unit": max_cycles_per_unit,
            "healthy_fraction": healthy_fraction,
            "degradation_proxy_fraction": degradation_proxy_fraction,
            "min_reference_samples": min_reference_samples,
            "siiml_preset": siiml_preset,
            "units_evaluated": len(lengths_by_unit),
        },
        "results": [siiml_metrics.__dict__, platform_metrics.__dict__],
        "comparison_table": table,
        "csv_path": str(csv_path),
    }

    json_path = output_path / "fd004_path_comparison.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nFD004 path comparison")
    print(table)
    print(f"\nCSV: {csv_path}")
    print(f"JSON: {json_path}")

    return summary


def main() -> None:
    os.environ["NERAIUM_FAST_MODE"] = "1"
    os.environ["NERAIUM_INCREMENTAL"] = "1"
    os.environ["NERAIUM_TRANSITION_AWARE"] = "1"

    parser = argparse.ArgumentParser(
        description=(
            "Benchmark FD004 subset using both the isolated SII-ML checkpoint path and the full Neraium platform path."
        )
    )
    parser.add_argument(
        "--train-path",
        default=None,
        help=(
            "Optional path to train_FD004.txt. "
            "If omitted, dataset discovery searches train_FD004.txt in cwd and data/."
        ),
    )
    parser.add_argument("--output-dir", default="reports/fd004_path_comparison", help="Directory for CSV/JSON outputs")
    parser.add_argument("--subset-units", type=int, default=20, help="Number of FD004 units to evaluate")
    parser.add_argument(
        "--max-cycles-per-unit",
        type=int,
        default=None,
        help="Optional cap on cycles per selected unit",
    )
    parser.add_argument("--healthy-fraction", type=float, default=0.35)
    parser.add_argument("--degradation-proxy-fraction", type=float, default=0.30)
    parser.add_argument("--min-reference-samples", type=int, default=20)
    parser.add_argument("--siiml-preset", default="balanced")
    args = parser.parse_args()

    run_fd004_path_comparison(
        train_path=args.train_path,
        output_dir=args.output_dir,
        subset_units=args.subset_units,
        max_cycles_per_unit=args.max_cycles_per_unit,
        healthy_fraction=args.healthy_fraction,
        degradation_proxy_fraction=args.degradation_proxy_fraction,
        min_reference_samples=args.min_reference_samples,
        siiml_preset=args.siiml_preset,
    )


if __name__ == "__main__":
    main()
