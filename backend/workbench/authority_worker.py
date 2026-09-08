"""Thin external-process adapter; imports analytical behavior from Neraium-1.0."""
import contextlib
import importlib.metadata
import json
from pathlib import Path
import sys


def main():
    root, operation = Path(sys.argv[1]), sys.argv[2]
    sys.path[:0] = [str(root / "backend"), str(root / "shared/neraium-intelligence/src")]
    payload = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        from app.services.data_quality import profile_numeric_columns
        from app.services.telemetry_classification import build_telemetry_signal_catalog
        def profile(dataset):
            columns, rows = dataset["columns"], dataset["rows"]
            matrix = [["" if row.get(c) is None else str(row[c]) for c in columns] for row in rows]
            profiles = profile_numeric_columns(columns, matrix)
            catalog = build_telemetry_signal_catalog(columns, numeric_profiles=profiles, timestamp_column="timestamp")
            for signal in dataset["signals"]:
                name = signal["meaning"].strip()
                catalog[name].update({"source_column": signal["column"], "original_header": signal["column"],
                                      "display_name": name, "engineering_units": signal["unit"].strip() or None})
            return profiles, catalog

        columns, rows = payload["columns"], payload["rows"]
        profiles, catalog = profile(payload)
        paired = payload.get("mode") == "paired"
        if paired:
            reference = payload["reference"]
            reference_profiles, reference_catalog = profile(reference)
        response = {"contract": "neraium-workbench-authority.v1", "operation": operation,
                    "catalog": {"reference": reference_catalog, "comparison": catalog} if paired else catalog}
        if operation == "analyze" and paired:
            from app.engine.sii_engine import evaluate_sii
            # Paired SII derives its own catalog and operating context. Analyst
            # context stays in the immutable App request; it is not a prior.
            response["result"] = evaluate_sii(
                columns=columns, reference_rows=reference["rows"], comparison_rows=rows,
                numeric_profiles=profiles, timestamp_column="timestamp",
                signal_units={s["meaning"].strip(): s["unit"].strip() for s in payload["signals"]},
                config={"numeric_columns": columns[1:], "engineering_priors": []},
            )
        elif operation == "analyze":
            from app.engine.sii_engine import evaluate_sii
            response["result"] = evaluate_sii(
                columns=columns, rows=rows, numeric_profiles=profiles,
                timestamp_column="timestamp", telemetry_signal_catalog=catalog,
                config={"numeric_columns": columns[1:], "row_count_total": len(rows),
                        "temporal_config": {"max_rows": len(rows)},
                        "source_run_id": payload["run_id"], "engineering_priors": [],
                        "primary_room": payload["context"]},
            )
        response["runtime"] = {"python": sys.version, "packages": sorted(
            f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())}
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
