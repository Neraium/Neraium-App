import numpy as np

from neraium_core.intelligence_stack.sii import SII


def _timeline_from_array(arr: np.ndarray) -> list[dict[str, float]]:
    return [{f"s{i}": float(row[i]) for i in range(arr.shape[1])} for row in arr]


def test_degrading_series_progression_is_ordered_and_stable() -> None:
    rng = np.random.default_rng(42)
    baseline = rng.normal(0.0, 0.03, size=(200, 3))
    model = SII(["s0", "s1", "s2"], baseline)

    n = 120
    ramp = np.linspace(0.0, 1.0, n)
    degrading = np.column_stack(
        [
            0.05 * ramp + rng.normal(0.0, 0.01, n),
            0.10 * ramp + rng.normal(0.0, 0.01, n),
            0.15 * ramp + rng.normal(0.0, 0.01, n),
        ]
    )
    out = model.assess_sequence(_timeline_from_array(degrading))
    scores = np.array([row["score"] for row in out], dtype=float)

    early = float(scores[int(0.15 * (n - 1))])
    mid = float(scores[int(0.50 * (n - 1))])
    late = float(scores[int(0.85 * (n - 1))])

    assert early <= mid <= late
    assert scores[-1] >= (late - 0.08)


def test_constant_healthy_input_stays_non_critical() -> None:
    baseline = np.zeros((100, 4), dtype=float)
    model = SII(["s0", "s1", "s2", "s3"], baseline)

    constant = np.zeros((80, 4), dtype=float)
    out = model.assess_sequence(_timeline_from_array(constant))

    assert all(row["state"] in {"healthy", "elevated"} for row in out)


def test_nan_input_does_not_crash_or_become_critical_by_default() -> None:
    baseline = np.zeros((60, 2), dtype=float)
    model = SII(["s0", "s1"], baseline)

    timeline = [
        {"s0": 0.0, "s1": 0.0},
        {"s0": float("nan"), "s1": float("inf")},
        {"s0": float("nan"), "s1": -float("inf")},
    ]
    out = model.assess_sequence(timeline)

    assert all(np.isfinite(float(row["score"])) for row in out)
    assert all(row["state"] != "critical" for row in out)


def test_progression_envelope_prevents_severe_late_collapse() -> None:
    baseline = np.zeros((120, 3), dtype=float)
    model = SII(["s0", "s1", "s2"], baseline)

    n = 100
    values = np.zeros((n, 3), dtype=float)
    values[30:75, :] = 0.8
    values[75:, :] = -0.2

    out = model.assess_sequence(_timeline_from_array(values))
    scores = np.array([row["score"] for row in out], dtype=float)

    peak = float(np.max(scores[30:75]))
    last = float(scores[-1])
    assert last >= peak * model.progression.progression_decay_floor ** (n - 1 - 74)


def test_baseline_uses_early_healthy_slice_min_30_rows() -> None:
    baseline = np.arange(80 * 2, dtype=float).reshape(80, 2)
    model = SII(["s0", "s1"], baseline)

    assert model.baseline.shape[0] == 30
    np.testing.assert_allclose(model.baseline, baseline[:30])
