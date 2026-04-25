#!/usr/bin/env python
"""Test script to verify optimization implementations."""
from __future__ import annotations

import time
import numpy as np
from neraium_core.realtime.circular_buffer import CircularNumpyBuffer, CircularMatrix2DBuffer
from neraium_core.realtime.incremental_stats import WelfordStats, IncrementalCovarianceTracker
from neraium_core.geometry import correlation_matrix
from neraium_core.spectral import dominant_mode_loading
from neraium_core.realtime.lazy_computation import ThresholdBasedLazyComputation


def test_circular_buffers():
    """Test circular buffer implementation."""
    print("Testing CircularNumpyBuffer...")
    buf = CircularNumpyBuffer(10)

    for i in range(25):
        buf.append(float(i))

    assert len(buf) == 10, f"Expected len=10, got {len(buf)}"
    assert buf[0] == 15.0, f"Expected buf[0]=15, got {buf[0]}"
    assert buf[-1] == 24.0, f"Expected buf[-1]=24, got {buf[-1]}"

    arr = buf.to_array()
    assert len(arr) == 10, f"Expected array len=10, got {len(arr)}"
    print("✓ CircularNumpyBuffer works correctly")

    print("Testing CircularMatrix2DBuffer...")
    mbuf = CircularMatrix2DBuffer(8, 3)

    for i in range(20):
        vec = np.array([float(i), float(i*2), float(i*3)])
        mbuf.append(vec)

    assert len(mbuf) == 8, f"Expected len=8, got {len(mbuf)}"
    recent = mbuf.recent(4)
    assert recent is not None and recent.shape == (4, 3), f"Expected shape (4,3), got {recent.shape if recent is not None else None}"
    print("✓ CircularMatrix2DBuffer works correctly")


def test_welford_stats():
    """Test Welford incremental statistics."""
    print("Testing WelfordStats...")
    stats = WelfordStats(3)

    # Generate some data
    rng = np.random.default_rng(42)
    data = rng.standard_normal(size=(100, 3))

    for row in data:
        stats.update(row)

    mean = stats.get_mean()
    var = stats.get_variance()

    # Compare with direct computation
    direct_mean = np.mean(data, axis=0)
    direct_var = np.var(data, axis=0, ddof=1)

    assert np.allclose(mean, direct_mean, rtol=1e-10), "Mean mismatch"
    assert np.allclose(var, direct_var, rtol=1e-10), "Variance mismatch"
    print("✓ WelfordStats matches direct computation")


def test_correlation_caching():
    """Test correlation matrix caching."""
    print("Testing correlation matrix caching...")

    data = np.random.randn(50, 10)

    # First call
    t0 = time.perf_counter()
    corr1 = correlation_matrix(data)
    t1 = time.perf_counter()
    time_first = t1 - t0

    # Second call (should hit cache)
    t0 = time.perf_counter()
    corr2 = correlation_matrix(data)
    t1 = time.perf_counter()
    time_cached = t1 - t0

    assert np.allclose(corr1, corr2), "Correlation matrices don't match"
    print(f"✓ First call: {time_first*1000:.3f}ms, Cached call: {time_cached*1000:.3f}ms")
    if time_cached < time_first:
        speedup = time_first / time_cached
        print(f"  Cache speedup: {speedup:.2f}x")


def test_lazy_computation():
    """Test lazy computation with threshold."""
    print("Testing ThresholdBasedLazyComputation...")

    call_count = [0]

    def expensive_fn():
        call_count[0] += 1
        return np.random.randn(10)

    lazy = ThresholdBasedLazyComputation(expensive_fn, threshold=0.7, cooldown_frames=2)

    # Low score - should not compute
    result = lazy.compute(0.5)
    assert result is None and call_count[0] == 0, "Should not compute below threshold"

    # High score - should compute
    result = lazy.compute(0.8)
    assert result is not None and call_count[0] == 1, "Should compute above threshold"

    # Within cooldown - cached
    result = lazy.compute(0.5)
    assert result is not None and call_count[0] == 1, "Should use cache during cooldown"

    # After cooldown, low score - no compute
    result = lazy.compute(0.5)
    result = lazy.compute(0.5)
    assert call_count[0] == 1, "Should not compute again after cooldown"

    print("✓ ThresholdBasedLazyComputation works correctly")


def test_spectral_caching():
    """Test spectral computation caching."""
    print("Testing spectral computation caching...")

    mat = np.array([[2.0, 0.5], [0.5, 1.0]])

    # First call
    t0 = time.perf_counter()
    result1 = dominant_mode_loading(mat, cached=True)
    t1 = time.perf_counter()
    time_first = t1 - t0

    # Second call (should hit cache)
    t0 = time.perf_counter()
    result2 = dominant_mode_loading(mat, cached=True)
    t1 = time.perf_counter()
    time_cached = t1 - t0

    assert result1 == result2, "Results don't match"
    print(f"✓ First call: {time_first*1000:.3f}ms, Cached call: {time_cached*1000:.3f}ms")


def test_covariance_tracker():
    """Test incremental covariance tracking."""
    print("Testing IncrementalCovarianceTracker...")

    tracker = IncrementalCovarianceTracker(3)
    rng = np.random.default_rng(42)
    data = rng.standard_normal(size=(50, 3))

    for row in data:
        tracker.update(row)

    inc_cov = tracker.get_covariance()
    inc_corr = tracker.get_correlation()

    # Direct computation
    direct_cov = np.cov(data, rowvar=False, ddof=1)

    assert np.allclose(inc_cov, direct_cov, rtol=1e-10), "Covariance mismatch"
    print("✓ IncrementalCovarianceTracker matches direct computation")


def main():
    """Run all tests."""
    print("=" * 60)
    print("OPTIMIZATION VERIFICATION TESTS")
    print("=" * 60)
    print()

    try:
        test_circular_buffers()
        print()
        test_welford_stats()
        print()
        test_covariance_tracker()
        print()
        test_correlation_caching()
        print()
        test_lazy_computation()
        print()
        test_spectral_caching()
        print()
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
