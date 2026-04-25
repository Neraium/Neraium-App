from datetime import datetime, timezone

from neraium_core.alignment import AlignmentEngine
from neraium_core.models import SystemDefinition
from neraium_core.telemetry import TelemetryPayload


def test_alignment_basic():
    definition = SystemDefinition(
        schema_version="1",
        system_id="sys_1",
        signals=[
            {
                "name": "a",
                "dtype": "float64",
                "unit": "x",
                "required_for_scoring": True,
            },
            {
                "name": "b",
                "dtype": "float64",
                "unit": "x",
                "required_for_scoring": True,
            },
        ],
        inference_window_seconds=60,
        raw_sample_period_seconds=5,
        vector_order=["a", "b"],
        max_forward_fill_windows=3,
        max_missing_signal_fraction=0.5,
    )

    engine = AlignmentEngine(definition)

    payload = TelemetryPayload(

        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        signals={"a": 1.0, "b": 2.0},
    )

    aligned = engine.align(payload.signals)

    assert aligned == [1.0, 2.0]
