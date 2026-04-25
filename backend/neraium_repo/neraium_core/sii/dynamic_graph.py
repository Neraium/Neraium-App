from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DynamicGraphMetrics:
    edge_persistence: float
    edge_birth_rate: float
    edge_death_rate: float
    centrality_shift: float
    fragility_score: float


def compute_dynamic_graph_metrics(
    *,
    current_adj: np.ndarray,
    prev_adj: np.ndarray | None,
    current_degree_centrality: dict[str, float],
    prev_degree_centrality: dict[str, float] | None,
    structural_drift: float,
    coupling_score: float,
) -> DynamicGraphMetrics:
    curr = np.asarray(current_adj, dtype=float)
    if prev_adj is None or np.asarray(prev_adj).shape != curr.shape:
        return DynamicGraphMetrics(
            edge_persistence=1.0,
            edge_birth_rate=0.0,
            edge_death_rate=0.0,
            centrality_shift=0.0,
            fragility_score=float(max(0.0, min(1.0, 0.45 * structural_drift + 0.55 * coupling_score))),
        )

    prev = np.asarray(prev_adj, dtype=float)
    curr_edges = curr > 0.0
    prev_edges = prev > 0.0
    prev_count = float(np.sum(prev_edges))
    curr_count = float(np.sum(curr_edges))

    persistent = float(np.sum(curr_edges & prev_edges))
    births = float(np.sum(curr_edges & ~prev_edges))
    deaths = float(np.sum(~curr_edges & prev_edges))

    persistence = persistent / max(1.0, prev_count)
    birth_rate = births / max(1.0, curr_count)
    death_rate = deaths / max(1.0, prev_count)

    prev_cent = prev_degree_centrality or {}
    curr_cent = current_degree_centrality or {}
    keys = sorted(set(prev_cent) | set(curr_cent))
    if keys:
        shifts = [abs(float(curr_cent.get(k, 0.0)) - float(prev_cent.get(k, 0.0))) for k in keys]
        cent_shift = float(np.mean(shifts))
    else:
        cent_shift = 0.0

    fragility = float(
        max(
            0.0,
            min(
                1.0,
                0.25 * birth_rate + 0.25 * death_rate + 0.20 * (1.0 - persistence) + 0.15 * cent_shift + 0.15 * (0.55 * structural_drift + 0.45 * coupling_score),
            ),
        )
    )

    return DynamicGraphMetrics(
        edge_persistence=round(persistence, 4),
        edge_birth_rate=round(birth_rate, 4),
        edge_death_rate=round(death_rate, 4),
        centrality_shift=round(cent_shift, 4),
        fragility_score=round(fragility, 4),
    )
