from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from neraium_core.features.feature_pipeline import build_feature_bundle


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--entities", nargs="*", default=[])
    args = p.parse_args()

    df = pd.read_csv(args.input)
    entity_filter = set(args.entities)
    if entity_filter:
        df = df[df["entity_id"].astype(str).isin(entity_filter)]

    feature_cols = [c for c in df.columns if c not in {"entity_id", "time", "scenario"}]
    for entity, sub in df.groupby("entity_id"):
        mat = sub.sort_values("time")[feature_cols].to_numpy(dtype=float)
        bundle = build_feature_bundle(mat)
        print(entity, {k: v.shape[0] for k, v in bundle.as_groups().items()})


if __name__ == "__main__":
    main()
