from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neraium_core.service import StructuralMonitoringService


_NUMERIC_LINE = re.compile(r"^\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?(?:[\s,;]+[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)*\s*$")


def _looks_like_signal_file(path: Path) -> bool:
    if path.suffix.lower() not in {".txt", ".csv", ".json", ".npy", ".npz", ""}:
        return False
    if path.suffix.lower() in {".npy", ".npz"}:
        return True
    try:
        first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
    except OSError:
        return False
    if not first_line:
        return False
    return bool(_NUMERIC_LINE.match(first_line[0]))


def _discover_ims_input_path() -> Path | None:
    candidate_roots: list[Path] = []
    for key in ("IMS_DATASET_PATH", "IMS_EXTRACTED_PATH", "DATASET_ROOT", "RAW_DATA_ROOT"):
        raw = os.environ.get(key)
        if raw:
            candidate_roots.append(Path(raw))
    candidate_roots.extend(
        Path(p)
        for p in (
            "/workspace",
            "/workspace/data",
            "/data",
            "/datasets",
            "/runtime",
            "/mnt",
            "/tmp",
        )
    )

    best: tuple[int, Path] | None = None
    seen: set[Path] = set()
    for root in candidate_roots:
        if root in seen or not root.exists():
            continue
        seen.add(root)
        for dirpath, _, filenames in os.walk(root):
            directory = Path(dirpath)
            if ".git" in directory.parts or "node_modules" in directory.parts or "__pycache__" in directory.parts:
                continue
            files = [directory / name for name in filenames]
            signal_files = [f for f in files if _looks_like_signal_file(f)]
            if len(signal_files) < 25:
                continue
            score = len(signal_files)
            if "ims" in str(directory).lower():
                score += 1000
            if "extract" in str(directory).lower():
                score += 500
            if best is None or score > best[0]:
                best = (score, directory)
    return best[1] if best else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neraium on raw industrial data (tabular or directory blocks).")
    parser.add_argument("--input", default=None, help="Raw input path (file or directory).")
    parser.add_argument("--output", required=True, help="JSON output path.")
    parser.add_argument("--site-id", default="raw-telemetry", help="Site id used when source does not provide one.")
    parser.add_argument("--customer-id", default="default-customer", help="Customer id for runtime persistence.")
    parser.add_argument(
        "--preprocessing-mode",
        default="auto",
        choices=["auto", "none", "waveform_features"],
        help="Raw preprocessing mode. Auto infers by input type.",
    )
    parser.add_argument(
        "--validation-sample-size",
        type=int,
        default=None,
        help="Small-sample validation mode: only ingest first N timesteps.",
    )
    parser.add_argument(
        "--discover-ims",
        action="store_true",
        help="Discover IMS extracted dataset directory from runtime environment.",
    )
    parser.add_argument(
        "--require-real-dataset",
        action="store_true",
        help="Fail fast when input path cannot be resolved or does not exist.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser() if args.input else None
    if args.discover_ims:
        discovered = _discover_ims_input_path()
        if discovered is None and args.require_real_dataset:
            raise SystemExit("Unable to discover IMS dataset path in runtime environment.")
        input_path = discovered or input_path
    if input_path is None and args.require_real_dataset:
        raise SystemExit("No real dataset path provided. Use --input or --discover-ims.")
    if input_path is None:
        raise SystemExit("Missing --input (or pass --discover-ims to auto-resolve IMS).")
    if args.require_real_dataset and not input_path.exists():
        raise SystemExit(f"Resolved dataset path does not exist: {input_path}")

    service = StructuralMonitoringService()
    out = service.ingest_raw_industrial_data(
        str(input_path),
        customer_id=args.customer_id,
        site_id=args.site_id,
        preprocessing_mode=args.preprocessing_mode,
        sample_size=args.validation_sample_size,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2))

    diag = out["diagnostics"]
    print(
        "detected_input_type={detected_input_type} timestep_count={timestep_count} "
        "sensor_count={sensor_count} preprocessing_mode={preprocessing_mode} "
        "has_valid_signals={has_valid_signals}".format(**diag)
    )
    print(f"resolved_input_path={input_path}")
    print(f"processed_results={len(out['results'])} output={output_path}")


if __name__ == "__main__":
    main()
