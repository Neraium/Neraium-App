#!/usr/bin/env python3
"""Terminal observer for true live PRONOSTIA ingestion.

This script sends one telemetry packet at a time to POST /api/live/ingest and
prints the engine response. The backend state only advances when the POST
request succeeds.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.live_pronostia_stream import ASSET_ID, generate_packets  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live PRONOSTIA ingestion terminal demo.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=150)
    parser.add_argument("--show-every", type=int, default=5)
    parser.add_argument("--stop-at-actionable", action="store_true")
    return parser.parse_args()


def post_json(url: str, payload: Dict[str, object]) -> Dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def reset_live_state(api_url: str) -> None:
    try:
        post_json(f"{api_url.rstrip('/')}/api/live/reset/{ASSET_ID}", {})
    except Exception:
        # The first ingest packet also resets cycle-1 streams; this is just a convenience.
        pass


def print_input(packet: Dict[str, object]) -> None:
    signals = packet["signals"]
    print(
        "[LIVE INPUT] "
        f"cycle={packet['cycle']} "
        f"rms={signals['rms']:.4f} "
        f"kurtosis={signals['kurtosis']:.4f} "
        f"crest={signals['crest_factor']:.4f}"
    )


def print_engine(result: Dict[str, object]) -> None:
    print(
        "[ENGINE] "
        f"drift={float(result['structural_drift_score']):.3f} "
        f"velocity={float(result['drift_velocity']):.3f} "
        f"instability={float(result['instability_score']):.3f} "
        f"state={result['state']}"
    )
    if result.get("event"):
        print(f"[EVENT] cycle={result['cycle']} {result['event']}")
        print(f"[WHY] {result['reason']}")


def main() -> int:
    args = parse_args()
    ingest_url = f"{args.api_url.rstrip('/')}/api/live/ingest"

    print("Live ingestion mode: engine updates only when telemetry packets arrive.")
    print("[LEAKAGE_GUARD] No failure endpoint is sent, shown, or used during streaming.")
    print(f"[TARGET] {ingest_url}")
    print()

    reset_live_state(args.api_url)

    try:
        for packet in generate_packets(args.max_cycles):
            result = post_json(ingest_url, packet)
            cycle = int(packet["cycle"])
            should_show = cycle == 1 or cycle % max(args.show_every, 1) == 0 or result.get("event")
            if should_show:
                print_input(packet)
                print_engine(result)
                print()

            if args.stop_at_actionable and result.get("event") == "ACTIONABLE_CONFIRMED":
                print("[STOP] Actionability confirmed; live observer stopped by --stop-at-actionable.")
                break

            time.sleep(max(args.interval, 0.0))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"[ERROR] Backend returned HTTP {exc.code}: {detail}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"[ERROR] Could not reach backend at {args.api_url}: {exc.reason}", file=sys.stderr)
        return 1

    print("[DONE] Live stream complete. No future endpoint was required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
