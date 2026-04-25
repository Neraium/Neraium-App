from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_investor_proof_demo import run_demo


def _json_request(method: str, url: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url=url, method=method.upper(), data=body, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw or "{}")


def _run_live_replay(base_url: str, customer_id: str, max_frames: int, poll_attempts: int = 8) -> dict:
    start_url = f"{base_url.rstrip('/')}/demo/cmapss/start?{urlencode({'customer_id': customer_id})}"
    started = _json_request("POST", start_url, {"customer_id": customer_id, "max_frames": max_frames})
    run_id = str(started.get("run_id") or "")
    if not run_id:
        raise RuntimeError("Replay start did not return run_id")
    status_url = f"{base_url.rstrip('/')}/demo/cmapss/status?{urlencode({'customer_id': customer_id, 'run_id': run_id})}"
    last_status: dict = {}
    for _ in range(max(1, poll_attempts)):
        last_status = _json_request("GET", status_url)
        if str(last_status.get("status") or "").lower() in {"ready", "failed", "empty"}:
            break
        time.sleep(1.0)
    proof_url = f"{base_url.rstrip('/')}/demo/cmapss/proof-summary?{urlencode({'customer_id': customer_id, 'run_id': run_id})}"
    proof = _json_request("GET", proof_url)
    return {"run_id": run_id, "status": last_status, "proof": proof}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neraium canonical investor demo flow with backup artifacts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customer-id", default="customer-a")
    parser.add_argument("--max-frames", type=int, default=240)
    parser.add_argument("--output-dir", default="reports/demo_proof")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    json_path, md_path, csv_path = run_demo(output_dir)

    live = {"mode": "backup_only", "reason": "live_replay_unavailable"}
    try:
        live = _run_live_replay(args.base_url, args.customer_id, args.max_frames)
        live["mode"] = "live_plus_backup"
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        live = {"mode": "backup_only", "reason": str(exc)}

    session_summary = {
        "startup": {
            "base_url": args.base_url,
            "customer_id": args.customer_id,
            "max_frames": args.max_frames,
        },
        "live": live,
        "backup_artifacts": {
            "report_json": str(json_path),
            "report_markdown": str(md_path),
            "timeline_csv": str(csv_path),
        },
        "demo_checklist": [
            "Confirm read-only/non-actuating language before opening dashboard.",
            "Show canonical story: normal -> drift -> rising instability -> actionable risk.",
            "Use proof summary to show lead over threshold-style detection.",
            "If API replay fails, present backup artifacts from reports/demo_proof.",
        ],
    }
    session_path = output_dir / "canonical_demo_session.json"
    session_path.write_text(json.dumps(session_summary, indent=2), encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {session_path}")
    print(f"Mode: {session_summary['live']['mode']}")


if __name__ == "__main__":
    main()
