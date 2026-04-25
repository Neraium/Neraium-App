"""Adaptive replay pacing and frame timing for greenhouse demo.

Controls playback timing based on phase transitions to make the replay
feel deliberate and stable rather than twitchy.

Principles:
- Stable phases linger longer to establish baseline
- Transition phases feel noticeably different in duration
- Verdict changes feel earned by replay progression
- Frame advancement is smooth and predictable
"""

from __future__ import annotations

from typing import Any


def get_phase_type(row: dict[str, Any]) -> str:
    """Classify a replay row into a phase type."""
    if not isinstance(row, dict):
        return "STABLE"

    # Check explicit phase/transition_type fields
    transition_type = (str(row.get("transition_type") or "")).strip().upper()
    if transition_type in {"TRANSITION", "REORGANIZATION"}:
        return transition_type

    # Infer from drift and stability if available
    drift = _safe_float(row.get("structural_drift_score", row.get("drift")), 0.0)
    stability = _safe_float(row.get("relational_stability_score", row.get("stability")), 1.0)

    # High drift or low stability suggests transition
    if drift >= 0.55 or stability <= 0.45:
        return "TRANSITION"
    if drift >= 0.35 or stability <= 0.65:
        return "TRANSITION"

    return "STABLE"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ReplayPaceController:
    """Manages timing and pacing for greenhouse replay playback.

    Attributes:
        speed_multiplier: User speed setting (0.1 to 1.5)
        stable_linger_ratio: How much longer to dwell in stable phases (default 1.4)
        transition_emphasis_ratio: Frame dwell in transition phases (default 1.1)
    """

    def __init__(
        self,
        speed_multiplier: float = 1.0,
        stable_linger_ratio: float = 1.4,
        transition_emphasis_ratio: float = 1.1,
    ):
        self.speed_multiplier = max(0.1, min(1.5, float(speed_multiplier)))
        self.stable_linger_ratio = max(1.0, stable_linger_ratio)
        self.transition_emphasis_ratio = max(1.0, transition_emphasis_ratio)
        self._previous_phase = "STABLE"

    def get_step_delay(
        self,
        frame_index: int,
        rows: list[dict[str, Any]],
    ) -> float:
        """Calculate delay for current frame based on context.

        Returns delay in seconds that creates good pacing:
        - Baseline delays around 0.65-0.8s per frame at speed 1.0
        - Stable phases linger longer to establish baseline
        - Transitions feel more urgent/active
        - Speed multiplier scales inversely (higher speed = faster frames)
        """
        # Base delay calculation
        # Lower speed_multiplier = longer delay
        # Formula gives ~0.7s at speed=1.0
        base_delay = max(0.45, 0.85 / max(float(self.speed_multiplier), 0.1))

        # Get current phase
        if 0 <= frame_index < len(rows):
            current_row = rows[frame_index]
            current_phase = get_phase_type(current_row)
        else:
            current_phase = "STABLE"

        # Apply phase-specific adjustment
        phase_factor = 1.0

        if current_phase == "STABLE":
            # Stable phases linger to establish baseline
            phase_factor = self.stable_linger_ratio
        elif current_phase == "TRANSITION":
            # Transitions feel slightly faster to convey urgency
            phase_factor = self.transition_emphasis_ratio
        elif current_phase == "REORGANIZATION":
            # Reorganization phases have same emphasis as transition
            phase_factor = self.transition_emphasis_ratio

        self._previous_phase = current_phase

        return round(base_delay * phase_factor, 3)


class VerdictStabilizer:
    """Prevents verdict from flipping frame-to-frame via hysteresis.

    Maintains a stable displayed verdict while tracking the real underlying
    verdict, only switching when confidence crosses a threshold.

    This makes the interface feel like it's observing real change, not
    reacting to every minor fluctuation.
    """

    def __init__(self, hysteresis_threshold: float = 0.08):
        """Initialize verdict stabilizer.

        Args:
            hysteresis_threshold: How much the signal must change to flip verdict.
                                 Roughly in 0-1 range for drift intensity.
        """
        self.hysteresis_threshold = max(0.01, min(0.2, float(hysteresis_threshold)))
        self._displayed_verdict = "SUPPRESS"
        self._real_verdict = "SUPPRESS"
        self._signal_strength = 0.0

    def apply_stability(
        self,
        gate_decision: dict[str, Any],
        signal_strength: float | None = None,
    ) -> dict[str, Any]:
        """Apply hysteresis to a gate decision.

        The displayed verdict only changes when:
        1. Real verdict changes, AND
        2. Signal strength has moved enough to justify it

        Args:
            gate_decision: Raw gate decision from engine
            signal_strength: Optional override for drift intensity (0-1)
                           Defaults to drift from decision.

        Returns:
            Modified gate decision with stabilized verdict
        """
        decision = dict(gate_decision) if isinstance(gate_decision, dict) else {}

        # Extract real verdict and signal strength
        real_verdict = (str(decision.get("decision") or "SUPPRESS")).upper()

        if signal_strength is None:
            # Try to extract from decision data
            transition = decision.get("transition")
            if isinstance(transition, dict):
                signal_strength = _safe_float(transition.get("delta_drift"), 0.0)
            else:
                signal_strength = 0.0

        signal_strength = _safe_float(signal_strength, 0.0)
        self._real_verdict = real_verdict
        self._signal_strength = signal_strength

        # Check if we should change displayed verdict
        if self._displayed_verdict != real_verdict:
            # Verdict changed in reality - check if signal is strong enough
            if abs(signal_strength) >= self.hysteresis_threshold:
                # Strong enough to display the change
                self._displayed_verdict = real_verdict
            # else: Suppress the display change, keep previous verdict

        # Return decision with potentially stabilized verdict
        stable_decision = dict(decision)
        stable_decision["decision"] = self._displayed_verdict
        stable_decision["_real_decision"] = real_verdict
        stable_decision["_signal_strength"] = round(signal_strength, 6)
        stable_decision["_verdict_changed"] = self._displayed_verdict != real_verdict

        return stable_decision

    def reset(self) -> None:
        """Reset stabilizer to initial state."""
        self._displayed_verdict = "SUPPRESS"
        self._real_verdict = "SUPPRESS"
        self._signal_strength = 0.0


