from __future__ import annotations

import os

from ui.app import create_gradio_app

DEFAULT_PORT = 7860


def _resolve_port() -> int:
    raw = os.getenv("PORT")
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    if port <= 0 or port > 65535:
        return DEFAULT_PORT
    return port


def main() -> None:
    app = create_gradio_app()
    app.launch(
        inbrowser=False,
        server_name="0.0.0.0",
        server_port=_resolve_port(),
        show_error=True,
    )


if __name__ == "__main__":
    main()
