from __future__ import annotations

"""Compatibility entrypoint for the hardened SII CLI contract.

This module intentionally delegates to :mod:`neraium_core.sii_cli` so that
``python -m neraium_core.sii.cli`` and ``neraium_core.sii_cli`` share the same
ingestion, summary, and exit-code behavior.
"""

import sys
from contextlib import contextmanager
from typing import Iterator

from neraium_core import sii_cli


@contextmanager
def _argv_scope(argv: list[str] | None) -> Iterator[None]:
    if argv is None:
        yield
        return

    original = sys.argv
    sys.argv = ["python -m neraium_core.sii.cli", *argv]
    try:
        yield
    finally:
        sys.argv = original


def main(argv: list[str] | None = None) -> int:
    """Run the canonical hardened SII CLI implementation."""
    with _argv_scope(argv):
        return sii_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
