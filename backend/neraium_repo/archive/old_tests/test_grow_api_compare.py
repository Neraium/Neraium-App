from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import DEFAULT_GROW_ENGINE, create_app
from neraium_core.grow.validation import load_records_from_path


def _client() -> TestClient:
    if not DEFAULT_GROW_ENGINE.list_states("room"):
        DEFAULT_GROW_ENGINE.ingest_records(load_records_from_path("examples/grow/demo_telemetry.json"))
    return TestClient(create_app())


def test_compare_endpoint_and_scope_lists() -> None:
    client = _client()
    plants = client.get("/plants")
    compare = client.get("/compare?scope_type=room&scope_id=flower-2")
    assert plants.status_code == 200
    assert len(plants.json()) >= 1
    assert compare.status_code == 200
    assert "summary" in compare.json()


def test_compare_entities_endpoint() -> None:
    client = _client()
    response = client.post("/compare/entities", json={"scope_type": "facility", "scope_ids": ["fac-chi-1", "fac-den-1"]})
    assert response.status_code == 200
    body = response.json()
    assert body["anchor"]["scope_type"] == "facility"
    assert len(body["peers"]) >= 1
