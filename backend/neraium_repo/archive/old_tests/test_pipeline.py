from datetime import datetime, UTC

from neraium_core.pipeline import TelemetryPipeline
from neraium_core.telemetry import TelemetryPayload


def test_pipeline_constructs():
    pipeline = TelemetryPipeline()
    assert pipeline is not None


def test_process_returns_event():
    pipeline = TelemetryPipeline()

    payload = TelemetryPayload(
        timestamp=datetime.now(UTC),
        signals={
            "cpu_usage": 20.0,
            "memory_usage": 55.0,
        },
    )

    result = pipeline.process(payload)

    assert isinstance(result, dict)
    assert "aligned" in result
    assert "score" in result
    assert "status" in result
    assert "anomaly" in result
