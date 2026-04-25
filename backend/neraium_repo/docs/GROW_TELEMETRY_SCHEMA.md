# GROW TELEMETRY SCHEMA

Each ingest record includes `timestamp`, `facility_id`, and at least one of `room_id`, `zone_id`, or `asset_id`.

Identity/context fields:

- `building_id`
- `asset_type`
- `subsystem_id`
- `line_id`
- `controller_id`
- `strain_or_crop_type`
- `growth_stage`
- `batch_id`
- `telemetry_source`

Supported telemetry includes the full cultivation scope requested in the product brief, including climate, HVAC/refrigeration, irrigation/fertigation, lighting, power, plant proxies, and workflow events. The canonical examples live in [examples/grow/demo_telemetry.json](/Users/Owner/Documents/neraium-core/examples/grow/demo_telemetry.json).
