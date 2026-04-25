from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .app import SIIApplication
from .config import SIIConfig
from .types import SIIResult


@dataclass
class SIIBenchmarkHarness:
    """
    Non-core benchmark/reporting harness isolated from engine internals.
    """

    app: SIIApplication

    @classmethod
    def from_env(cls) -> "SIIBenchmarkHarness":
        return cls(app=SIIApplication.from_env())

    @classmethod
    def from_config(cls, config: SIIConfig) -> "SIIBenchmarkHarness":
        return cls(app=SIIApplication.from_config(config))

    def run_payloads(self, payloads: list[dict[str, Any]]) -> list[SIIResult]:
        return self.app.run_payloads(payloads)

    def run_file_to_file(self, *, input_path: str | Path, output_path: str | Path) -> list[SIIResult]:
        results = self.app.run_input_file(input_path)
        self.app.write_output_file(output_path, results)
        return results

