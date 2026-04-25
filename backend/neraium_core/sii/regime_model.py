from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from neraium_core.sii.config import SIIConfig
from neraium_core.sii.errors import SIIIOError


@dataclass(frozen=True)
class RegimeObservation:
    geometry_signature: np.ndarray
    graph_signature: np.ndarray
    feature_names: list[str]


@dataclass(frozen=True)
class RegimeResult:
    regime_name: str
    regime_distance: float
    regime_support: float
    regime_activated: bool
    geometry_distance: float = 0.0
    graph_distance: float = 0.0
    regime_confidence: float = 0.0
    regime_uncertainty: float = 1.0


class RegimeModel:
    """
    Regime modeling for stable operating structure.
    """

    def __init__(self, *, config: SIIConfig) -> None:
        self.config = config
        self._regimes: list[dict[str, Any]] = []
        self._pending: dict[str, Any] | None = None
        self._store_path = Path(self.config.regime_store_path)
        self._posterior: dict[str, float] = {}
        self.load()

    @staticmethod
    def _distance(a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return float("inf")
        return float(np.linalg.norm(a - b))

    def _compose(self, geometry_signature: np.ndarray, graph_signature: np.ndarray) -> np.ndarray:
        return np.concatenate([geometry_signature, graph_signature])

    def _weighted_distance(
        self,
        *,
        geom_a: np.ndarray,
        geom_b: np.ndarray,
        graph_a: np.ndarray,
        graph_b: np.ndarray,
    ) -> tuple[float, float, float]:
        gdist = self._distance(geom_a, geom_b)
        grdist = self._distance(graph_a, graph_b)
        if not np.isfinite(gdist) or not np.isfinite(grdist):
            return float("inf"), float("inf"), float("inf")
        # Geometry dominates regime identity; graph gives structural topology support.
        total = float(0.72 * gdist + 0.28 * grdist)
        return total, float(gdist), float(grdist)

    def _nearest(
        self,
        geometry_signature: np.ndarray,
        graph_signature: np.ndarray,
    ) -> tuple[dict[str, Any] | None, float, float, float]:
        best_reg: dict[str, Any] | None = None
        best_dist = float("inf")
        best_geom = 0.0
        best_graph = 0.0
        for reg in self._regimes:
            prototypes = reg.get("prototypes", [])
            for p in prototypes:
                if not isinstance(p, dict):
                    continue
                geom_proto = np.asarray(p.get("geometry_signature", []), dtype=float)
                graph_proto = np.asarray(p.get("graph_signature", []), dtype=float)
                dist, gdist, grdist = self._weighted_distance(
                    geom_a=geometry_signature,
                    geom_b=geom_proto,
                    graph_a=graph_signature,
                    graph_b=graph_proto,
                )
                if dist < best_dist:
                    best_dist = dist
                    best_geom = gdist
                    best_graph = grdist
                    best_reg = reg
        if best_reg is None:
            return None, 0.0, 0.0, 0.0
        return best_reg, float(best_dist), float(best_geom), float(best_graph)

    def nearest_matches(
        self,
        *,
        geometry_signature: np.ndarray,
        graph_signature: np.ndarray,
        top_k: int = 3,
    ) -> list[dict[str, float | str]]:
        matches: list[dict[str, float | str]] = []
        geom = np.asarray(geometry_signature, dtype=float)
        graph = np.asarray(graph_signature, dtype=float)
        for reg in self._regimes:
            prototypes = reg.get("prototypes", [])
            best_dist = float("inf")
            best_geom = float("inf")
            best_graph = float("inf")
            for p in prototypes:
                if not isinstance(p, dict):
                    continue
                geom_proto = np.asarray(p.get("geometry_signature", []), dtype=float)
                graph_proto = np.asarray(p.get("graph_signature", []), dtype=float)
                dist, gdist, grdist = self._weighted_distance(
                    geom_a=geom,
                    geom_b=geom_proto,
                    graph_a=graph,
                    graph_b=graph_proto,
                )
                if dist < best_dist:
                    best_dist = float(dist)
                    best_geom = float(gdist)
                    best_graph = float(grdist)
            if np.isfinite(best_dist):
                similarity = float(np.exp(-best_dist))
                matches.append(
                    {
                        "regime_name": str(reg.get("name", "unknown")),
                        "distance": round(best_dist, 6),
                        "similarity": round(similarity, 6),
                        "geometry_distance": round(best_geom, 6),
                        "graph_distance": round(best_graph, 6),
                        "hits": float(reg.get("hits", 0.0)),
                    }
                )
        matches.sort(key=lambda x: float(x.get("distance", float("inf"))))
        return matches[: max(1, int(top_k))]


    def _update_posterior(self, distances: dict[str, float], focus_name: str) -> tuple[float, float]:
        if not distances:
            self._posterior = {focus_name: 1.0}
            return 1.0, 0.0
        likelihoods = {k: float(np.exp(-max(0.0, v))) for k, v in distances.items()}
        total = float(sum(likelihoods.values())) + 1e-12
        likelihoods = {k: v / total for k, v in likelihoods.items()}
        if not self._posterior:
            self._posterior = dict(likelihoods)
        else:
            blended: dict[str, float] = {}
            all_keys = set(self._posterior) | set(likelihoods)
            for key in all_keys:
                prior = float(self._posterior.get(key, 1e-6))
                like = float(likelihoods.get(key, 1e-6))
                blended[key] = 0.82 * prior + 0.18 * like
            norm = float(sum(blended.values())) + 1e-12
            self._posterior = {k: v / norm for k, v in blended.items()}
        focus_prob = float(self._posterior.get(focus_name, 0.0))
        probs = np.asarray(list(self._posterior.values()), dtype=float)
        ent = float(-np.sum(probs * np.log(probs + 1e-12)))
        denom = float(np.log(max(2, probs.size)))
        uncertainty = float(max(0.0, min(1.0, ent / max(1e-9, denom))))
        return focus_prob, uncertainty

    def _append_prototype(
        self,
        reg: dict[str, Any],
        *,
        geometry_signature: np.ndarray,
        graph_signature: np.ndarray,
    ) -> None:
        protos = reg.setdefault("prototypes", [])
        protos.append(
            {
                "geometry_signature": np.asarray(geometry_signature, dtype=float).tolist(),
                "graph_signature": np.asarray(graph_signature, dtype=float).tolist(),
            }
        )
        max_p = int(self.config.regime_max_prototypes)
        if len(protos) > max_p:
            del protos[0 : len(protos) - max_p]
        geom_arr = np.asarray([p["geometry_signature"] for p in protos], dtype=float)
        graph_arr = np.asarray([p["graph_signature"] for p in protos], dtype=float)
        reg["geometry_signature"] = np.mean(geom_arr, axis=0).tolist()
        reg["graph_signature"] = np.mean(graph_arr, axis=0).tolist()
        reg["signature"] = self._compose(
            np.asarray(reg["geometry_signature"], dtype=float),
            np.asarray(reg["graph_signature"], dtype=float),
        ).tolist()

    def observe(self, obs: RegimeObservation) -> RegimeResult:
        geometry_signature = np.asarray(obs.geometry_signature, dtype=float)
        graph_signature = np.asarray(obs.graph_signature, dtype=float)
        signature = self._compose(geometry_signature, graph_signature)
        if not self._regimes:
            reg = {
                "name": "regime_0",
                "feature_names": list(obs.feature_names),
                "prototypes": [
                    {
                        "geometry_signature": geometry_signature.tolist(),
                        "graph_signature": graph_signature.tolist(),
                    }
                ],
                "geometry_signature": geometry_signature.tolist(),
                "graph_signature": graph_signature.tolist(),
                "signature": signature.tolist(),
                "hits": 1,
            }
            self._regimes.append(reg)
            return RegimeResult(
                regime_name="regime_0",
                regime_distance=0.0,
                regime_support=1.0,
                regime_activated=True,
                geometry_distance=0.0,
                graph_distance=0.0,
                regime_confidence=1.0,
                regime_uncertainty=0.0,
            )

        nearest, dist, geom_dist, graph_dist = self._nearest(geometry_signature, graph_signature)
        threshold = float(self.config.regime_distance_threshold)
        dist_map: dict[str, float] = {}
        for reg in self._regimes:
            name = str(reg.get("name", "unknown"))
            protos = reg.get("prototypes", [])
            best = float("inf")
            for p in protos:
                if not isinstance(p, dict):
                    continue
                geom_proto = np.asarray(p.get("geometry_signature", []), dtype=float)
                graph_proto = np.asarray(p.get("graph_signature", []), dtype=float)
                cand, _, _ = self._weighted_distance(geom_a=geometry_signature, geom_b=geom_proto, graph_a=graph_signature, graph_b=graph_proto)
                if cand < best:
                    best = cand
            if np.isfinite(best):
                dist_map[name] = float(best)
        if nearest is not None and dist <= threshold:
            self._append_prototype(
                nearest,
                geometry_signature=geometry_signature,
                graph_signature=graph_signature,
            )
            nearest["hits"] = int(nearest.get("hits", 0)) + 1
            conf, unc = self._update_posterior(dist_map, str(nearest["name"]))
            return RegimeResult(
                regime_name=str(nearest["name"]),
                regime_distance=float(dist),
                regime_support=max(0.0, min(1.0, float(nearest["hits"]) / 12.0)),
                regime_activated=False,
                geometry_distance=float(geom_dist),
                graph_distance=float(graph_dist),
                regime_confidence=float(conf),
                regime_uncertainty=float(unc),
            )

        # Pending regime candidate requires repeated observations.
        if self._pending is None:
            self._pending = {
                "name": f"regime_{len(self._regimes)}",
                "feature_names": list(obs.feature_names),
                "geometry_signature": geometry_signature.tolist(),
                "graph_signature": graph_signature.tolist(),
                "signature": signature.tolist(),
                "prototypes": [
                    {
                        "geometry_signature": geometry_signature.tolist(),
                        "graph_signature": graph_signature.tolist(),
                    }
                ],
                "hits": 1,
            }
            return RegimeResult(
                regime_name=str(self._pending["name"]),
                regime_distance=float(dist),
                regime_support=0.1,
                regime_activated=False,
                geometry_distance=float(geom_dist),
                graph_distance=float(graph_dist),
            )

        pending_geom = np.asarray(self._pending["geometry_signature"], dtype=float)
        pending_graph = np.asarray(self._pending["graph_signature"], dtype=float)
        pending_dist, pending_geom_dist, pending_graph_dist = self._weighted_distance(
            geom_a=geometry_signature,
            geom_b=pending_geom,
            graph_a=graph_signature,
            graph_b=pending_graph,
        )
        if pending_dist <= threshold:
            self._pending["hits"] = int(self._pending.get("hits", 1)) + 1
            self._pending["prototypes"].append(
                {
                    "geometry_signature": geometry_signature.tolist(),
                    "graph_signature": graph_signature.tolist(),
                }
            )
            p_geom = np.asarray([p["geometry_signature"] for p in self._pending["prototypes"]], dtype=float)
            p_graph = np.asarray([p["graph_signature"] for p in self._pending["prototypes"]], dtype=float)
            self._pending["geometry_signature"] = np.mean(p_geom, axis=0).tolist()
            self._pending["graph_signature"] = np.mean(p_graph, axis=0).tolist()
            self._pending["signature"] = self._compose(
                np.asarray(self._pending["geometry_signature"], dtype=float),
                np.asarray(self._pending["graph_signature"], dtype=float),
            ).tolist()
            if int(self._pending["hits"]) >= int(self.config.regime_min_persistence):
                activated = dict(self._pending)
                activated["hits"] = int(activated.get("hits", 1))
                self._regimes.append(activated)
                self._pending = None
                return RegimeResult(
                    regime_name=str(activated["name"]),
                    regime_distance=float(pending_dist),
                    regime_support=max(0.0, min(1.0, float(activated["hits"]) / 12.0)),
                    regime_activated=True,
                    geometry_distance=float(pending_geom_dist),
                    graph_distance=float(pending_graph_dist),
                    regime_confidence=0.55,
                    regime_uncertainty=0.45,
                )
            return RegimeResult(
                regime_name=str(self._pending["name"]),
                regime_distance=float(pending_dist),
                regime_support=max(0.0, min(1.0, float(self._pending["hits"]) / 12.0)),
                regime_activated=False,
                geometry_distance=float(pending_geom_dist),
                graph_distance=float(pending_graph_dist),
                regime_confidence=0.35,
                regime_uncertainty=0.65,
            )

        # Replace pending if it diverges too far from repeated evidence.
        self._pending = {
            "name": f"regime_{len(self._regimes)}",
            "feature_names": list(obs.feature_names),
            "geometry_signature": geometry_signature.tolist(),
            "graph_signature": graph_signature.tolist(),
            "signature": signature.tolist(),
            "prototypes": [
                {
                    "geometry_signature": geometry_signature.tolist(),
                    "graph_signature": graph_signature.tolist(),
                }
            ],
            "hits": 1,
        }
        return RegimeResult(
            regime_name=str(self._pending["name"]),
            regime_distance=float(dist),
            regime_support=0.1,
            regime_activated=False,
            geometry_distance=float(geom_dist),
            graph_distance=float(graph_dist),
            regime_confidence=0.2,
            regime_uncertainty=0.9,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "regimes": list(self._regimes),
            "pending": None if self._pending is None else dict(self._pending),
            "posterior": dict(self._posterior),
        }

    def _sanitize_loaded(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        regimes = raw.get("regimes")
        pending = raw.get("pending")
        posterior = raw.get("posterior")
        if isinstance(regimes, list):
            safe_regimes: list[dict[str, Any]] = []
            for item in regimes:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", f"regime_{len(safe_regimes)}"))
                feature_names = item.get("feature_names")
                signature = item.get("signature")
                geometry_signature = item.get("geometry_signature")
                graph_signature = item.get("graph_signature")
                prototypes = item.get("prototypes")
                hits = int(item.get("hits", 0))
                if not isinstance(prototypes, list):
                    continue
                safe_prototypes: list[dict[str, Any]] = []
                for proto in prototypes:
                    if not isinstance(proto, dict):
                        continue
                    p_geom = proto.get("geometry_signature")
                    p_graph = proto.get("graph_signature")
                    if isinstance(p_geom, list) and isinstance(p_graph, list):
                        safe_prototypes.append(
                            {"geometry_signature": p_geom, "graph_signature": p_graph}
                        )
                if not safe_prototypes:
                    continue
                if not isinstance(geometry_signature, list):
                    geometry_signature = list(safe_prototypes[-1]["geometry_signature"])
                if not isinstance(graph_signature, list):
                    graph_signature = list(safe_prototypes[-1]["graph_signature"])
                if not isinstance(signature, list):
                    signature = self._compose(
                        np.asarray(geometry_signature, dtype=float),
                        np.asarray(graph_signature, dtype=float),
                    ).tolist()
                safe_regimes.append(
                    {
                        "name": name,
                        "feature_names": list(feature_names) if isinstance(feature_names, list) else [],
                        "geometry_signature": geometry_signature,
                        "graph_signature": graph_signature,
                        "signature": signature,
                        "prototypes": safe_prototypes,
                        "hits": hits,
                    }
                )
            self._regimes = safe_regimes
        if isinstance(pending, dict):
            name = str(pending.get("name", f"regime_{len(self._regimes)}"))
            feature_names = pending.get("feature_names")
            geometry_signature = pending.get("geometry_signature")
            graph_signature = pending.get("graph_signature")
            signature = pending.get("signature")
            prototypes = pending.get("prototypes")
            hits = int(pending.get("hits", 1))
            if isinstance(prototypes, list):
                safe_prototypes: list[dict[str, Any]] = []
                for proto in prototypes:
                    if not isinstance(proto, dict):
                        continue
                    p_geom = proto.get("geometry_signature")
                    p_graph = proto.get("graph_signature")
                    if isinstance(p_geom, list) and isinstance(p_graph, list):
                        safe_prototypes.append(
                            {"geometry_signature": p_geom, "graph_signature": p_graph}
                        )
                if not safe_prototypes:
                    return
                if not isinstance(geometry_signature, list):
                    geometry_signature = list(safe_prototypes[-1]["geometry_signature"])
                if not isinstance(graph_signature, list):
                    graph_signature = list(safe_prototypes[-1]["graph_signature"])
                if not isinstance(signature, list):
                    signature = self._compose(
                        np.asarray(geometry_signature, dtype=float),
                        np.asarray(graph_signature, dtype=float),
                    ).tolist()
                self._pending = {
                    "name": name,
                    "feature_names": list(feature_names) if isinstance(feature_names, list) else [],
                    "geometry_signature": geometry_signature,
                    "graph_signature": graph_signature,
                    "signature": signature,
                    "prototypes": safe_prototypes,
                    "hits": hits,
                }


        if isinstance(posterior, dict):
            cleaned: dict[str, float] = {}
            for k, v in posterior.items():
                try:
                    cleaned[str(k)] = float(v)
                except Exception:
                    continue
            if cleaned:
                norm = float(sum(cleaned.values()))
                if norm > 0.0:
                    self._posterior = {k: v / norm for k, v in cleaned.items()}
    def save(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_text(
                json.dumps(self.to_dict(), indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            raise SIIIOError(f"Failed to write regime store: {self._store_path}") from exc

    def load(self) -> None:
        if not self._store_path.exists():
            return
        if not self._store_path.is_file():
            raise SIIIOError(f"Regime store path is not a file: {self._store_path}")
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SIIIOError(f"Failed to parse regime store: {self._store_path}") from exc
        self._sanitize_loaded(raw)
