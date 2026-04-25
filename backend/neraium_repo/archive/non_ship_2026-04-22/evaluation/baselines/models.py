from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from evaluation.scenarios import INTERVENTIONS, Scenario


@dataclass
class BaselineModelResult:
    model_id: str
    scenario_id: str
    predicted_risk: float
    predicted_unstable: bool
    first_alert_step: int | None
    recommended_intervention: str
    confidence: float
    calibration_probability: float


def _best_intervention_from_risk(risk: float) -> str:
    if risk < 0.55:
        return "none"
    if risk < 0.75:
        return "suppress_subsystem_instability"
    return "remove_top_driver_contribution"


class ThresholdBaseline:
    model_id = "baseline_threshold"

    def predict(self, scenario: Scenario) -> BaselineModelResult:
        series = [float(row["composite_instability"]) for row in scenario.trajectory]
        first_alert = next((i for i, v in enumerate(series) if v >= 0.7), None)
        risk = max(series) if series else 0.0
        return BaselineModelResult(
            model_id=self.model_id,
            scenario_id=scenario.scenario_id,
            predicted_risk=risk,
            predicted_unstable=risk >= 0.65,
            first_alert_step=first_alert,
            recommended_intervention=_best_intervention_from_risk(risk),
            confidence=min(1.0, max(0.0, risk)),
            calibration_probability=min(1.0, max(0.0, risk)),
        )


class RollingZScoreBaseline:
    model_id = "baseline_anomaly_zscore"

    def predict(self, scenario: Scenario) -> BaselineModelResult:
        series = [float(row["composite_instability"]) for row in scenario.trajectory]
        if len(series) < 4:
            risk = series[-1] if series else 0.0
            return BaselineModelResult(self.model_id, scenario.scenario_id, risk, risk >= 0.65, None, _best_intervention_from_risk(risk), risk, risk)

        window = 4
        zscores: list[float] = []
        first_alert: int | None = None
        for i in range(window, len(series)):
            segment = series[i - window : i]
            mu = mean(segment)
            var = sum((x - mu) ** 2 for x in segment) / max(1, len(segment) - 1)
            std = (var ** 0.5) if var > 1e-9 else 1e-6
            z = (series[i] - mu) / std
            zscores.append(z)
            if first_alert is None and z >= 2.0:
                first_alert = i
        peak_z = max(zscores) if zscores else 0.0
        risk = min(1.0, max(0.0, 0.5 + 0.18 * peak_z))
        return BaselineModelResult(
            model_id=self.model_id,
            scenario_id=scenario.scenario_id,
            predicted_risk=risk,
            predicted_unstable=risk >= 0.65,
            first_alert_step=first_alert,
            recommended_intervention=_best_intervention_from_risk(risk),
            confidence=risk,
            calibration_probability=risk,
        )


class TrendExtrapolationBaseline:
    model_id = "baseline_trend_extrapolation"

    def predict(self, scenario: Scenario) -> BaselineModelResult:
        series = [float(row["composite_instability"]) for row in scenario.trajectory]
        n = len(series)
        if n < 3:
            risk = series[-1] if series else 0.0
            return BaselineModelResult(self.model_id, scenario.scenario_id, risk, risk >= 0.65, None, _best_intervention_from_risk(risk), risk, risk)

        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(series) / n
        denom = sum((x - x_mean) ** 2 for x in xs) or 1e-6
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, series)) / denom
        extrapolated = series[-1] + slope * 3
        risk = min(1.0, max(0.0, extrapolated))
        first_alert = next((i for i, v in enumerate(series) if v >= 0.68), None)
        intervention = "restore_relationship_cluster_to_baseline" if slope < -0.02 else _best_intervention_from_risk(risk)
        if intervention not in INTERVENTIONS:
            intervention = "none"
        return BaselineModelResult(
            model_id=self.model_id,
            scenario_id=scenario.scenario_id,
            predicted_risk=risk,
            predicted_unstable=risk >= 0.65,
            first_alert_step=first_alert,
            recommended_intervention=intervention,
            confidence=min(1.0, 0.4 + abs(slope) * 3.0),
            calibration_probability=risk,
        )


__all__ = [
    "BaselineModelResult",
    "ThresholdBaseline",
    "RollingZScoreBaseline",
    "TrendExtrapolationBaseline",
]
