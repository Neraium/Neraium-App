"""Root ASGI entrypoint for cloud runtimes (App Runner, Railway, etc.)."""

from apps.api.main import app

__all__ = ["app"]
