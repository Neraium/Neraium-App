from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot state-graph diagnostics over time.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    path = Path(args.input)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        ent = df.get("state_graph_transition_entropy", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        div = df.get("state_graph_graph_divergence_score", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        com = df.get("state_graph_path_commitment_score", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        node = df.get("state_graph_node_count", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
        edge = df.get("state_graph_edge_count", pd.Series(dtype=float)).fillna(0.0).astype(float).tolist()
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else [payload]
        ent, div, com, node, edge = [], [], [], [], []
        for r in rows:
            g = (r.get("state_graph") or (r.get("experimental_analytics", {}).get("state_graph", {})))
            ent.append(float(g.get("transition_entropy", 0.0)))
            div.append(float(g.get("graph_divergence_score", 0.0)))
            com.append(float(g.get("path_commitment_score", 0.0)))
            node.append(float(g.get("node_count", 0.0)))
            edge.append(float(g.get("edge_count", 0.0)))

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(ent, label="transition_entropy")
    axes[0].plot(div, label="graph_divergence_score")
    axes[0].plot(com, label="path_commitment_score")
    axes[0].legend()
    axes[0].set_title("State transition graph diagnostics")
    axes[1].plot(node, label="node_count")
    axes[1].plot(edge, label="edge_count")
    axes[1].plot([(e / max(1.0, n * (n - 1.0))) for n, e in zip(node, edge)], label="edge_density")
    axes[1].legend()
    axes[1].set_xlabel("time index")
    plt.tight_layout()
    plt.savefig(args.output, dpi=140)


if __name__ == "__main__":
    main()
