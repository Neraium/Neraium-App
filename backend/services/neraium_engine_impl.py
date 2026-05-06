"""Minimal NeraiumEngine implementation adapter.

This wraps the existing SII state and decision synthesizer services behind the
simple packet interface expected by the IMS runner. It intentionally keeps the
logic small and deterministic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.services import decision_synth
from backend.services import sii_state


class NeraiumEngine:
    _printed_init = False

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self.config = {
            "watch_threshold": 0.50,
            "watch_commitment_threshold": 0.50,
            "watch_recovery_resistance_max": 0.60,
            "actionable_hazard_threshold": 0.65,
            "recovery_resistance_threshold": 0.25,
            "instability_density_threshold": 0.70,
            "accumulation_slope_threshold": 0.65,
            "recurrence_count_threshold": 3,
            "min_actionable_cycle_bearing3": 2000,
            "min_actionable_cycle_bearing4": 1400,
        }
        if config:
            self.config.update(config)
        self.cycle = 0
        self._hazard_history: list[float] = []
        self._hazard_rate_history: list[float] = []
        self._hazard_acceleration_history: list[float] = []
        self._cumulative_instability = 0.0
        self._cumulative_instability_history: list[float] = []
        self._failure_estimate_history: list[float] = []
        self._state = "STABLE"
        self._watch_seen = False
        self._watch_event_cycles: list[int] = []
        self._watch_candidate_cycles: list[int] = []
        self._watch_reversion_cycles: list[int] = []
        self._actionable_lock = False
        self._actionable_entry_cycle: int | None = None
        self._first_change_cycle: int | None = None
        self._signal_history: list[Dict[str, float]] = []
        self._last_frames: Dict[str, Dict[str, Any]] = {}
        self._plateau_duration = 0
        self._registered_assets: set[str] = set()
        if not NeraiumEngine._printed_init:
            print("[ENGINE] NeraiumEngine initialized")
            NeraiumEngine._printed_init = True

    def update(self, packet: dict) -> dict:
        self.cycle += 1
        asset_id = str(packet.get("asset_id") or packet.get("bearing_id") or "ims_bearing")
        bearing_id = str(packet.get("bearing_id") or asset_id)
        cycle = int(packet.get("cycle") or self.cycle)
        timestamp = float(cycle)
        signals = self._signals(packet)
        self._signal_history.append(dict(signals))
        if len(self._signal_history) > 600:
            self._signal_history = self._signal_history[-600:]

        if asset_id not in self._registered_assets and not sii_state.has_system(asset_id):
            sii_state.register_system(
                system_id=asset_id,
                template="industrial",
                label=asset_id,
                variables=list(signals.keys()),
                units={key: "" for key in signals},
            )
            self._registered_assets.add(asset_id)

        try:
            state_frame = sii_state.ingest_frame(asset_id, signals, timestamp)
            decision = decision_synth.build_decision(asset_id)
            drift = float(
                state_frame.get("structural_drift")
                or state_frame.get("instability_score")
                or self._simple_drift(signals)
            )
            stability = max(0.0, min(1.0, 1.0 - drift))
            state = self._state_from_existing(
                str(decision.get("state") or state_frame.get("display_regime") or state_frame.get("regime") or ""),
                drift,
            )
            confidence = self._confidence_label(float(state_frame.get("confidence") or 0.0), state)
        except Exception:
            drift = self._simple_drift(signals)
            stability = max(0.0, min(1.0, 1.0 - drift))
            state = self._state_from_drift(drift)
            confidence = self._confidence_label(drift, state)

        if self.cycle <= 50:
            drift = 0.0
            stability = 1.0
            confidence = "LOW"
        hazard_score = float(drift)
        previous_hazard = self._hazard_history[-1] if self._hazard_history else hazard_score
        hazard_rate = hazard_score - previous_hazard if self._hazard_history else 0.0
        previous_rate = self._hazard_rate_history[-1] if self._hazard_rate_history else hazard_rate
        hazard_acceleration = hazard_rate - previous_rate if self._hazard_rate_history else 0.0
        if self.cycle <= 50:
            hazard_rate = 0.0
            hazard_acceleration = 0.0
        self._cumulative_instability += float(hazard_score)
        self._cumulative_instability_history.append(float(self._cumulative_instability))
        self._hazard_history.append(hazard_score)
        self._hazard_rate_history.append(hazard_rate)
        self._hazard_acceleration_history.append(hazard_acceleration)
        persistence = self._signal_persistence()
        recovery_resistance = self._recovery_resistance()
        positive_slope_fraction = self._positive_slope_fraction()
        instability_intensity = self._instability_intensity()
        instability_progression = self._instability_progression()
        progression_consistency = self._progression_consistency()
        instability_density = self._instability_density()
        accumulation_slope = self._accumulation_slope()
        recurrence_count = self._recurrence_count()
        recurrence_density = self._recurrence_density(recurrence_count)
        plateau_condition = instability_intensity >= 0.90
        self._plateau_duration = self._plateau_duration + 1 if plateau_condition else 0
        phase = self._phase(instability_intensity, instability_progression, progression_consistency)
        trajectory_commitment_score = self._trajectory_commitment_score()
        state = self._persistent_state(
            asset_id,
            hazard_score,
            persistence,
            trajectory_commitment_score,
            recovery_resistance,
            positive_slope_fraction,
            instability_intensity,
            progression_consistency,
            plateau_condition,
            self._plateau_duration,
            instability_density,
            accumulation_slope,
            recurrence_count,
        )
        recurrence_count = self._recurrence_count()
        recurrence_density = self._recurrence_density(recurrence_count)
        if self.cycle <= 50:
            state = "STABLE"
        if state in {"WATCH", "ACTIONABLE", "ALERT"} and self._first_change_cycle is None:
            self._first_change_cycle = self.cycle
        if state == "STABLE" and self.cycle <= 50:
            operator = self._baseline_operator_frame()
        else:
            operator = self._operator_frame(state)
        actionable_duration = self._actionable_duration()
        hazard_state = state
        hazard_confidence = str(confidence).upper()
        if state == "ACTIONABLE" and actionable_duration >= 25:
            hazard_confidence = "HIGH"
            confidence = "high"
        hazard_reason = self._hazard_reason(state)
        trajectory = self._trajectory_frame(state)
        time_to_threshold = 0.0 if state in {"ACTIONABLE", "ALERT"} else None
        time_to_failure_estimate = self._time_to_failure_estimate(state, hazard_score, hazard_rate)
        trajectory_strength = max(
            float(drift),
            float(hazard_score),
            float(trajectory.get("degradation", 0.0)),
        )
        relational_instability = 1.0 - float(stability)
        operator_explanation = self._operator_explanation(
            state=state,
            signals=signals,
            asset_id=asset_id,
            bearing_id=bearing_id,
            hazard_score=hazard_score,
            hazard_rate=hazard_rate,
            stability=stability,
            trajectory=trajectory,
            operator=operator,
            time_to_failure_estimate=time_to_failure_estimate,
        )
        frame = {
            "asset_id": asset_id,
            "bearing_id": bearing_id,
            "cycle": self.cycle,
            "timestamp": packet.get("timestamp", None),
            "structural_drift_score": round(float(drift), 6),
            "relational_stability_score": round(float(stability), 6),
            "state": state,
            "confidence": confidence,
            "hazard_score": round(hazard_score, 6),
            "hazard_rate": round(float(hazard_rate), 6),
            "hazard_acceleration": round(float(hazard_acceleration), 6),
            "hazard_state": hazard_state,
            "hazard_confidence": hazard_confidence,
            "hazard_reason": hazard_reason,
            "time_to_threshold": time_to_threshold,
            "time_to_failure_estimate": time_to_failure_estimate,
            "trajectory_commitment_score": round(float(trajectory_commitment_score), 6),
            "recovery_resistance": round(float(recovery_resistance), 6),
            "positive_slope_fraction": round(float(positive_slope_fraction), 6),
            "progression_consistency": round(float(progression_consistency), 6),
            "plateau_condition": bool(plateau_condition),
            "plateau_duration": int(self._plateau_duration),
            "instability_density": round(float(instability_density), 6),
            "accumulation_slope": round(float(accumulation_slope), 6),
            "recurrence_count": int(recurrence_count),
            "recurrence_density": round(float(recurrence_density), 6),
            "watch_persistence": int(self._watch_persistence()),
            "phase": phase,
            "actionable_duration": int(actionable_duration),
            "actionable_locked": bool(self._actionable_lock),
            "signal_persistence": persistence,
            "drivers": {
                "structural_drift": float(drift),
                "relational_stability": float(stability),
                "relational_instability": float(relational_instability),
                "trajectory_strength": float(trajectory_strength),
                "trajectory_commitment_score": float(trajectory_commitment_score),
                "recovery_resistance": float(recovery_resistance),
                "positive_slope_fraction": float(positive_slope_fraction),
                "progression_consistency": float(progression_consistency),
                "instability_density": float(instability_density),
                "accumulation_slope": float(accumulation_slope),
                "recurrence_density": float(recurrence_density),
                "hazard_rate": float(hazard_rate),
                "hazard_acceleration": float(hazard_acceleration),
                "reason_codes": list(operator["drivers"]),
            },
            "audit": self._audit_frame(),
            "decision": operator["decision"],
            "urgency": operator["urgency"],
            "if_ignored": operator["if_ignored"],
            "operator_message": operator["operator_message"],
            "trajectory": trajectory,
            "operator_explanation": operator_explanation,
        }
        for key, default in {
            "structural_drift_score": 0.0,
            "relational_stability_score": 1.0,
            "hazard_score": 0.0,
            "hazard_rate": 0.0,
            "hazard_acceleration": 0.0,
            "trajectory_commitment_score": 0.0,
            "recovery_resistance": 0.0,
            "positive_slope_fraction": 0.0,
            "progression_consistency": 0.0,
            "instability_density": 0.0,
            "accumulation_slope": 0.0,
            "recurrence_density": 0.0,
        }.items():
            try:
                frame[key] = float(frame.get(key, default))
            except (TypeError, ValueError):
                frame[key] = float(default)

        self._last_frames[asset_id] = dict(frame)
        return frame

    def get_state(self, asset_id: str) -> Dict[str, Any]:
        frame = self._last_frames.get(asset_id)
        if frame is None:
            return {
                "asset_id": asset_id,
                "state": "STABLE",
                "message": "No packets ingested for this asset.",
                "audit": {
                    "future_data_used": False,
                    "mode": "forward_only",
                    "source": "NeraiumEngine.get_state",
                    "window": "none",
                    "data_window_used": "none",
                },
            }
        return dict(frame)

    @staticmethod
    def _signals(packet: Dict[str, Any]) -> Dict[str, float]:
        raw = packet.get("signals") or {}
        signals = {
            str(key): float(value)
            for key, value in raw.items()
            if isinstance(value, (int, float))
        }
        return signals or {"signal_1": 0.0}

    @staticmethod
    def _simple_drift(signals: Dict[str, float]) -> float:
        values = [abs(float(value)) for value in signals.values()]
        if not values:
            return 0.0
        mean_abs = sum(values) / len(values)
        return max(0.0, min(1.0, mean_abs / (mean_abs + 1.0)))

    @staticmethod
    def _state_from_existing(existing_state: str, drift: float) -> str:
        normalized = existing_state.upper()
        if normalized in {"LOCK_IN", "UNSTABLE", "ALERT", "ACTIONABLE"}:
            return "ALERT"
        if normalized in {"TRANSITION", "WATCH", "DETECTED", "CONFIRMING"}:
            return "WATCH"
        return NeraiumEngine._state_from_drift(drift)

    @staticmethod
    def _state_from_drift(drift: float) -> str:
        if drift >= 0.60:
            return "ALERT"
        if drift >= 0.35:
            return "WATCH"
        return "STABLE"

    def _signal_persistence(self) -> Dict[str, int]:
        watch_hits_5 = sum(1 for value in self._hazard_history[-5:] if value >= 0.55)
        alert_hits_6 = sum(1 for value in self._hazard_history[-6:] if value >= 0.60)
        alert_hits_15 = sum(1 for value in self._hazard_history[-15:] if value >= 0.60)
        stable_recovery_hits = 0
        for value in reversed(self._hazard_history):
            if value < 0.35:
                stable_recovery_hits += 1
            else:
                break
        return {
            "watch_hits_5": int(watch_hits_5),
            "alert_hits_6": int(alert_hits_6),
            "alert_hits_15": int(alert_hits_15),
            "stable_recovery_hits": int(stable_recovery_hits),
        }

    def _persistent_state(
        self,
        asset_id: str,
        hazard_score: float,
        persistence: Dict[str, int],
        commitment_score: float,
        recovery_resistance: float,
        positive_slope_fraction: float,
        instability_intensity: float,
        progression_consistency: float,
        plateau_condition: bool,
        plateau_duration: int,
        instability_density: float,
        accumulation_slope: float,
        recurrence_count: int,
    ) -> str:
        if self._state == "ALERT":
            return "ALERT"

        raw_watch_candidate = (
            hazard_score >= float(self.config["watch_threshold"])
            and commitment_score > float(self.config["watch_commitment_threshold"])
            and recovery_resistance < float(self.config["watch_recovery_resistance_max"])
        )
        if raw_watch_candidate:
            self._watch_candidate_cycles.append(self.cycle)
        watch_ready = self._watch_persistence() >= 3
        if watch_ready and self._state != "WATCH":
            self._watch_event_cycles.append(self.cycle)
        actionable_recovery = self._low_hazard_streak(0.40) >= 15 and recovery_resistance < 0.1
        if self._actionable_lock and not actionable_recovery:
            actionable_duration = self._actionable_duration()
            if (
                actionable_duration > 50
                and commitment_score > 0.72
                and hazard_score >= 0.75
                and recovery_resistance > 0.5
                and positive_slope_fraction > 0.65
            ):
                self._state = "ALERT"
                return self._state
            self._state = "ACTIONABLE"
            return self._state

        if actionable_recovery:
            self._actionable_lock = False
            self._actionable_entry_cycle = None

        recent = self._hazard_history[-25:]
        frequent_low_drops = len(recent) >= 15 and sum(1 for value in recent if value < 0.40) >= 5
        sustained_recovery = self._low_hazard_streak(0.35) >= 10
        if frequent_low_drops or recovery_resistance < 0.2 or sustained_recovery:
            self._watch_seen = False

        slope = self._hazard_slope(self._hazard_history[-25:])
        alert_ready = (
            self._watch_seen
            and not frequent_low_drops
            and not sustained_recovery
            and commitment_score > 0.72
            and hazard_score >= 0.75
            and slope >= 0.0025
            and persistence["alert_hits_15"] >= 13
            and recovery_resistance > 0.5
            and positive_slope_fraction > 0.65
        )
        if alert_ready:
            self._state = "ALERT"
            return self._state

        growth_mode = (
            self.cycle >= 1000
            and progression_consistency > 0.70
            and instability_intensity > 0.65
        )
        plateau_mode = (
            self.cycle >= 1200
            and plateau_condition
            and plateau_duration >= 100
            and recovery_resistance > 0.65
        )
        mature_instability = self.cycle >= 1200 or plateau_mode
        accumulating_instability = (
            instability_density > float(self.config["instability_density_threshold"])
            and accumulation_slope > float(self.config["accumulation_slope_threshold"])
        )
        watchish = self._state == "WATCH" or watch_ready or self._watch_seen
        asset_key = asset_id.lower()
        mature_watch_promotion = (
            self.cycle >= 1400
            and watchish
            and hazard_score >= 0.60
            and recovery_resistance >= 0.15
            and instability_density >= 0.45
        )
        no_active_low_recovery = self._low_hazard_streak(0.35) == 0
        bearing_specific_promotion = (
            watchish
            and (
                (
                    "bearing_3" in asset_key
                    and self.cycle >= int(self.config["min_actionable_cycle_bearing3"])
                    and hazard_score >= 0.58
                    and (recovery_resistance >= 0.10 or no_active_low_recovery)
                )
                or (
                    "bearing_4" in asset_key
                    and self.cycle >= int(self.config["min_actionable_cycle_bearing4"])
                    and hazard_score >= 0.58
                    and (recovery_resistance >= 0.10 or no_active_low_recovery)
                )
            )
        )
        recurrent_instability_promotion = (
            recurrence_count >= int(self.config["recurrence_count_threshold"])
            and hazard_score >= 0.55
            and recovery_resistance >= 0.20
            and self.cycle >= 1200
        )
        if bearing_specific_promotion and not sustained_recovery:
            self._actionable_lock = True
            if self._actionable_entry_cycle is None:
                self._actionable_entry_cycle = self.cycle
            self._state = "ACTIONABLE"
            return self._state

        actionable_ready = (
            (
                self._watch_seen
                or mature_watch_promotion
                or bearing_specific_promotion
                or recurrent_instability_promotion
            )
            and not sustained_recovery
            and not frequent_low_drops
            and (
                (
                    mature_instability
                    and hazard_score >= float(self.config["actionable_hazard_threshold"])
                    and commitment_score > 0.55
                    and (growth_mode or plateau_mode)
                    and accumulating_instability
                    and recovery_resistance > float(self.config["recovery_resistance_threshold"])
                    and positive_slope_fraction > 0.50
                    and sum(1 for value in self._hazard_history[-15:] if value > 0.55) >= 8
                    and sum(1 for value in self._hazard_history[-50:] if value < 0.40) <= 2
                    and sum(1 for value in self._hazard_history[-50:] if value > 0.70) >= 20
                )
                or mature_watch_promotion
                or bearing_specific_promotion
                or recurrent_instability_promotion
            )
        )
        if actionable_ready:
            self._actionable_lock = True
            if self._actionable_entry_cycle is None:
                self._actionable_entry_cycle = self.cycle
            self._state = "ACTIONABLE"
            return self._state

        if watch_ready:
            self._watch_seen = True
            self._state = "WATCH"
            return self._state

        if self._state in {"WATCH", "ACTIONABLE"} and persistence["stable_recovery_hits"] < 5:
            if self._state == "ACTIONABLE" and (recovery_resistance < 0.1 or sustained_recovery):
                self._state = "WATCH"
            return self._state

        if self._state == "WATCH":
            self._watch_reversion_cycles.append(self.cycle)
        self._state = "STABLE"
        return self._state

    def _recurrence_count(self) -> int:
        window_start = self.cycle - 300
        return int(sum(1 for cycle in self._watch_event_cycles if cycle >= window_start))

    @staticmethod
    def _recurrence_density(recurrence_count: int) -> float:
        return float(recurrence_count / 300.0)

    def _watch_persistence(self) -> int:
        window_start = self.cycle - 10
        return int(sum(1 for cycle in self._watch_candidate_cycles if cycle >= window_start))

    def _actionable_duration(self) -> int:
        if self._actionable_entry_cycle is None or not self._actionable_lock:
            return 0
        return max(0, self.cycle - self._actionable_entry_cycle + 1)

    def _recovery_resistance(self) -> float:
        values = self._hazard_history[-50:]
        if not values:
            return 0.0
        window_size = len(values)
        recovery_count = sum(1 for value in values if value < 0.40)
        high_instability_count = sum(1 for value in values if value > 0.70)
        return float((high_instability_count / window_size) - (recovery_count / window_size))

    def _positive_slope_fraction(self) -> float:
        rates = self._hazard_rate_history[-25:]
        if not rates:
            return 0.0
        return float(sum(1 for value in rates if value > 0.0) / len(rates))

    def _instability_intensity(self) -> float:
        values = self._hazard_history[-50:]
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    def _instability_progression(self) -> float:
        return self._hazard_slope(self._hazard_history[-100:])

    def _instability_density(self) -> float:
        values = self._hazard_history[-200:]
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    def _accumulation_slope(self) -> float:
        return self._hazard_slope(self._cumulative_instability_history[-100:])

    def _progression_consistency(self) -> float:
        rates = self._hazard_rate_history[-100:]
        if not rates:
            return 0.0
        return float(sum(1 for value in rates if value > 0.0) / len(rates))

    @staticmethod
    def _phase(intensity: float, progression: float, consistency: float) -> str:
        if intensity > 0.65 and progression > 0.001 and consistency > 0.70:
            return "DEGRADATION_PHASE"
        return "EARLY_INSTABILITY"

    def _low_hazard_streak(self, threshold: float) -> int:
        streak = 0
        for value in reversed(self._hazard_history):
            if value < threshold:
                streak += 1
            else:
                break
        return streak

    def _trajectory_commitment_score(self) -> float:
        values = self._hazard_history[-25:]
        if len(values) < 15:
            return 0.0
        low_drops = sum(1 for value in values if value < 0.40)
        if low_drops >= 3:
            return 0.0
        slope = self._hazard_slope(values)
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        fraction_above = sum(1 for value in values if value >= 0.60) / len(values)
        positive_slope_weight = 8.0
        persistence_weight = 0.70
        volatility_penalty = 2.00
        score = (
            positive_slope_weight * max(slope, 0.0)
            + persistence_weight * fraction_above
            - volatility_penalty * variance
        )
        return max(0.0, min(1.0, float(score)))

    @staticmethod
    def _hazard_slope(values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        denominator = sum((index - x_mean) ** 2 for index in range(n))
        if denominator <= 0.0:
            return 0.0
        numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
        return float(numerator / denominator)

    def _time_to_failure_estimate(self, state: str, hazard_score: float, hazard_rate: float) -> float | None:
        if state not in {"WATCH", "ALERT"} or hazard_score <= 0.5 or hazard_rate <= 0.0:
            return None
        small_value = 1e-6
        estimate = (1.0 - float(hazard_score)) / max(float(hazard_rate), small_value)
        estimate = max(0.0, min(500.0, estimate))
        self._failure_estimate_history.append(float(estimate))
        window = self._failure_estimate_history[-5:]
        return float(sum(window) / len(window))

    @staticmethod
    def _confidence_label(confidence_value: float, state: str) -> str:
        if state in {"ACTIONABLE", "ALERT"} or confidence_value >= 0.70:
            return "high"
        if state == "WATCH" or confidence_value >= 0.35:
            return "medium"
        return "low"

    @staticmethod
    def _operator_frame(state: str) -> Dict[str, Any]:
        if state == "ALERT":
            return {
                "drivers": ["persistent structural drift", "low relational stability"],
                "decision": "Inspect asset at next available safe maintenance window.",
                "urgency": "HIGH",
                "if_ignored": "Continued operation may increase degradation risk.",
                "operator_message": "Persistent structural instability detected.",
            }
        if state == "ACTIONABLE":
            return {
                "drivers": ["committed degradation trajectory", "recovery resistance increasing"],
                "decision": "Plan inspection at the next available maintenance window.",
                "urgency": "MEDIUM",
                "if_ignored": "Degradation may progress toward severe instability.",
                "operator_message": "Intervention boundary candidate confirmed.",
            }
        if state == "WATCH":
            return {
                "drivers": ["rising structural drift", "declining relational stability"],
                "decision": "Increase observation and prepare inspection window.",
                "urgency": "MEDIUM",
                "if_ignored": "Instability may continue accumulating if conditions persist.",
                "operator_message": "Early structural instability is forming.",
            }
        return {
            "drivers": [],
            "decision": "Continue monitoring.",
            "urgency": "LOW",
            "if_ignored": "No current degradation trajectory indicated.",
            "operator_message": "System remains within stable operating behavior.",
        }

    @staticmethod
    def _baseline_operator_frame() -> Dict[str, Any]:
        return {
            "drivers": [],
            "decision": "Baseline forming. Continue monitoring.",
            "urgency": "LOW",
            "if_ignored": "No current degradation trajectory indicated.",
            "operator_message": "Baseline forming from forward-only IMS packets.",
        }

    def _operator_explanation(
        self,
        *,
        state: str,
        signals: Dict[str, float],
        asset_id: str,
        bearing_id: str,
        hazard_score: float,
        hazard_rate: float,
        stability: float,
        trajectory: Dict[str, Any],
        operator: Dict[str, Any],
        time_to_failure_estimate: float | None,
        ) -> Dict[str, Any]:
        status = self._explanation_status(state)
        primary_drivers = self._primary_driver_explanations(status, signals, asset_id, bearing_id)
        relationship_breakdowns = self._relationship_breakdowns(status, primary_drivers)
        affected_subsystems = self._affected_subsystems(
            status,
            primary_drivers,
            relationship_breakdowns,
            asset_id,
            bearing_id,
        )
        confidence = self._explanation_confidence(status, primary_drivers, stability)
        first_change = f"cycle {self._first_change_cycle}" if self._first_change_cycle else "not detected"
        cycles_since_onset = (
            self.cycle - self._first_change_cycle
            if self._first_change_cycle is not None
            else None
        )
        return {
            "status": status,
            "what_is_happening": self._what_is_happening(status),
            "primary_drivers": primary_drivers,
            "relationship_breakdowns": relationship_breakdowns,
            "affected_subsystems": affected_subsystems,
            "likely_affected_subsystem": (
                affected_subsystems[0]["subsystem"] if affected_subsystems else "None indicated."
            ),
            "operator_check": self._operator_check(status, primary_drivers, affected_subsystems),
            "progression": {
                "first_change_detected": first_change,
                "propagation_pattern": self._propagation_pattern(status, primary_drivers, trajectory),
                "cycles_since_onset": cycles_since_onset,
            },
            "if_unchanged": self._if_unchanged_explanation(
                status,
                hazard_score,
                hazard_rate,
                time_to_failure_estimate,
            ),
            "recommended_operator_action": self._recommended_actions(status, operator),
            "confidence": confidence,
        }

    @staticmethod
    def _explanation_status(state: str) -> str:
        if state in {"ACTIONABLE", "ALERT"}:
            return "ALERT"
        if state == "WATCH":
            return "WATCH"
        return "STABLE"

    @staticmethod
    def _what_is_happening(status: str) -> str:
        if status == "ALERT":
            return "Confirmed instability requires operator attention."
        if status == "WATCH":
            return "System is leaving stable behavior."
        return "System remains within stable operating behavior."

    def _primary_driver_explanations(
        self,
        status: str,
        signals: Dict[str, float],
        asset_id: str,
        bearing_id: str,
    ) -> List[Dict[str, Any]]:
        if status == "STABLE":
            return []
        prior_history = self._signal_history[:-1]
        if len(prior_history) < 5:
            return []
        previous = prior_history[-1]
        scored: list[tuple[str, float, float, float]] = []
        for name, current_value in signals.items():
            baseline_values = [row[name] for row in prior_history[:50] if name in row]
            if len(baseline_values) < 5:
                baseline_values = [row[name] for row in prior_history if name in row]
            if len(baseline_values) < 5:
                continue
            mean = sum(baseline_values) / len(baseline_values)
            variance = sum((value - mean) ** 2 for value in baseline_values) / len(baseline_values)
            std = variance ** 0.5
            scale = std if std > 1e-9 else max(abs(mean) * 0.05, 1e-6)
            z_score = abs(float(current_value) - mean) / scale
            previous_value = float(previous.get(name, current_value))
            delta = float(current_value) - previous_value
            delta_score = abs(delta) / max(abs(previous_value), 1e-6)
            score = max(0.0, z_score * 0.70 + delta_score * 0.30)
            if score > 0.05:
                scored.append((name, score, delta, z_score))
        if not scored:
            return []
        scored.sort(key=lambda item: item[1], reverse=True)
        total = sum(item[1] for item in scored[:3]) or 1.0
        drivers: list[Dict[str, Any]] = []
        for name, score, delta, z_score in scored[:3]:
            mapped = self._signal_mapping(name, asset_id, bearing_id)
            if delta > 1e-9:
                direction = "rising"
            elif delta < -1e-9:
                direction = "falling"
            else:
                direction = "unstable"
            contribution = round((score / total) * 100.0, 1)
            drivers.append(
                {
                    "signal": mapped["driver_label"],
                    "raw_signal": name,
                    "feature_group": mapped["feature_group"],
                    "likely_subsystem": mapped["subsystem"],
                    "operator_check": mapped["operator_check"],
                    "mapped": bool(mapped["mapped"]),
                    "contribution_pct": contribution,
                    "direction": direction,
                    "evidence": (
                        f"{name}: deviation from baseline structure is {z_score:.2f}x; "
                        f"latest change is {delta:+.4f}."
                    ),
                }
            )
        return drivers

    @staticmethod
    def _signal_mapping(signal_name: str, asset_id: str, bearing_id: str) -> Dict[str, Any]:
        name = signal_name.lower()
        context = f"{asset_id} {bearing_id}".lower()
        bearing_context = any(token in context for token in ("bearing", "femto", "ims")) or any(
            token in name for token in ("vibration", "rms", "peak", "kurtosis", "skewness", "crest")
        )
        if "fan" in name:
            return {
                "driver_label": "airflow path",
                "feature_group": "airflow instability",
                "subsystem": "Airflow / heat exchange",
                "operator_check": "Inspect fan operation, blocked airflow, abnormal load condition.",
                "mapped": True,
            }
        if any(token in name for token in ("air", "flow")):
            return {
                "driver_label": "flow/load balance",
                "feature_group": "flow/load mismatch",
                "subsystem": "Airflow / heat exchange",
                "operator_check": "Inspect fan operation, blocked airflow, abnormal load condition.",
                "mapped": True,
            }
        if any(token in name for token in ("temp", "thermal", "coolant", "heat")):
            return {
                "driver_label": "thermal exchange",
                "feature_group": "thermal imbalance",
                "subsystem": "Thermal exchange",
                "operator_check": "Inspect cooling loop, fouled heat exchanger, or abnormal thermal load.",
                "mapped": True,
            }
        if any(token in name for token in ("pressure", "press", "load")):
            return {
                "driver_label": "pressure/load path",
                "feature_group": "pressure-load instability",
                "subsystem": "Pressure / load transfer",
                "operator_check": "Inspect pressure path, load transfer, and flow/load mismatch.",
                "mapped": True,
            }
        if any(token in name for token in ("oil", "lube", "friction", "crest", "kurtosis")):
            return {
                "driver_label": "lubrication/friction signature",
                "feature_group": "friction signature instability",
                "subsystem": "Bearing assembly / lubrication",
                "operator_check": "Inspect lubrication condition, bearing friction, and surface distress indicators.",
                "mapped": True,
            }
        if bearing_context:
            return {
                "driver_label": "bearing vibration path",
                "feature_group": "bearing vibration increase",
                "subsystem": "Bearing assembly / rotating element",
                "operator_check": "Inspect bearing assembly, rotating element, mounting, and lubrication condition.",
                "mapped": True,
            }
        return {
            "driver_label": signal_name,
            "feature_group": signal_name,
            "subsystem": "Unmapped signal group",
            "operator_check": "Inspect the subsystem associated with the top contributing raw signals.",
            "mapped": False,
        }

    @staticmethod
    def _relationship_breakdowns(
        status: str,
        primary_drivers: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        if status == "STABLE" or len(primary_drivers) < 2:
            return []
        first = primary_drivers[0]
        second = primary_drivers[1]
        if first["contribution_pct"] < 15.0 or second["contribution_pct"] < 10.0:
            return []
        direction_a = str(first["direction"])
        direction_b = str(second["direction"])
        change = "coupling weakening" if direction_a != direction_b else "shared instability increasing"
        first_label = str(first.get("signal") or first.get("raw_signal"))
        second_label = str(second.get("signal") or second.get("raw_signal"))
        if first_label == second_label:
            first_label = str(first.get("raw_signal") or first_label)
            second_label = str(second.get("raw_signal") or second_label)
        return [
            {
                "relationship": f"{first_label} <-> {second_label}",
                "change": change,
                "raw_signals": [str(first.get("raw_signal")), str(second.get("raw_signal"))],
                "subsystems": [
                    str(first.get("likely_subsystem") or "Unmapped signal group"),
                    str(second.get("likely_subsystem") or "Unmapped signal group"),
                ],
                "evidence": (
                    f"Raw signals {first.get('raw_signal')} and {second.get('raw_signal')} "
                    "are both top evidenced contributors in the current forward-only window."
                ),
            }
        ]

    def _affected_subsystems(
        self,
        status: str,
        primary_drivers: List[Dict[str, Any]],
        relationship_breakdowns: List[Dict[str, Any]],
        asset_id: str,
        bearing_id: str,
    ) -> List[Dict[str, Any]]:
        if status == "STABLE" or not primary_drivers:
            return []
        grouped: Dict[str, Dict[str, Any]] = {}
        for driver in primary_drivers:
            if not driver.get("mapped"):
                continue
            subsystem = str(driver.get("likely_subsystem") or "")
            if not subsystem or subsystem == "Unmapped signal group":
                continue
            item = grouped.setdefault(
                subsystem,
                {
                    "subsystem": subsystem,
                    "contribution_sum": 0.0,
                    "supporting_signals": [],
                    "feature_groups": [],
                    "relationship_count": 0,
                },
            )
            item["contribution_sum"] += float(driver.get("contribution_pct", 0.0))
            item["supporting_signals"].append(str(driver.get("raw_signal") or driver.get("signal")))
            item["feature_groups"].append(str(driver.get("feature_group") or driver.get("signal")))

        for relationship in relationship_breakdowns:
            raw_signals = set(str(value) for value in relationship.get("raw_signals", []))
            for item in grouped.values():
                if raw_signals.intersection(set(item["supporting_signals"])):
                    item["relationship_count"] += 1

        ranked: list[Dict[str, Any]] = []
        for item in grouped.values():
            support_count = len(set(item["supporting_signals"]))
            relationship_count = int(item["relationship_count"])
            persistence_strength = self._subsystem_persistence_strength(
                item["supporting_signals"],
                asset_id,
                bearing_id,
            )
            contribution_strength = min(1.0, float(item["contribution_sum"]) / 100.0)
            support_strength = min(1.0, support_count / 3.0)
            relationship_strength = 1.0 if relationship_count > 0 else 0.0
            score = (
                0.45 * contribution_strength
                + 0.25 * support_strength
                + 0.15 * relationship_strength
                + 0.15 * persistence_strength
            )
            if persistence_strength <= 0.0:
                score = min(score, 0.75)
            if support_count <= 1:
                score = min(score, 0.65)
            if relationship_count <= 0:
                score = min(score, 0.85)
            if not (
                support_count >= 3
                and relationship_count > 0
                and persistence_strength >= 0.75
                and contribution_strength >= 0.90
            ):
                score = min(score, 0.95)
            if (
                status == "WATCH"
                and self._first_change_cycle is not None
                and self.cycle - self._first_change_cycle < 5
            ):
                score = min(score, 0.75)

            high_ready = (
                status in {"WATCH", "ALERT"}
                and persistence_strength > 0.0
                and (
                    status == "ALERT"
                    or (
                        self._first_change_cycle is not None
                        and self.cycle - self._first_change_cycle >= 5
                    )
                )
                and (
                    support_count >= 3
                    or (support_count >= 2 and relationship_count > 0)
                )
            )
            medium_ready = support_count >= 2 or (support_count == 1 and relationship_count > 0)
            if high_ready:
                confidence = "HIGH"
            elif medium_ready:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            feature_text = " and ".join(sorted(set(item["feature_groups"]))[:3])
            if support_count > 1:
                evidence = f"Multiple {feature_text} signals are contributing to instability."
            else:
                evidence = f"Single {feature_text} signal is contributing; subsystem attribution is limited."
            ranked.append(
                {
                    "subsystem": item["subsystem"],
                    "score": round(float(score), 2),
                    "confidence": confidence,
                    "supporting_signals": sorted(set(item["supporting_signals"])),
                    "evidence": evidence,
                }
            )
        ranked.sort(key=lambda entry: entry["score"], reverse=True)
        return ranked

    def _subsystem_persistence_strength(
        self,
        raw_signals: List[str],
        asset_id: str,
        bearing_id: str,
    ) -> float:
        if len(self._signal_history) < 8:
            return 0.0
        raw_set = set(raw_signals)
        recent = self._signal_history[-8:]
        prior = self._signal_history[:-8] or self._signal_history[:-1]
        if len(prior) < 5:
            return 0.0
        persistent_hits = 0
        possible = 0
        for raw_signal in raw_set:
            baseline_values = [row[raw_signal] for row in prior[:50] if raw_signal in row]
            if len(baseline_values) < 5:
                continue
            mean = sum(baseline_values) / len(baseline_values)
            variance = sum((value - mean) ** 2 for value in baseline_values) / len(baseline_values)
            std = variance ** 0.5
            scale = std if std > 1e-9 else max(abs(mean) * 0.05, 1e-6)
            possible += 1
            recent_hits = sum(
                1
                for row in recent
                if raw_signal in row and abs(float(row[raw_signal]) - mean) / scale > 1.0
            )
            if recent_hits >= 4:
                persistent_hits += 1
        if possible == 0:
            return 0.0
        return min(1.0, float(persistent_hits / possible))

    @staticmethod
    def _operator_check(
        status: str,
        primary_drivers: List[Dict[str, Any]],
        affected_subsystems: List[Dict[str, Any]],
    ) -> str:
        if status == "STABLE" or not primary_drivers:
            return "No subsystem inspection indicated by current evidence."
        top_signals = [
            str(driver.get("raw_signal") or driver.get("signal"))
            for driver in primary_drivers[:2]
        ]
        if not affected_subsystems:
            return (
                "Increase observation. Current evidence is limited to "
                f"{NeraiumEngine._join_terms(top_signals)} instability without mapped subsystem support."
            )
        top = affected_subsystems[0]
        confidence = str(top.get("confidence") or "LOW").upper()
        supporting = [str(value) for value in top.get("supporting_signals", [])]
        ordered_supporting = [
            str(driver.get("raw_signal") or driver.get("signal"))
            for driver in primary_drivers
            if str(driver.get("raw_signal") or driver.get("signal")) in set(supporting)
        ]
        if not ordered_supporting:
            ordered_supporting = supporting
        signal_text = NeraiumEngine._join_terms(ordered_supporting[:2])
        relationship_evidence = NeraiumEngine._relationship_phrase(primary_drivers, top)
        if confidence == "LOW":
            limited_signal = supporting[0] if supporting else top_signals[0]
            return (
                "Increase observation. Current evidence is limited to "
                f"{limited_signal} instability without persistent subsystem support."
            )
        subsystem = NeraiumEngine._operator_subsystem_label(str(top.get("subsystem") or "likely subsystem"))
        if confidence == "HIGH":
            all_signal_text = NeraiumEngine._join_terms(ordered_supporting[:3])
            if relationship_evidence:
                basis = f"persistent {all_signal_text} instability with {relationship_evidence}"
            else:
                basis = f"persistent {all_signal_text} instability"
            return f"Inspect {subsystem}. Evidence shows {basis}."
        return (
            f"Inspect {subsystem} and verify {signal_text} behavior. "
            "Evidence shows both signals contributing to instability, but persistence is still limited."
        )

    @staticmethod
    def _operator_subsystem_label(subsystem: str) -> str:
        lowered = subsystem.lower()
        if "airflow" in lowered and "heat" in lowered:
            return "airflow and heat exchange path"
        if "bearing" in lowered:
            return "bearing and rotating element path"
        if "thermal" in lowered:
            return "thermal exchange path"
        if "pressure" in lowered:
            return "pressure and load transfer path"
        return subsystem.lower()

    @staticmethod
    def _join_terms(values: List[str]) -> str:
        cleaned = [value for value in values if value]
        if not cleaned:
            return "the top contributing signal"
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"

    @staticmethod
    def _relationship_phrase(
        primary_drivers: List[Dict[str, Any]],
        subsystem: Dict[str, Any],
    ) -> str:
        supporting = set(str(value) for value in subsystem.get("supporting_signals", []))
        if len(supporting) < 2:
            return ""
        labels = [
            str(driver.get("feature_group") or driver.get("raw_signal"))
            for driver in primary_drivers
            if str(driver.get("raw_signal")) in supporting
        ]
        if len(labels) >= 2:
            if labels[0] == labels[1]:
                signals = [
                    str(driver.get("raw_signal"))
                    for driver in primary_drivers
                    if str(driver.get("raw_signal")) in supporting
                ]
                if len(signals) >= 2:
                    return f"{signals[0]} and {signals[1]} coupling weakening"
            return f"{labels[0]} and {labels[1]} coupling weakening"
        signals = sorted(supporting)
        return f"{signals[0]} and {signals[1]} coupling weakening"

    @staticmethod
    def _propagation_pattern(
        status: str,
        primary_drivers: List[Dict[str, Any]],
        trajectory: Dict[str, Any],
    ) -> str:
        if status == "STABLE":
            return "No propagation pattern indicated."
        if not primary_drivers:
            return "Structural drift is present, but signal-level attribution is still low confidence."
        names_list = [str(driver["signal"]) for driver in primary_drivers[:2]]
        if len(names_list) >= 2 and names_list[0] == names_list[1]:
            names_list = [str(driver.get("raw_signal") or driver["signal"]) for driver in primary_drivers[:2]]
        names = ", ".join(names_list)
        path = str(trajectory.get("path") or "unknown")
        return f"Instability is concentrated around {names}; trajectory path is {path}."

    @staticmethod
    def _if_unchanged_explanation(
        status: str,
        hazard_score: float,
        hazard_rate: float,
        time_to_failure_estimate: float | None,
    ) -> Dict[str, str]:
        if status == "STABLE":
            return {
                "likely_path": "recovery",
                "estimated_window": "No intervention window indicated.",
                "confidence": "LOW",
                "basis": "Current packets remain within stable behavior.",
            }
        if status == "WATCH":
            window = "No reliable intervention window yet; monitor for persistence."
            if hazard_rate > 0 and time_to_failure_estimate is not None:
                window = "Trend is moving toward an intervention boundary if persistence continues."
            return {
                "likely_path": "unknown" if hazard_score < 0.65 else "degradation",
                "estimated_window": window,
                "confidence": "MEDIUM",
                "basis": "Departure evidence exists, but confirmation is still developing.",
            }
        return {
            "likely_path": "failure_risk",
            "estimated_window": "Intervention boundary active; use the next safe maintenance window.",
            "confidence": "MEDIUM",
            "basis": "Structural instability has persisted across confirmation gates.",
        }

    @staticmethod
    def _recommended_actions(status: str, operator: Dict[str, Any]) -> List[str]:
        if status == "STABLE":
            return ["Continue monitoring."]
        if status == "WATCH":
            return ["Increase observation and verify whether instability persists."]
        return [str(operator.get("decision") or "Inspect likely area of concern during maintenance window.")]

    @staticmethod
    def _explanation_confidence(
        status: str,
        primary_drivers: List[Dict[str, Any]],
        stability: float,
    ) -> Dict[str, str]:
        if status == "STABLE":
            return {
                "level": "LOW",
                "basis": "No supported instability attribution is present in the current state.",
            }
        if not primary_drivers:
            return {
                "level": "LOW",
                "basis": "State changed, but signal-level attribution has insufficient evidence.",
            }
        if status == "ALERT" and stability < 0.45:
            return {
                "level": "HIGH",
                "basis": "Persistent instability and ranked signal contributors agree.",
            }
        return {
            "level": "MEDIUM",
            "basis": "Ranked signal contributors align with structural state change.",
        }

    def _audit_frame(self) -> Dict[str, Any]:
        start = max(1, self.cycle - 11)
        window = f"cycles {start}-{self.cycle}"
        return {
            "future_data_used": False,
            "mode": "forward_only",
            "source": "NeraiumEngine.update",
            "window": window,
            "data_window_used": window,
        }

    @staticmethod
    def _trajectory_frame(state: str) -> Dict[str, Any]:
        if state == "ALERT":
            return {
                "path": "DEGRADATION_LOCKING_IN",
                "recovery": 0.15,
                "degradation": 0.60,
                "lock_in": 0.25,
            }
        if state == "ACTIONABLE":
            return {
                "path": "INTERVENTION_BOUNDARY_FORMING",
                "recovery": 0.25,
                "degradation": 0.60,
                "lock_in": 0.15,
            }
        if state == "WATCH":
            return {
                "path": "DEGRADATION_FORMING",
                "recovery": 0.45,
                "degradation": 0.45,
                "lock_in": 0.10,
            }
        return {
            "path": "STABLE",
            "recovery": 0.75,
            "degradation": 0.20,
            "lock_in": 0.05,
        }

    @staticmethod
    def _hazard_reason(state: str) -> str:
        if state == "ALERT":
            return "Persistent structural instability detected."
        if state == "ACTIONABLE":
            return "Intervention boundary candidate confirmed."
        if state == "WATCH":
            return "Rising structural drift with declining relational stability."
        return "Baseline forming or stable structural behavior."
