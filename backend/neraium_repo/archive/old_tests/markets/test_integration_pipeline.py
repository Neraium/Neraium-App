from __future__ import annotations

from pathlib import Path

from neraium_core.markets.app.api import run_signal_pipeline
from neraium_core.markets.evidence.evidence_log import EvidenceLog


def test_pipeline_runs_with_sample_data(tmp_path: Path) -> None:
    evidence = EvidenceLog(tmp_path / "evidence.jsonl")
    signals = run_signal_pipeline(Path("neraium_core/markets/sample_data"), evidence)
    assert len(signals) >= 1
    assert evidence.path.exists()
