from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class StructuralAttribution:
    top_sensors: list[dict[str, Any]]
    top_relationships: list[dict[str, Any]]
    subsystem_impact: dict[str, Any]
    change_character: dict[str, str]
    contribution_scores: dict[str, float]
    explanation: str


def _clamp01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _connected_components(adj: np.ndarray, names: list[str]) -> list[list[str]]:
    n = int(adj.shape[0])
    seen = [False] * n
    comps: list[list[str]] = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp_idx: list[int] = []
        while stack:
            i = stack.pop()
            comp_idx.append(i)
            neighbors = np.where(adj[i] > 0.0)[0]
            for j in neighbors.tolist():
                if not seen[j]:
                    seen[j] = True
                    stack.append(j)
        comps.append([names[i] for i in comp_idx if i < len(names)])
    return comps


def build_structural_attribution(
    *,
    sensor_names: list[str],
    baseline_corr: np.ndarray,
    recent_corr: np.ndarray,
    baseline_adj: np.ndarray,
    recent_adj: np.ndarray,
    baseline_mean: np.ndarray,
    recent_mean: np.ndarray,
    structural_score: float,
    relational_score: float,
    graph_score: float,
    coupling_score: float,
    recent_composite: list[float],
) -> StructuralAttribution:
    names = list(sensor_names)
    n = min(len(names), int(recent_corr.shape[0]))
    if n <= 0:
        return StructuralAttribution([], [], {"primary_cluster": "none", "clusters": []}, {"scope": "local", "tempo": "gradual"}, {}, "No sensor attribution available.")

    corr_delta = np.asarray(recent_corr[:n, :n] - baseline_corr[:n, :n], dtype=float)
    abs_delta = np.abs(corr_delta)
    np.fill_diagonal(abs_delta, 0.0)

    mean_shift = np.abs(np.asarray(recent_mean[:n], dtype=float) - np.asarray(baseline_mean[:n], dtype=float))
    mean_norm = mean_shift / (np.max(mean_shift) + 1e-6)
    rel_node = np.mean(abs_delta, axis=1)
    rel_norm = rel_node / (np.max(rel_node) + 1e-6)

    node_scores = 0.65 * rel_norm + 0.35 * mean_norm
    sensor_rank = np.argsort(node_scores)[::-1]
    top_sensors = [
        {
            "sensor": names[i],
            "score": round(float(node_scores[i]), 4),
            "relational_shift": round(float(rel_norm[i]), 4),
            "mean_shift": round(float(mean_norm[i]), 4),
        }
        for i in sensor_rank[: min(5, n)]
    ]

    rel_entries: list[tuple[float, dict[str, Any]]] = []
    for i in range(n):
        for j in range(i + 1, n):
            d = float(corr_delta[i, j])
            ad = abs(d)
            if ad < 1e-6:
                continue
            b = abs(float(baseline_corr[i, j]))
            r = abs(float(recent_corr[i, j]))
            if b >= 0.4 and r <= 0.15:
                mode = "break"
            elif b <= 0.15 and r >= 0.4:
                mode = "new"
            elif d > 0.0:
                mode = "strengthened"
            else:
                mode = "weakened"
            rel_entries.append(
                (
                    ad,
                    {
                        "pair": f"{names[i]}↔{names[j]}",
                        "delta": round(d, 4),
                        "magnitude": round(ad, 4),
                        "change": mode,
                    },
                )
            )
    rel_entries.sort(key=lambda x: x[0], reverse=True)
    top_relationships = [e[1] for e in rel_entries[: min(6, len(rel_entries))]]

    adj = np.asarray(recent_adj[:n, :n], dtype=float)
    clusters = _connected_components(adj, names[:n])
    cluster_scores: list[dict[str, Any]] = []
    for c in clusters:
        idx = [names.index(s) for s in c if s in names]
        if not idx:
            continue
        score = float(np.mean(node_scores[idx]))
        cluster_scores.append({"cluster": c, "impact": round(score, 4), "size": len(c)})
    cluster_scores.sort(key=lambda x: float(x.get("impact", 0.0)), reverse=True)
    primary_cluster = ", ".join(cluster_scores[0]["cluster"]) if cluster_scores else "none"

    coverage = float(np.mean(node_scores > 0.35))
    scope = "distributed" if coverage >= 0.4 else "local"
    if len(recent_composite) >= 6:
        arr = np.asarray(recent_composite[-8:], dtype=float)
        x = np.arange(arr.size, dtype=float)
        slope, _ = np.polyfit(x, arr, 1)
        tempo = "abrupt" if abs(float(slope)) >= 0.03 else "gradual"
    else:
        tempo = "gradual"

    explanation = (
        f"Primary drivers are {', '.join(s['sensor'] for s in top_sensors[:3]) or 'none'}, "
        f"with strongest relationship shifts in {', '.join(r['pair'] for r in top_relationships[:2]) or 'none'}. "
        f"Impact appears {scope} and {tempo}; most affected cluster: {primary_cluster}."
    )

    contribution_scores = {
        "structural": round(_clamp01(structural_score), 4),
        "relational": round(_clamp01(relational_score), 4),
        "graph": round(_clamp01(graph_score), 4),
        "coupling": round(_clamp01(coupling_score), 4),
    }
    return StructuralAttribution(
        top_sensors=top_sensors,
        top_relationships=top_relationships,
        subsystem_impact={"primary_cluster": primary_cluster, "clusters": cluster_scores[:4]},
        change_character={"scope": scope, "tempo": tempo},
        contribution_scores=contribution_scores,
        explanation=explanation,
    )
