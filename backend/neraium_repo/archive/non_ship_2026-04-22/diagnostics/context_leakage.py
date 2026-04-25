from __future__ import annotations

from pathlib import Path

from evaluation.representation_compare import (
    build_temporal_representation,
    compute_context_leakage_metrics,
    load_dataset,
)


def run_context_leakage_check(
    input_path: Path,
    *,
    entity_col: str | None = None,
    time_col: str | None = None,
    mode: str = "combined",
) -> dict[str, float | bool]:
    df, spec = load_dataset(input_path, entity_col=entity_col, time_col=time_col)
    rep = build_temporal_representation(df, spec, mode=mode)
    return compute_context_leakage_metrics(rep, spec)
