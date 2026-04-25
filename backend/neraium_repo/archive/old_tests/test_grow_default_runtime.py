from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_grow_is_default_runtime() -> None:
    client = TestClient(create_app())
    health = client.get("/health")
    body = health.json()
    assert health.status_code == 200
    assert body["deployment_mode"] == "grow"


def test_default_runtime_exposes_multi_scope_routes() -> None:
    client = TestClient(create_app())
    paths = {route.path for route in client.app.router.routes}
    for required in {
        "/portfolio/summary",
        "/plants",
        "/zones",
        "/rooms",
        "/subsystems",
        "/compare",
        "/compare/entities",
        "/plants/{plant_id}/state",
        "/facilities/{facility_id}/state",
    }:
        assert required in paths
