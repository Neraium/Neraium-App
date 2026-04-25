from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any


INTERVENTIONS = [
    "none",
    "remove_top_driver_contribution",
    "suppress_subsystem_instability",
    "restore_relationship_cluster_to_baseline",
]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    scenario_type: str
    domain: str
    trajectory: list[dict[str, Any]]
    ground_truth: dict[str, Any]
    expected_behaviors: dict[str, Any]
    variant: str = "base"


def _clamp(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _obs(step: int, base: float, *, domain: str, system_type: str, wave: float = 0.0) -> dict[str, Any]:
    instability = _clamp(base + wave)
    coherence = _clamp(1.0 - (0.6 * instability + 0.15))
    return {
        "asset_id": f"{domain}-{system_type}-asset",
        "domain": domain,
        "system_type": system_type,
        "structural_drift_score": _clamp(instability * 0.92),
        "relational_instability_score": _clamp(instability * 0.95),
        "regime_distance": _clamp(instability * 0.9),
        "graph_deformation_score": _clamp(instability * 0.88),
        "coherence_score": coherence,
        "coupling_instability_score": _clamp(instability * 0.9),
        "risk_pressure": _clamp(instability),
        "path_length_shift": _clamp(instability * 0.7),
        "subspace_rotation": _clamp(instability * 0.65),
        "mean_shift": _clamp(instability * 0.6),
        "covariance_shift": _clamp(instability * 0.58),
        "composite_instability": instability,
        "contribution_scores": {"coupling": round(instability, 4), "entropy": round(1.0 - coherence, 4)},
        "top_relationships": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "subsystem_impact": {"sub1": round(_clamp(instability + 0.05), 4), "sub2": round(_clamp(0.5 * instability), 4)},
        "step": step,
    }


def _series(length: int, profile: list[float], *, domain: str, system_type: str, oscillation: float = 0.0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(length):
        phase = profile[min(i, len(profile) - 1)]
        wave = oscillation * math.sin(i * 0.8)
        out.append(_obs(i, phase, domain=domain, system_type=system_type, wave=wave))
    return out


def build_benchmark_scenarios(seed: int = 13, include_noise_variants: bool = True) -> list[Scenario]:
    random.seed(seed)
    base: list[Scenario] = [
        Scenario(
            scenario_id="stable_system",
            scenario_type="stable system",
            domain="manufacturing",
            trajectory=_series(16, [0.18] * 16, domain="manufacturing", system_type="pump"),
            ground_truth={"phase": "stable", "outcome": "stable", "critical_step": None, "intervention_effect": {k: "neutral" for k in INTERVENTIONS}},
            expected_behaviors={"should_alert": False, "should_recommend_intervention": False},
        ),
        Scenario(
            scenario_id="slow_drift",
            scenario_type="slow drift",
            domain="manufacturing",
            trajectory=_series(18, [0.2 + 0.03 * i for i in range(18)], domain="manufacturing", system_type="pump"),
            ground_truth={"phase": "drift", "outcome": "degraded", "critical_step": 14, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "helpful", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_alert": True, "min_lead_time": 2},
        ),
        Scenario(
            scenario_id="oscillatory_instability",
            scenario_type="oscillatory instability",
            domain="energy",
            trajectory=_series(20, [0.45] * 20, domain="energy", system_type="grid", oscillation=0.24),
            ground_truth={"phase": "oscillatory", "outcome": "degraded", "critical_step": 12, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "neutral", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "helpful"}},
            expected_behaviors={"should_alert": True, "should_detect_instability_pattern": True},
        ),
        Scenario(
            scenario_id="sudden_collapse",
            scenario_type="sudden collapse",
            domain="water",
            trajectory=_series(14, [0.2] * 8 + [0.95] * 6, domain="water", system_type="treatment"),
            ground_truth={"phase": "collapse", "outcome": "collapse", "critical_step": 8, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "helpful", "suppress_subsystem_instability": "neutral", "restore_relationship_cluster_to_baseline": "harmful"}},
            expected_behaviors={"should_alert": True, "min_lead_time": 0},
        ),
        Scenario(
            scenario_id="reversible_recovery",
            scenario_type="reversible recovery after intervention",
            domain="manufacturing",
            trajectory=_series(18, [0.3, 0.35, 0.4, 0.5, 0.62, 0.74, 0.78, 0.72, 0.6, 0.48, 0.4, 0.34, 0.28, 0.24, 0.2, 0.18, 0.17, 0.16], domain="manufacturing", system_type="compressor"),
            ground_truth={"phase": "recovery", "outcome": "recovered", "critical_step": 6, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "helpful", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_alert": True, "should_identify_reversibility": True},
        ),
        Scenario(
            scenario_id="misleading_lookalike_harmful",
            scenario_type="misleading lookalike",
            domain="finance",
            trajectory=_series(16, [0.28, 0.33, 0.4, 0.48, 0.57, 0.65, 0.72, 0.79, 0.83, 0.86, 0.88, 0.9, 0.91, 0.92, 0.93, 0.94], domain="finance", system_type="portfolio"),
            ground_truth={"phase": "lookalike", "outcome": "collapse", "critical_step": 8, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "harmful", "suppress_subsystem_instability": "neutral", "restore_relationship_cluster_to_baseline": "helpful"}},
            expected_behaviors={"should_alert": True, "should_avoid_default_intervention": True},
        ),
        Scenario(
            scenario_id="misleading_lookalike_helpful",
            scenario_type="misleading lookalike",
            domain="finance",
            trajectory=_series(16, [0.28, 0.33, 0.4, 0.48, 0.57, 0.65, 0.72, 0.79, 0.76, 0.7, 0.64, 0.58, 0.51, 0.44, 0.37, 0.32], domain="finance", system_type="portfolio"),
            ground_truth={"phase": "lookalike", "outcome": "degraded", "critical_step": 7, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "helpful", "suppress_subsystem_instability": "neutral", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_alert": True, "should_disambiguate_lookalikes": True},
        ),
        Scenario(
            scenario_id="helpful_intervention_case",
            scenario_type="helpful intervention",
            domain="healthcare",
            trajectory=_series(15, [0.32, 0.38, 0.45, 0.52, 0.58, 0.64, 0.7, 0.73, 0.68, 0.6, 0.5, 0.42, 0.35, 0.3, 0.26], domain="healthcare", system_type="triage"),
            ground_truth={"phase": "intervention", "outcome": "recovered", "critical_step": 7, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "helpful", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_recommend_intervention": True},
        ),
        Scenario(
            scenario_id="neutral_intervention_case",
            scenario_type="neutral intervention",
            domain="logistics",
            trajectory=_series(14, [0.34, 0.4, 0.46, 0.53, 0.57, 0.61, 0.63, 0.64, 0.65, 0.66, 0.66, 0.66, 0.66, 0.66], domain="logistics", system_type="fleet"),
            ground_truth={"phase": "plateau", "outcome": "degraded", "critical_step": 9, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "neutral", "suppress_subsystem_instability": "neutral", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_recommend_intervention": False},
        ),
        Scenario(
            scenario_id="harmful_intervention_case",
            scenario_type="harmful intervention",
            domain="chemicals",
            trajectory=_series(14, [0.35, 0.41, 0.47, 0.54, 0.62, 0.7, 0.77, 0.84, 0.88, 0.9, 0.92, 0.93, 0.94, 0.95], domain="chemicals", system_type="reactor"),
            ground_truth={"phase": "escalating", "outcome": "collapse", "critical_step": 7, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "harmful", "suppress_subsystem_instability": "neutral", "restore_relationship_cluster_to_baseline": "helpful"}},
            expected_behaviors={"should_recommend_intervention": True, "avoid_harmful": "remove_top_driver_contribution"},
        ),
        Scenario(
            scenario_id="sparse_data_cold_start",
            scenario_type="sparse-data / cold-start",
            domain="satellite",
            trajectory=_series(6, [0.42, 0.45, 0.52, 0.6, 0.68, 0.73], domain="satellite", system_type="thermal"),
            ground_truth={"phase": "cold_start", "outcome": "degraded", "critical_step": 5, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "neutral", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "neutral"}},
            expected_behaviors={"should_express_low_confidence": True},
        ),
        Scenario(
            scenario_id="cross_domain_transfer_case",
            scenario_type="cross-domain transfer case",
            domain="aerospace",
            trajectory=_series(17, [0.24, 0.29, 0.36, 0.44, 0.53, 0.61, 0.68, 0.75, 0.8, 0.85, 0.83, 0.79, 0.72, 0.64, 0.55, 0.47, 0.4], domain="aerospace", system_type="actuator"),
            ground_truth={"phase": "transfer", "outcome": "degraded", "critical_step": 8, "intervention_effect": {"none": "harmful", "remove_top_driver_contribution": "neutral", "suppress_subsystem_instability": "helpful", "restore_relationship_cluster_to_baseline": "helpful"}},
            expected_behaviors={"requires_transfer_reasoning": True},
        ),
    ]

    if not include_noise_variants:
        return base

    noisy: list[Scenario] = []
    for scenario in base:
        if scenario.scenario_id in {"stable_system", "cross_domain_transfer_case", "slow_drift"}:
            noisy_traj = []
            missing_traj = []
            for row in scenario.trajectory:
                jitter = random.uniform(-0.06, 0.06)
                noisy_row = dict(row)
                noisy_row["composite_instability"] = _clamp(float(row["composite_instability"]) + jitter)
                noisy_row["risk_pressure"] = _clamp(float(row["risk_pressure"]) + jitter)
                noisy_traj.append(noisy_row)

                missing_row = dict(noisy_row)
                if int(row["step"]) % 4 == 0:
                    missing_row["subsystem_impact"] = {}
                    missing_row["top_relationships"] = []
                missing_traj.append(missing_row)

            noisy.append(
                Scenario(
                    scenario_id=f"{scenario.scenario_id}_noise",
                    scenario_type=scenario.scenario_type,
                    domain=scenario.domain,
                    trajectory=noisy_traj,
                    ground_truth=scenario.ground_truth,
                    expected_behaviors=scenario.expected_behaviors,
                    variant="noise",
                )
            )
            noisy.append(
                Scenario(
                    scenario_id=f"{scenario.scenario_id}_missing",
                    scenario_type=scenario.scenario_type,
                    domain=scenario.domain,
                    trajectory=missing_traj,
                    ground_truth=scenario.ground_truth,
                    expected_behaviors=scenario.expected_behaviors,
                    variant="missing",
                )
            )

    return base + noisy


__all__ = ["Scenario", "INTERVENTIONS", "build_benchmark_scenarios"]
