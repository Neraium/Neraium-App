"""Bounded tabular intake. No imputation or semantic inference."""
import csv
import io
import json
import math
import re
from datetime import datetime, timezone

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000
MAX_COLUMNS = 64
SOURCE_CLOCK_MODE = "naive_historical_source_clock"
SOURCE_CLOCK_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("JSON objects must not contain duplicate keys.")
        obj[key] = value
    return obj


def parse(raw: bytes, filename: str) -> dict:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Supply a nonempty file of at most 10 MiB.")
    try:
        text = raw.decode("utf-8-sig")
        if filename.lower().endswith(".json"):
            rows = json.loads(text, parse_constant=lambda value: value, object_pairs_hook=unique_object)
            if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
                raise ValueError("JSON must be a nonempty array of flat row objects.")
            columns = list(dict.fromkeys(k for row in rows for k in row))
        elif filename.lower().endswith((".csv", ".tsv")):
            reader = csv.reader(io.StringIO(text), delimiter="\t" if filename.lower().endswith(".tsv") else ",", strict=True)
            columns = next(reader)
            rows = []
            for index, values in enumerate(reader, 2):
                if len(values) != len(columns):
                    raise ValueError(f"Row {index} has a different number of fields than the header.")
                rows.append(dict(zip(columns, values)))
                if len(rows) > MAX_ROWS:
                    raise ValueError("Maximum 10,000 rows; use explicitly scoped evaluations.")
        else:
            raise ValueError("Supported formats: UTF-8 CSV, TSV, or JSON row arrays.")
    except (UnicodeError, csv.Error, StopIteration, json.JSONDecodeError) as exc:
        raise ValueError("The file is not valid UTF-8 tabular data.") from exc
    if not rows or len(rows) > MAX_ROWS or not 2 <= len(columns) <= MAX_COLUMNS:
        raise ValueError("Supply 1–10,000 rows and 2–64 columns.")
    if len(set(columns)) != len(columns) or any(not c.strip() or len(c) > 160 for c in columns):
        raise ValueError("Headers must be unique, nonempty, and at most 160 characters.")
    if any(isinstance(v, (dict, list, bool)) for r in rows for v in r.values()):
        raise ValueError("Cells must be text, numbers, or null; flatten nested objects before upload.")
    return {"columns": columns, "rows": rows}


