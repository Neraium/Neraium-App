from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(method: str, base_url: str, path: str, params: dict[str, str], payload: dict | None = None) -> dict:
    query = urlencode(params)
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, method=method, headers=headers)
    with urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a short operator workflow demo against the Neraium API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--customer-id", default="customer-a")
    parser.add_argument("--run-id", default="run-operator-demo")
    args = parser.parse_args()

    params = {"customer_id": args.customer_id, "run_id": args.run_id}
    start = datetime.now(tz=timezone.utc).replace(microsecond=0)
    frames = [
        {"pressure": 49.8, "temperature": 80.2, "flow": 12.1},
        {"pressure": 57.6, "temperature": 85.4, "flow": 11.3},
        {"pressure": 69.1, "temperature": 91.8, "flow": 10.2},
    ]

    print("Ingesting demo frames...")
    for i, sensors in enumerate(frames):
        payload = {
            "timestamp": (start + timedelta(minutes=i)).isoformat(),
            "site_id": "site-operator-demo",
            "asset_id": "asset-operator-demo",
            "customer_id": args.customer_id,
            "sensor_values": sensors,
        }
        out = request_json("POST", args.base_url, "/ingest/frame", params, payload)
        print(f"  cycle={out.get('cycle')} risk={out.get('risk_assessment', {}).get('risk_level')} recommendation={out.get('operational_recommendation', {}).get('recommended_action')}")

    state = request_json("GET", args.base_url, "/state", params)
    history = request_json("GET", args.base_url, "/history", {**params, "limit": "10"})

    current = state.get("state") or {}
    print("\nCurrent state summary")
    print(f"  timestamp: {current.get('timestamp')}")
    print(f"  cycle: {current.get('cycle')}")
    print(f"  risk_assessment: {json.dumps(current.get('risk_assessment', {}), sort_keys=True)}")
    print(f"  operational_recommendation: {json.dumps(current.get('operational_recommendation', {}), sort_keys=True)}")
    print(f"  explanation_text: {current.get('explanation_text')}")
    print(f"  events: {current.get('events')}")
    print(f"  memory_recall: {json.dumps(current.get('memory_recall', {}), sort_keys=True)}")

    print("\nRecent timeline")
    for row in history.get("history", []):
        risk = (row.get("risk_assessment") or {}).get("risk_level")
        rec = row.get("operational_recommendation") or {}
        rec_status = (rec.get("status") or {}).get("available")
        rec_conf = rec.get("recommendation_confidence")
        novelty = ((row.get("memory_recall") or {}).get("novelty") or {}).get("is_novel")
        print(
            f"  cycle={row.get('cycle')} risk={risk} rec_available={rec_status} rec_confidence={rec_conf} novelty={novelty} events={row.get('events')}"
        )


if __name__ == "__main__":
    main()
