from __future__ import annotations

from neraium_core.markets.app.api import create_app


def test_legacy_markets_runtime_still_available() -> None:
    app = create_app()
    paths = {route.path for route in app.router.routes}
    assert "/health" in paths
    assert "/run-signals" in paths
