"""Baseline and state management.

Responsibilities:
- Rolling baseline correlation tracking
- Baseline lock/unlock mechanics
- Regime library persistence and loading
- Regime baseline updates
- Episode memory and transitions
- State snapshot/restore for serialization

Note: This layer manages all stateful elements. Separated from detection
logic so state can be reset, serialized, or restored independently.
"""

from typing import Dict, Any, Optional, List
import numpy as np


class BaselineManager:
    """Manages rolling baseline correlation matrix."""

    def __init__(self):
        self._rolling_baseline_corr: Optional[np.ndarray] = None
        self._baseline_locked: bool = False
        self._baseline_set_at: Optional[str] = None
        self._baseline_coverage_samples: int = 0

    def get_rolling_baseline(self) -> Optional[np.ndarray]:
        """Get current rolling baseline correlation matrix."""
        return self._rolling_baseline_corr

    def set_rolling_baseline(self, corr: Optional[np.ndarray]) -> None:
        """Update rolling baseline correlation matrix."""
        if corr is not None:
            self._rolling_baseline_corr = np.asarray(corr, dtype=float, copy=True)
        else:
            self._rolling_baseline_corr = None

    def lock_baseline(self, locked: bool = True) -> None:
        """Lock/unlock baseline from updates."""
        self._baseline_locked = bool(locked)

    def is_locked(self) -> bool:
        """Check if baseline is locked."""
        return self._baseline_locked

    def reset(self) -> None:
        """Reset baseline to None."""
        self._rolling_baseline_corr = None
        self._baseline_locked = False
        self._baseline_set_at = None
        self._baseline_coverage_samples = 0

    def get_info(self) -> Dict[str, Any]:
        """Get baseline metadata."""
        return {
            "available": self._rolling_baseline_corr is not None,
            "locked": self._baseline_locked,
            "set_at": self._baseline_set_at,
            "coverage_samples": self._baseline_coverage_samples,
        }


class RegimeManager:
    """Manages regime library and per-regime baselines."""

    def __init__(self):
        self._regime_signatures: List[Dict[str, object]] = []
        self._regime_baselines: Dict[str, Dict[str, object]] = {}

    def add_regime_signature(self, signature: Dict[str, object]) -> None:
        """Add a regime signature to the library."""
        if isinstance(signature, dict):
            self._regime_signatures.append(signature)

    def get_regime_signatures(self) -> List[Dict[str, object]]:
        """Get all regime signatures."""
        return list(self._regime_signatures)

    def set_regime_signatures(self, sigs: List[Dict[str, object]]) -> None:
        """Replace regime signatures."""
        self._regime_signatures = list(sigs) if sigs else []

    def get_regime_baselines(self) -> Dict[str, Dict[str, object]]:
        """Get regime baselines dict."""
        return dict(self._regime_baselines)

    def set_regime_baselines(self, baselines: Dict[str, Dict[str, object]]) -> None:
        """Replace regime baselines."""
        self._regime_baselines = dict(baselines) if baselines else {}

    def update_regime_baseline(
        self, regime_name: str, baseline: Dict[str, object]
    ) -> None:
        """Update or create a regime baseline."""
        if regime_name and isinstance(baseline, dict):
            self._regime_baselines[regime_name] = dict(baseline)

    def reset(self) -> None:
        """Clear all regime data."""
        self._regime_signatures = []
        self._regime_baselines = {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "regimes": list(self._regime_signatures),
            "baselines": dict(self._regime_baselines),
        }


class EpisodeMemory:
    """Tracks episode history and current episode state."""

    def __init__(self):
        self._episode_history: List[Dict[str, object]] = []
        self._current_episode: Dict[str, object] = {
            "current_episode_type": "onset",
            "episode_index": 0,
            "episode_start": 0,
            "episode_duration": 0,
            "episode_transition_reason": "initialization",
            "episode_history": [],
        }

    def get_current_episode(self) -> Dict[str, object]:
        """Get current episode state."""
        return dict(self._current_episode)

    def update_episode(self, update: Dict[str, object]) -> None:
        """Update current episode fields."""
        self._current_episode.update(update)

    def new_episode(
        self,
        episode_type: str,
        reason: str,
        start_index: int = 0,
    ) -> None:
        """Start a new episode."""
        self._episode_history.append(dict(self._current_episode))
        self._current_episode = {
            "current_episode_type": episode_type,
            "episode_index": len(self._episode_history),
            "episode_start": start_index,
            "episode_duration": 0,
            "episode_transition_reason": reason,
            "episode_history": [],
        }

    def get_history(self) -> List[Dict[str, object]]:
        """Get episode history."""
        return [dict(e) for e in self._episode_history]

    def reset(self) -> None:
        """Clear all episode data."""
        self._episode_history = []
        self._current_episode = {
            "current_episode_type": "onset",
            "episode_index": 0,
            "episode_start": 0,
            "episode_duration": 0,
            "episode_transition_reason": "reset",
            "episode_history": [],
        }


class EngineState:
    """Aggregates all stateful components."""

    def __init__(self):
        self.baseline = BaselineManager()
        self.regimes = RegimeManager()
        self.episodes = EpisodeMemory()

    def snapshot(self) -> Dict[str, Any]:
        """Create serializable snapshot of state."""
        return {
            "baseline": {
                "rolling_corr": (
                    self.baseline._rolling_baseline_corr.tolist()
                    if self.baseline._rolling_baseline_corr is not None
                    else None
                ),
                "locked": self.baseline._baseline_locked,
                "set_at": self.baseline._baseline_set_at,
                "coverage_samples": self.baseline._baseline_coverage_samples,
            },
            "regimes": self.regimes.to_dict(),
            "episodes": {
                "history": self.episodes.get_history(),
                "current": self.episodes.get_current_episode(),
            },
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Restore state from snapshot."""
        if "baseline" in snapshot:
            bl = snapshot["baseline"]
            self.baseline._baseline_locked = bool(bl.get("locked", False))
            self.baseline._baseline_set_at = bl.get("set_at")
            self.baseline._baseline_coverage_samples = int(bl.get("coverage_samples", 0))
            if bl.get("rolling_corr") is not None:
                self.baseline._rolling_baseline_corr = np.asarray(
                    bl["rolling_corr"], dtype=float
                )

        if "regimes" in snapshot:
            reg = snapshot["regimes"]
            self.regimes.set_regime_signatures(reg.get("regimes", []))
            self.regimes.set_regime_baselines(reg.get("baselines", {}))

        if "episodes" in snapshot:
            ep = snapshot["episodes"]
            self.episodes._episode_history = [
                dict(e) for e in ep.get("history", [])
            ]
            current = ep.get("current")
            if current:
                self.episodes._current_episode = dict(current)

    def reset(self) -> None:
        """Clear all state."""
        self.baseline.reset()
        self.regimes.reset()
        self.episodes.reset()
