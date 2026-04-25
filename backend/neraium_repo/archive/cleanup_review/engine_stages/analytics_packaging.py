from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalyticsPackagingInput:
    analytics: dict[str, Any]
    unavailable_payload: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class AnalyticsPackagingResult:
    analytics: dict[str, Any]
    experimental_analytics: dict[str, Any]


def package_analytics_output(stage_input: AnalyticsPackagingInput) -> AnalyticsPackagingResult:
    analytics = dict(stage_input.analytics)

    for key, payload in stage_input.unavailable_payload.items():
        existing = analytics.get(key)
        analytics[key] = existing if isinstance(existing, dict) and existing else payload

    trajectory_analysis = analytics["trajectory_analysis"]
    branching_analysis = analytics["branching_analysis"]
    constraint_analysis = analytics["constraint_analysis"]
    hierarchy_analysis = analytics["hierarchy_analysis"]
    horizon_analysis = analytics["horizon_analysis"]
    counterfactual_simulation = analytics["counterfactual_simulation"]

    experimental_analytics = {
        "trajectory_analysis": trajectory_analysis,
        "branching_analysis": branching_analysis,
        "constraint_analysis": constraint_analysis,
        "hierarchy_analysis": hierarchy_analysis,
        "horizon_analysis": horizon_analysis,
        "counterfactual_simulation": counterfactual_simulation,
        **analytics,
    }
    return AnalyticsPackagingResult(analytics=analytics, experimental_analytics=experimental_analytics)
