import numpy as np

from neraium_core.intelligence_stack.detector import _build_ensemble_vote_series, _causal_rolling_mean


def test_causal_rolling_mean_respects_partial_history() -> None:
    arr = np.array([1.0, 3.0, 5.0, 7.0])
    out = _causal_rolling_mean(arr, window=3)
    assert np.allclose(out, np.array([1.0, 2.0, 3.0, 5.0]))


def test_build_ensemble_vote_series_requires_configured_vote_quorum() -> None:
    ema = np.array([0.1, 0.2, 0.7, 0.9, 1.1, 1.2], dtype=float)
    vote_ratio, vote_threshold = _build_ensemble_vote_series(
        ema=ema,
        threshold=0.6,
        micro_window=2,
        meso_window=3,
        macro_window=4,
        acceleration_window=1,
        acceleration_threshold=0.01,
        min_votes=3,
    )

    assert vote_ratio.shape == ema.shape
    assert np.isclose(vote_threshold, 0.75)
    assert vote_ratio[-1] >= vote_threshold
