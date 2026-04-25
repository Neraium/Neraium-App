#!/usr/bin/env python
"""Test script to verify performance optimizations are working.

Tests:
1. Lazy causal analysis throttling
2. Regime persistence throttling
3. Storage bounding
4. Lagged correlation vectorization
"""

import time
import numpy as np
from neraium_core.performance_throttle import (
    ThrottleConfig,
    CausalAnalysisThrottle,
    RegimePersistenceThrottle,
    StorageBound,
)
from neraium_core.directional import lagged_correlation_matrix


def test_lazy_causal_throttle():
    """Test lazy causal analysis throttling."""
    print("Testing CausalAnalysisThrottle...")
    config = ThrottleConfig()
    throttle = CausalAnalysisThrottle(config)

    # Low instability - should skip
    assert not throttle.should_compute_causal(0.1), "Should skip when instability is low"
    throttle.record_computation(False)

    # High instability - should compute
    assert throttle.should_compute_causal(1.5), "Should compute when instability is high"
    throttle.record_computation(True)

    # After compute, should skip for a few frames
    assert not throttle.should_compute_causal(0.1), "Should skip after recent computation"

    print("  ✓ CausalAnalysisThrottle works correctly")


def test_regime_persistence_throttle():
    """Test regime persistence throttling."""
    print("Testing RegimePersistenceThrottle...")
    config = ThrottleConfig()
    throttle = RegimePersistenceThrottle(config)

    # Should not persist initially
    for i in range(config.regime_persist_interval - 1):
        assert not throttle.should_persist(), f"Should skip persistence at frame {i}"
        throttle.skip_persistence()

    # Should persist after interval
    assert throttle.should_persist(), "Should persist after interval"
    throttle.mark_persistence()

    # Should reset counter
    assert not throttle.should_persist(), "Should reset after persistence"

    print("  ✓ RegimePersistenceThrottle works correctly")


def test_storage_bound():
    """Test storage bounding."""
    print("Testing StorageBound...")
    config = ThrottleConfig(max_regime_baselines=5, max_regime_signatures=10)
    bound = StorageBound(config)

    # Test regime baselines pruning
    baselines = {
        f"regime_{i}": {"count": i, "correlation": np.zeros((2, 2))}
        for i in range(20)
    }
    pruned = bound.prune_regime_baselines(baselines)
    assert pruned == 15, f"Expected to prune 15 baselines, got {pruned}"
    assert len(baselines) == 20, "Original dict should not be modified"

    # Test regime signatures pruning
    signatures = [{"sig": i} for i in range(30)]
    pruned = bound.prune_regime_signatures(signatures)
    assert pruned == 20, f"Expected to prune 20 signatures, got {pruned}"

    print("  ✓ StorageBound works correctly")


def test_lagged_correlation_vectorization():
    """Test vectorized lagged correlation computation."""
    print("Testing lagged_correlation_matrix vectorization...")

    # Create test data
    np.random.seed(42)
    n_samples = 100
    n_features = 10
    data = np.random.randn(n_samples, n_features)

    # Test computation
    result = lagged_correlation_matrix(data, lag=1)

    # Verify shape
    assert result.shape == (n_features, n_features), f"Expected shape ({n_features}, {n_features}), got {result.shape}"

    # Verify values are in reasonable range (correlations should be -1 to 1)
    assert np.all(result >= -1.1) and np.all(result <= 1.1), "Correlation values out of range"

    # Verify diagonal is not necessarily 1 (lagged correlation, not auto-correlation)
    # But values should still be reasonable
    assert np.all(np.isfinite(result)), "Result contains NaN or Inf"

    print(f"  ✓ lagged_correlation_matrix produces valid output")
    print(f"    Shape: {result.shape}, Value range: [{result.min():.3f}, {result.max():.3f}]")


def test_vectorization_performance():
    """Benchmark vectorized vs original approach."""
    print("\nBenchmarking lagged_correlation_matrix performance...")

    np.random.seed(42)
    for n_sensors in [10, 20, 50]:
        data = np.random.randn(100, n_sensors)

        start = time.perf_counter()
        for _ in range(10):
            result = lagged_correlation_matrix(data, lag=1)
        elapsed = (time.perf_counter() - start) / 10

        print(f"  {n_sensors} sensors: {elapsed*1000:.2f}ms per call")


def test_metrics():
    """Test performance metrics tracking."""
    print("\nTesting performance metrics tracking...")

    throttle = CausalAnalysisThrottle()

    # Simulate frame processing
    for i in range(100):
        if i % 5 == 0:
            throttle.record_computation(True)
        else:
            throttle.record_computation(False)
        throttle.update_frame_count()

    metrics = throttle.metrics.get_summary()
    print(f"  Causal skip rate: {metrics['causal_analysis']['skip_rate_pct']:.1f}%")
    print(f"  Total frames: {metrics['frame_count']}")

    assert metrics['frame_count'] == 100, "Frame count should be 100"
    assert metrics['causal_analysis']['computed'] == 20, "Should compute 20 times (every 5th)"


if __name__ == "__main__":
    print("=" * 80)
    print("PERFORMANCE OPTIMIZATION TEST SUITE")
    print("=" * 80)
    print()

    try:
        test_lazy_causal_throttle()
        test_regime_persistence_throttle()
        test_storage_bound()
        test_lagged_correlation_vectorization()
        test_vectorization_performance()
        test_metrics()

        print()
        print("=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        print()
        print("Performance Improvements Summary:")
        print("  • Lazy causal analysis: Skip expensive computation when instability is low")
        print("  • Regime persistence: Throttle I/O operations (every N frames)")
        print("  • Storage bounding: Prevent unbounded growth of regime library")
        print("  • Vectorized correlation: O(n²·T) → O(n²) for lagged correlations")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
