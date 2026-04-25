import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_rest_payload(payload: Dict) -> Dict:
    timestamp = payload.get("timestamp") or now_iso()
    site_id = payload.get("site_id", "default-site")
    asset_id = payload.get("asset_id", "default-asset")
    sensor_values = payload.get("sensor_values", {})

    if not isinstance(sensor_values, dict):
        raise ValueError("sensor_values must be an object")

    normalized = {
        "timestamp": timestamp,
        "site_id": str(site_id),
        "asset_id": str(asset_id),
        "sensor_values": {},
    }

    for key, value in sensor_values.items():
        try:
            normalized["sensor_values"][str(key)] = float(value)
        except (TypeError, ValueError):
            normalized["sensor_values"][str(key)] = 0.0

    return normalized


def parse_csv_text(csv_text: str) -> List[Dict]:
    reader = csv.DictReader(StringIO(csv_text))
    rows = list(reader)

    if not rows:
        return []

    required = {"timestamp", "site_id", "asset_id"}
    headers = set(rows[0].keys())

    if not required.issubset(headers):
        raise ValueError("CSV must include timestamp, site_id, asset_id columns")

    sensor_columns = [h for h in rows[0].keys() if h not in required]
    frames: List[Dict] = []

    for row in rows:
        frame = {
            "timestamp": row.get("timestamp") or now_iso(),
            "site_id": row.get("site_id") or "default-site",
            "asset_id": row.get("asset_id") or "default-asset",
            "sensor_values": {},
        }

        for col in sensor_columns:
            raw = row.get(col, "")
            try:
                frame["sensor_values"][col] = float(raw)
            except (TypeError, ValueError):
                frame["sensor_values"][col] = 0.0

        frames.append(frame)

    return frames