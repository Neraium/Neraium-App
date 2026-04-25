#!/usr/bin/env python3
"""Minimal pre-deploy smoke checks for Neraium API + dashboard."""

from __future__ import annotations

import sys
from typing import Any

from apps.api.main import create_app


REQUIRED_HEALTH_FIELDS = (
    "status",
    "version",
    "auth_configured",
    "persistence_available",
    "latest_result_available",
    "core_runtime_mode",
    "core_runtime_fallback",
    "core_runtime_notes",
)

DASHBOARD_MARKERS = (
    "Operator command summary",
    "Neraium",
)


def _build_test_client():
    try:
        from fastapi.testclient import TestClient
    except (ModuleNotFoundError, RuntimeError) as exc:
        message = str(exc)
        if getattr(exc, "name", None) == "httpx" or "requires the httpx package" in message:
            print("Install httpx to run tests: pip install httpx")
            return None
        raise

    app = create_app()

    try:
        return TestClient(app)
    except (ModuleNotFoundError, RuntimeError) as exc:
        message = str(exc)
        if getattr(exc, "name", None) == "httpx" or "requires the httpx package" in message:
            print("Install httpx to run tests: pip install httpx")
            return None
        raise


def _check_health(client: Any) -> bool:
    try:
        response = client.get("/health")
    except Exception as exc:
        print(f"FAIL: health endpoint request error: {exc}")
        return False

    print(f"/health status: {response.status_code}")
    if response.status_code != 200:
        print("FAIL: health endpoint not OK")
        return False

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"FAIL: health endpoint returned invalid JSON: {exc}")
        return False

    missing = [field for field in REQUIRED_HEALTH_FIELDS if field not in payload]
    if missing:
        print(f"FAIL: health response missing fields: {', '.join(missing)}")
        return False

    print("SUCCESS: health endpoint OK")
    print("SUCCESS: runtime fields detected")
    return True


def _check_dashboard(client: Any) -> bool:
    try:
        response = client.get("/dashboard")
    except Exception as exc:
        print(f"FAIL: dashboard endpoint request error: {exc}")
        return False

    print(f"/dashboard status: {response.status_code}")
    if response.status_code != 200:
        print("FAIL: dashboard endpoint not OK")
        return False

    html = response.text or ""
    missing = [marker for marker in DASHBOARD_MARKERS if marker not in html]
    if missing:
        print(f"FAIL: dashboard missing expected markers: {', '.join(missing)}")
        return False

    print("SUCCESS: dashboard endpoint OK")
    return True


def main() -> int:
    client = _build_test_client()
    if client is None:
        return 1

    checks = [
        _check_health(client),
        _check_dashboard(client),
    ]
    if all(checks):
        print("SUCCESS: pre-deploy checks passed")
        return 0

    print("FAIL: pre-deploy checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
