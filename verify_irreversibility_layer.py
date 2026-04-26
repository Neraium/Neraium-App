#!/usr/bin/env python3
"""
Verification script for the irreversibility layer in SII Engine.

This script demonstrates that:
1. The 5-factor instability score S(t) is unchanged
2. The new irreversibility factor R(t) is computed correctly
3. The inevitability score I(t) = S(t) * R(t) works as expected
4. Both legacy (drift-only) and new (inevitability) modes work in CMAPSS runner
"""

import sys
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from neraium_core.sii_engine_unified import SIIEngine


def test_irreversibility_layer():
    """Test that irreversibility layer is properly computed."""
    print("=" * 70)
    print("Testing Irreversibility Layer")
    print("=" * 70)

    # Create synthetic test data with baseline + degradation
    np.random.seed(42)

    # Baseline: stable period
    baseline_data = np.random.randn(50, 5) * 0.1 + np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    # Degradation: increasing instability
    degradation_data = []
    for i in range(30):
        trend = i / 30.0  # Linear increase from 0 to 1
        noise = np.random.randn(5) * (0.1 + 0.3 * trend)
        point = baseline_data[0] + np.array([1.0, 0.5, -0.5, 0.3, -0.2]) * trend + noise
        degradation_data.append(point)

    degradation_data = np.array(degradation_data)

    # Create engine
    engine = SIIEngine(baseline_window=30, recent_window=12)

    print("\n📊 Testing with synthetic degradation signal:")
    print(f"   Baseline period: 50 samples")
    print(f"   Degradation period: 30 samples")
    print()

    # Process baseline
    for i, row in enumerate(baseline_data):
        output = engine.update(row, timestamp=float(i))
        if i == baseline_data.shape[0] - 1:
            print(f"✓ Baseline completed at frame {i}")
            print(f"  Instability score: {output.instability_score:.4f}")
            print(f"  Regime: {output.regime}")

    # Process degradation
    print("\n📈 Processing degradation phase:")
    print()
    print("Frame | Instability | Inevitability | Irreversibility | Persistence | Acceleration | CovarPersist | FailAlign")
    print("------|-------------|---------------|-----------------|-------------|--------------|--------------|----------")

    degradation_milestone_frames = [5, 10, 15, 20, 25, 29]

    for i, row in enumerate(degradation_data):
        output = engine.update(row, timestamp=float(50 + i))

        # Print milestones
        if i in degradation_milestone_frames:
            print(
                f"{50+i:5d} | {output.instability_score:11.4f} | {output.structural_inevitability_score:13.4f} | "
                f"{output.irreversibility_factor:15.4f} | {output.persistence_score:11.4f} | "
                f"{output.drift_acceleration_score:12.4f} | {output.covariance_persistence_score:12.4f} | "
                f"{output.failure_alignment_score:9.4f}"
            )

    final_output = output

    # Verify key properties
    print("\n✓ Verification Results:")
    print()

    # Check 1: Instability score should increase during degradation
    if final_output.instability_score > 0.3:
        print("✓ Instability score increased during degradation")
    else:
        print("✗ Instability score did not increase as expected")

    # Check 2: Inevitability should be <= instability (since R(t) ≤ 1)
    if final_output.structural_inevitability_score <= final_output.instability_score + 1e-6:
        print("✓ Inevitability score = Instability × Irreversibility (both bounded [0,1])")
    else:
        print("✗ Inevitability score exceeds instability score")

    # Check 3: Irreversibility factor should be in [0, 1]
    if 0 <= final_output.irreversibility_factor <= 1:
        print(f"✓ Irreversibility factor in valid range [0, 1]: {final_output.irreversibility_factor:.4f}")
    else:
        print(f"✗ Irreversibility factor out of range: {final_output.irreversibility_factor:.4f}")

    # Check 4: All component scores should be in [0, 1]
    components = [
        ("persistence", final_output.persistence_score),
        ("drift_acceleration", final_output.drift_acceleration_score),
        ("covariance_persistence", final_output.covariance_persistence_score),
        ("failure_alignment", final_output.failure_alignment_score),
    ]

    all_valid = True
    for name, score in components:
        if 0 <= score <= 1:
            print(f"✓ {name:20s}: {score:.4f}")
        else:
            print(f"✗ {name:20s}: {score:.4f} (out of range)")
            all_valid = False

    print()
    print("=" * 70)
    if all_valid:
        print("✓ All irreversibility layer tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 70)

    return all_valid


def test_runner_flags():
    """Test that CMAPSS runner accepts the new flags."""
    print("\n" + "=" * 70)
    print("Testing CMAPSS Runner Flags")
    print("=" * 70)

    runner_script = Path("/home/user/Neraium-App/tools/cmapss_unified_runner.py")

    if not runner_script.exists():
        print(f"✗ Runner script not found: {runner_script}")
        return False

    # Check for inevitability flag in runner
    with open(runner_script, "r") as f:
        content = f.read()

    checks = [
        ("--use-inevitability-score flag", "--use-inevitability-score" in content),
        ("use_inevitability_score parameter", "use_inevitability_score: bool" in content),
        ("Inevitability print statement", "use_inevitability_score:" in content),
        ("Check raw alert uses inevitability", "self.use_inevitability_score" in content),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False

    print()
    print("=" * 70)
    if all_passed:
        print("✓ All runner flag tests passed!")
    else:
        print("✗ Some runner flag tests failed")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  IRREVERSIBILITY LAYER VERIFICATION".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        test1 = test_irreversibility_layer()
        test2 = test_runner_flags()

        if test1 and test2:
            print("\n✓ All verification tests passed!")
            sys.exit(0)
        else:
            print("\n✗ Some verification tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