class ReasoningStateTracker:
    """Tracks reasoning state to avoid re-rendering identical text.

    During replay, reasoning lines should only update when the underlying
    values change meaningfully, not on every frame.
    """

    def __init__(self, change_threshold: float = 0.06):
        """Initialize tracker.

        Args:
            change_threshold: Minimum change in relevant metrics to trigger update
        """
        self.change_threshold = max(0.01, min(0.2, float(change_threshold)))
        self._previous_state = {}
        self._previous_rendered = {}

    def should_update_reasoning(
        self,
        current_row: dict[str, Any],
        previous_row: dict[str, Any] | None = None,
    ) -> bool:
        """Check if reasoning should be re-rendered.

        Returns True if metrics have changed enough to warrant update.
        """
        if not isinstance(current_row, dict):
            return False

        if previous_row is None:
            previous_row = self._previous_state

        # Key metrics that matter for reasoning
        key_fields = [
            "structural_drift_score",
            "relational_stability_score",
            "event_admitted",
            "transition_type",
            "system_health",
        ]

        for field in key_fields:
            curr_val = _safe_float(
                current_row.get(field),
                str(current_row.get(field)) if field in current_row else "",
            )
            prev_val = _safe_float(
                previous_row.get(field),
                str(previous_row.get(field)) if field in previous_row else "",
            )

            # For numeric fields
            if isinstance(curr_val, (int, float)) and isinstance(prev_val, (int, float)):
                if abs(curr_val - prev_val) > self.change_threshold:
                    self._previous_state = dict(current_row)
                    return True
            # For categorical fields
            elif str(curr_val) != str(prev_val):
                self._previous_state = dict(current_row)
                return True

        return False

    def reset(self) -> None:
        """Reset tracking state."""
        self._previous_state = {}
        self._previous_rendered = {}


def calculate_phase_progression(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze phase distribution to inform pacing.

    Returns metadata about stable vs transition phases to help
    configure appropriate dwell times.
    """
    if not rows:
        return {
            "stable_count": 0,
            "transition_count": 0,
            "reorganization_count": 0,
            "phase_sequence": [],
        }

    phase_sequence = [get_phase_type(row) for row in rows]

    return {
        "stable_count": phase_sequence.count("STABLE"),
        "transition_count": phase_sequence.count("TRANSITION"),
        "reorganization_count": phase_sequence.count("REORGANIZATION"),
        "phase_sequence": phase_sequence,
        "average_stable_run_length": _calculate_average_run_length(phase_sequence, "STABLE"),
        "transition_entry_indices": [
            i for i, phase in enumerate(phase_sequence)
            if phase in {"TRANSITION", "REORGANIZATION"} and (i == 0 or phase_sequence[i - 1] == "STABLE")
        ],
    }


def _calculate_average_run_length(sequence: list[str], value: str) -> float:
    """Calculate average consecutive run length of value in sequence."""
    if not sequence or value not in sequence:
        return 0.0

    runs = []
    current_run = 0

    for item in sequence:
        if item == value:
            current_run += 1
        else:
            if current_run > 0:
                runs.append(current_run)
            current_run = 0

    if current_run > 0:
        runs.append(current_run)

    return sum(runs) / len(runs) if runs else 0.0


class SmoothUIFrameController:
    """Manages frame skipping and UI update rate decoupling.

    The backend processes all frames at full speed, but the UI only redraws
    at a human-friendly rate (5-6 Hz) to avoid the "frame loading" effect.

    This creates the perception of continuous motion rather than a slideshow.
    """

    def __init__(self, target_ui_hz: float = 5.5):
        """Initialize frame controller.

        Args:
            target_ui_hz: Target UI update frequency in Hz (default 5.5 = ~180ms per update)
        """
        self.target_ui_hz = max(3.0, min(15.0, float(target_ui_hz)))
        self.target_frame_interval = 1.0 / self.target_ui_hz
        self._last_ui_update_time = 0.0
        self._frame_accumulator = 0
        self._total_elapsed = 0.0

    def should_render_frame(self, current_time: float) -> bool:
        """Check if enough time has passed to render the next UI frame.

        Args:
            current_time: Current elapsed time in seconds

        Returns:
            True if UI should update, False to skip this frame
        """
        elapsed_since_update = current_time - self._last_ui_update_time
        if elapsed_since_update >= self.target_frame_interval:
            self._last_ui_update_time = current_time
            return True
        return False

    def reset(self) -> None:
        """Reset timing state."""
        self._last_ui_update_time = 0.0
        self._frame_accumulator = 0
        self._total_elapsed = 0.0


class InterpolationHelper:
    """Provides smooth interpolation for visual state transitions.

    Prevents hard jumps in progress indicators, drift values, etc.
    """

    @staticmethod
    def lerp(start: float, end: float, t: float) -> float:
        """Linear interpolation between two values.

        Args:
            start: Starting value
            end: Ending value
            t: Interpolation factor (0.0 to 1.0)

        Returns:
            Interpolated value
        """
        return start + (end - start) * max(0.0, min(1.0, t))

    @staticmethod
    def smooth_step(t: float) -> float:
        """Smoothstep interpolation (cubic ease in/out).

        Creates smoother motion than linear interpolation.
        """
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)
