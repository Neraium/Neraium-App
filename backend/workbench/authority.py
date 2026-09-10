"""Process boundary to a pinned, clean Neraium-1.0 checkout. No fallback."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONTRACT = "neraium-workbench-authority.v1"
SUPPORTED_COMMIT = "b790479f0abcb90aa71f7677d10aa542222b55c8"


class AuthorityError(RuntimeError):
    pass


def identity():
    root = os.environ.get("NERAIUM_AUTHORITY_ROOT", "")
    commit = os.environ.get("NERAIUM_AUTHORITY_COMMIT") or SUPPORTED_COMMIT
    if not root or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise AuthorityError("Configure a clean Neraium-1.0 checkout and its full commit SHA.")
    if commit != SUPPORTED_COMMIT:
        raise AuthorityError("This authority revision has not been contract-validated by this workbench.")
    try:
        actual = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", root, "status", "--porcelain", "--untracked-files=all"], text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AuthorityError("The configured authority checkout cannot be verified.") from exc
    if actual != commit or dirty.strip():
        raise AuthorityError("Authority must match the pinned commit with no modified or untracked files.")
    return {"repository": "Neraium/Neraium-1.0", "commit": commit,
            "callable": "app.engine.sii_engine.evaluate_sii", "adapter_contract": CONTRACT,
            "adapter_sha256": hashlib.sha256(Path(__file__).with_name("authority_worker.py").read_bytes()).hexdigest()}


def call(payload: dict, operation: str = "analyze") -> dict:
    before = identity()
    worker = Path(__file__).with_name("authority_worker.py")
    python = os.environ.get("NERAIUM_AUTHORITY_PYTHON", sys.executable)
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "SYSTEMROOT"}}
    env.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1", "NERAIUM_ENV": "development"})
    try:
        with tempfile.TemporaryDirectory(prefix="neraium-evaluation-") as scratch:
            env["NERAIUM_RUNTIME_DIR"] = scratch
            process = subprocess.run(
                [python, "-I", "-B", str(worker), str(Path(os.environ["NERAIUM_AUTHORITY_ROOT"]).resolve()), operation],
                input=json.dumps(payload, allow_nan=False), text=True, capture_output=True,
                cwd=scratch, env=env, timeout=120 if operation == "analyze" else 30,
            )
        if process.returncode:
            raise AuthorityError("Authoritative process failed. Check the pinned interpreter's dependencies; no result was substituted.")
        response = json.loads(process.stdout)
        if not isinstance(response, dict) or response.get("contract") != CONTRACT or response.get("operation") != operation:
            raise AuthorityError("Authority response contract mismatch.")
        if not isinstance(response.get("catalog"), dict) or not isinstance(response.get("runtime"), dict):
            raise AuthorityError("Authority provenance or signal catalog is missing.")
        if operation == "analyze":
            result = response.get("result", {})
            if not isinstance(result, dict) or result.get("engine") != {"name": "neraium_sii", "version": "v2"} or result.get("status") not in {"complete", "limited", "failed"}:
                raise AuthorityError("Unsupported authoritative result semantics.")
            if (not isinstance(result.get("findings"), list) or any(not isinstance(result.get(k), dict) for k in ("uncertainty", "processing_trace", "relationship_analysis", "persistence_analysis"))):
                raise AuthorityError("Authoritative evidence sections are missing or malformed.")
            if payload.get("mode") == "paired":
                supplied = result.get("supplied_reference")
                governed = result.get("analysis_result")
                if (not isinstance(supplied, dict) or supplied.get("contract_version") not in {"supplied-reference-v1", "supplied-reference-v1.1"}
                        or any(not isinstance(supplied.get(role), dict) for role in ("reference", "comparison"))
                        or not isinstance(governed, dict) or not isinstance(governed.get("insights"), list)
                        or not isinstance(governed.get("sii_evidence"), dict)
                        or not isinstance(result.get("temporal_analysis"), dict)):
                    raise AuthorityError("Unsupported paired authoritative evidence contract.")
                if supplied["contract_version"] == "supplied-reference-v1.1":
                    if (supplied.get("timestamp_mode") != "naive_historical_source_clock"
                            or supplied.get("source_timezone") != {"status": "timezone_not_supplied", "value": None}
                            or supplied.get("timestamp_format") != "%Y-%m-%d %H:%M:%S"
                            or supplied.get("timing_basis") != "direct_source_clock_datetime_differences"
                            or governed["sii_evidence"].get("supplied_reference") != supplied
                            or any(supplied[role].get("source_timestamps") != [r["timestamp"] for r in dataset["rows"]]
                                   for role, dataset in (("reference", payload["reference"]), ("comparison", payload)))):
                        raise AuthorityError("Unsupported source-clock authoritative provenance.")
        if identity() != before:
            raise AuthorityError("Authority changed during execution; result rejected.")
        response["identity"] = before
        return response
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise AuthorityError("Authority unavailable, timed out, or returned invalid JSON; no fallback was used.") from exc
