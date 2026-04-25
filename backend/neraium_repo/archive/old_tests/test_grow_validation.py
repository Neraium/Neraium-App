from __future__ import annotations

from neraium_core.grow.validation import parse_csv_text, parse_json_payload


def test_grow_json_validation_accepts_supported_signal_contract() -> None:
    records = parse_json_payload(
        {
            "records": [
                {
                    "timestamp": "2026-04-03T08:00:00Z",
                    "site_id": "site-1",
                    "facility_id": "fac-1",
                    "room_id": "flower-1",
                    "zone_id": "flower-1-canopy",
                    "plant_id": "cluster-a",
                    "asset_id": "ahu-1",
                    "zone_temperature": 76.0,
                    "zone_relative_humidity": 59.0,
                    "load_percent": 61.0,
                }
            ]
        }
    )
    assert len(records) == 1
    assert records[0].signals["zone_temperature"] == 76.0


def test_grow_csv_validation_requires_entity_identity() -> None:
    csv_text = "timestamp,facility_id,zone_temperature\n2026-04-03T08:00:00Z,fac-1,76.0\n"
    try:
        parse_csv_text(csv_text)
    except ValueError as exc:
        assert "one of plant_id, zone_id, room_id, asset_id, or subsystem_id is required" in str(exc)
    else:
        raise AssertionError("expected grow identity validation to fail")
