from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from neraium_core.sii.escalation import EscalationEngine


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if out != out:  # NaN
        return float(default)
    return float(out)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return False


def _dominant_zone_from_row(row: dict[str, Any]) -> str | None:
    for key in (
        "zone",
        "dominant_zone",
        "dominant_component",
        "dominant_driver",
        "dominant_driver_name",
    ):
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _write_csv_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_jsonl_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=False))
            f.write("\n")


def _unit_key(row: dict[str, Any]) -> str:
    for key in ("unit_id", "unit", "asset_id", "asset", "id"):
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return "unit_001"


def _cycle_value(row: dict[str, Any], index: int) -> int:
    raw = row.get("cycle", row.get("step", row.get("t", row.get("timestamp_index"))))
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return int(index)


def apply_operator_escalation(rows: list[dict[str, Any]], *, engine: EscalationEngine) -> list[dict[str, Any]]:
    drift_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=8))
    persistence: dict[str, int] = defaultdict(int)

    enriched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        unit_id = _unit_key(row)
        drift = _safe_float(row.get("structural_drift_score", row.get("drift", 0.0)), 0.0)
        hist = drift_history[unit_id]
        hist.append(float(drift))

        if drift >= engine.watch_threshold:
            persistence[unit_id] += 1
        else:
            persistence[unit_id] = 0

        drift_trend = 0.0
        if len(hist) >= 4:
            prior = list(hist)[-4:-1]
            drift_trend = float(drift) - (sum(prior) / float(len(prior)))

        spread_detected = _safe_bool(row.get("spread_detected", False)) or _safe_bool(row.get("divergence_alert", False))
        dominant_zone = _dominant_zone_from_row(row)

        esc = engine.evaluate(
            {
                "structural_drift_score": drift,
                "persistence": persistence[unit_id],
                "dominant_zone": dominant_zone,
                "drift_trend": drift_trend,
                "spread_detected": spread_detected,
            }
        )

        out = dict(row)
        out["unit_id"] = unit_id
        out["cycle"] = _cycle_value(row, idx)
        out["state"] = esc.state
        out["zone"] = esc.zone
        out["progression"] = esc.progression
        out["confidence"] = round(float(esc.confidence), 6)
        out["persistence"] = int(esc.persistence)
        enriched.append(out)

    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply operator escalation (NORMAL/WATCH/INTERVENE) onto cycle-level runner outputs.")
    parser.add_argument("--input", required=True, help="Path to cycle-level CSV or JSONL runner output.")
    parser.add_argument("--output-csv", default="", help="Output CSV path. If omitted, writes next to input with suffix _operator.csv.")
    parser.add_argument("--output-jsonl", default="", help="Output JSONL path. If omitted, writes next to input with suffix _operator.jsonl.")
    parser.add_argument("--watch-threshold", type=float, default=0.35)
    parser.add_argument("--intervene-threshold", type=float, default=0.65)
    parser.add_argument("--min-persistence-cycles", type=int, default=5)
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"input file not found: {input_path}")

    engine = EscalationEngine(
        watch_threshold=float(args.watch_threshold),
        intervene_threshold=float(args.intervene_threshold),
        min_persistence_cycles=int(args.min_persistence_cycles),
    )

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        rows = _load_csv_rows(input_path)
    elif suffix in {".jsonl", ".ndjson"}:
        rows = _load_jsonl_rows(input_path)
    else:
        raise SystemExit(f"unsupported input format: {suffix}")

    enriched = apply_operator_escalation(rows, engine=engine)

    stem = input_path.with_suffix("").name
    default_csv = input_path.with_name(f"{stem}_operator.csv")
    default_jsonl = input_path.with_name(f"{stem}_operator.jsonl")

    out_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else default_csv
    out_jsonl = Path(args.output_jsonl).expanduser().resolve() if args.output_jsonl else default_jsonl

    _write_csv_rows(out_csv, enriched)
    _write_jsonl_rows(out_jsonl, enriched)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