def timestamp(value, mode: str) -> str:
    try:
        if mode == SOURCE_CLOCK_MODE:
            if not isinstance(value, str) or not SOURCE_CLOCK_PATTERN.fullmatch(value):
                raise ValueError("Exact source-clock format required")
            datetime.fromisoformat(value)  # Validate calendar fields without attaching a timezone.
            return value
        if mode in {"epoch_seconds", "epoch_milliseconds"}:
            dt = datetime.fromtimestamp(float(value) / (1000 if mode == "epoch_milliseconds" else 1), timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("Timezone required")
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise ValueError("Use timezone-aware ISO, an explicit epoch unit, or exact YYYY-MM-DD HH:MM:SS source-clock timestamps in paired mode.") from exc


def validate(table: dict, column: str, mode: str, *, allow_source_clock: bool = False) -> dict:
    modes = {"iso", "epoch_seconds", "epoch_milliseconds"}
    if allow_source_clock:
        modes.add(SOURCE_CLOCK_MODE)
    if column not in table["columns"] or mode not in modes:
        raise ValueError("Select a timestamp column and explicit timestamp format.")
    times, invalid = [], []
    for i, row in enumerate(table["rows"]):
        try:
            times.append(timestamp(row.get(column), mode))
        except ValueError:
            invalid.append(i + 1)
    duplicates = len(times) - len(set(times))
    ordered = all(a < b for a, b in zip(times, times[1:]))
    signals = []
    for name in table["columns"]:
        if name == column:
            continue
        values, missing, bad = [], 0, 0
        for row in table["rows"]:
            v = row.get(name)
            if v is None or str(v).strip() == "":
                missing += 1
                continue
            try:
                number = float(v)
                if not math.isfinite(number):
                    bad += 1
                else:
                    values.append(number)
            except (ValueError, TypeError):
                bad += 1
        signals.append({"column": name, "numeric_count": len(values), "missing_count": missing,
                        "invalid_count": bad, "constant": bool(values) and min(values) == max(values)})
    warnings = []
    if invalid:
        warnings.append(f"Invalid timestamps in {len(invalid)} rows; first row indices: {invalid[:10]}.")
    if duplicates:
        warnings.append(f"{duplicates} duplicate timestamps; no rows were dropped or aggregated.")
    if not ordered:
        warnings.append("Timestamps are not strictly increasing; no rows were reordered.")
    if any(s["missing_count"] or s["invalid_count"] for s in signals):
        warnings.append("Missing/invalid cells exist. Missing values stay missing; invalid included signals block analysis.")
    return {"timestamp_column": column, "timestamp_mode": mode, "row_count": len(table["rows"]),
            "eligible_timestamps": not invalid and not duplicates and ordered, "warnings": warnings,
            "start": times[0] if times else None, "end": times[-1] if times else None, "signals": signals}


class TimestampReview(ValueError):
    """Unresolved intake choices; hints never constitute stored validation."""
    def __init__(self, column="", mode=""):
        super().__init__("Timestamp needs review: choose the unresolved column or format. Use timezone-aware ISO, an explicit epoch unit, or exact YYYY-MM-DD HH:MM:SS in paired mode.")
        self.choices = {"timestamp_column": column, "timestamp_mode": mode}


def auto_validate(table: dict, *, allow_source_clock: bool = False) -> dict:
    """Require every value to support one explicit interpretation.

    Headers prioritize inspection and can declare epoch units, but cannot override
    invalid values or resolve competing valid timestamp columns.
    """
    epoch_headers = {"epoch_seconds": "epoch_seconds", "timestamp_seconds": "epoch_seconds",
                     "epoch_milliseconds": "epoch_milliseconds",
                     "timestamp_milliseconds": "epoch_milliseconds"}

    def name(column):
        return re.sub(r"[\s-]+", "_", column.strip().lower())

    def obvious(column):
        return bool(set(name(column).split("_")) & {"timestamp", "datetime", "date", "time", "epoch"})

    candidates, numeric_columns = [], []
    for column in sorted(table["columns"], key=lambda c: not obvious(c)):
        mode = epoch_headers.get(name(column), "iso")
        if allow_source_clock and all(isinstance(row.get(column), str) and SOURCE_CLOCK_PATTERN.fullmatch(row[column])
                                      for row in table["rows"]):
            mode = SOURCE_CLOCK_MODE
        values = [row.get(column) for row in table["rows"]]
        try:
            # Use the validation/analysis parser on every row, never just a sample.
            for value in values:
                timestamp(value, mode)
            candidates.append((column, mode))
        except ValueError:
            if obvious(column):
                try:
                    if all(math.isfinite(float(value)) for value in values):
                        numeric_columns.append(column)
                except (ValueError, TypeError, OverflowError):
                    pass
    if len(candidates) == 1:
        return validate(table, *candidates[0], allow_source_clock=allow_source_clock)
    # Numeric units remain an operator decision regardless of magnitude.
    if not candidates and len(numeric_columns) == 1:
        raise TimestampReview(column=numeric_columns[0])
    modes = {mode for _, mode in candidates}
    raise TimestampReview(mode=next(iter(modes)) if len(modes) == 1 else "")


def analysis_input(table: dict, validation: dict, mapping: dict) -> dict:
    if not validation["eligible_timestamps"]:
        raise ValueError("Resolve invalid, duplicate, or unordered timestamps in a new source upload.")
    approved = mapping["signals"]
    expected = {s["column"] for s in validation["signals"]}
    if len(approved) != len(expected) or {s["column"] for s in approved} != expected:
        raise ValueError("Explicitly include or exclude every detected signal once.")
    selected = [s for s in approved if s["include"]]
    if not selected or len(selected) > 24:
        raise ValueError("Include 1–24 signals for a bounded evaluation.")
    names = [s["meaning"].strip() for s in selected]
    if len(names) != len(set(names)) or "timestamp" in names or any(not n for n in names):
        raise ValueError("Included signals require unique confirmed meanings, distinct from 'timestamp'.")
    quality = {s["column"]: s for s in validation["signals"]}
    if any(quality[s["column"]]["invalid_count"] for s in selected):
        raise ValueError("Included signals contain invalid numeric cells; exclude them or upload corrected data.")
    if any(not s["reason"].strip() for s in approved if not s["include"]):
        raise ValueError("Record a reason for every excluded signal.")
    rows = []
    for row in table["rows"]:
        t = timestamp(row.get(validation["timestamp_column"]), validation["timestamp_mode"])
        if mapping.get("start") and t < timestamp(mapping["start"], "iso"):
            continue
        if mapping.get("end") and t > timestamp(mapping["end"], "iso"):
            continue
        output = {"timestamp": t}
        for signal in selected:
            value = row.get(signal["column"])
            output[signal["meaning"].strip()] = None if value is None or str(value).strip() == "" else float(value)
        rows.append(output)
    if not rows:
        raise ValueError("The selected historical window contains no rows.")
    return {"columns": ["timestamp", *names], "rows": rows, "signals": selected,
            "context": mapping["context"], "baseline_policy": "authoritative_engine_selected",
            "transformations": ["Exact source-clock timestamps preserved; timezone not supplied"
                                if validation["timestamp_mode"] == SOURCE_CLOCK_MODE else "Explicit timestamp parsing to UTC",
                                "Numeric parsing; null preserved",
                                "Operator-confirmed signal names; no unit conversion",
                                "Inclusive selected time window; source order retained"]}


def paired_input(reference, comparison, reference_validation, comparison_validation, mapping):
    """Explicit shared mapping; compatibility is attested, never inferred from names."""
    if not mapping.get("pair_confirmed"):
        raise ValueError("Confirm both datasets describe the same physical system, signal identities, meanings and units; exclude outcome labels.")
    if mapping.get("start") or mapping.get("end"):
        raise ValueError("Paired evaluations use both complete supplied periods; interval restrictions are not supported.")
    if any(not s["unit"].strip() for s in mapping["signals"] if s["include"]):
        raise ValueError("Paired included signals require explicit matching units (use 'dimensionless' when confirmed).")
    # Exact source identities only in this first version. Different schemas require
    # an explicit future per-source mapping, never automatic renaming.
    if {s["column"] for s in reference_validation["signals"]} != {s["column"] for s in comparison_validation["signals"]}:
        raise ValueError("Incompatible signal schemas: paired mode requires identical signal columns and a shared mapping.")
    if (reference_validation["timestamp_mode"] == SOURCE_CLOCK_MODE) != (comparison_validation["timestamp_mode"] == SOURCE_CLOCK_MODE):
        raise ValueError("Paired timestamp modes must match: do not mix source-clock and timezone-aware datasets.")
    ref = analysis_input(reference, reference_validation, mapping)
    comp = analysis_input(comparison, comparison_validation, mapping)
    return {**comp, "mode": "paired", "reference": ref,
            "baseline_policy": "supplied_reference_authoritative_behavioral_baseline"}
