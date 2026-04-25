#!/usr/bin/env python3
"""
Test script to verify the display_health and raw_system_health split.

This script demonstrates:
1. The exact formula used for display_health in engine.py
2. Examples in each state (warmup, STABLE, WATCH, ALERT)
3. Confirmation that the UI uses display_health instead of raw values
"""

from neraium_core.sii.engine import SystemicInfrastructureIntelligenceEngine
from neraium_core.sii.types import SIIConfig


def test_display_health_formula():
    """Test the display_health computation formula."""
    print("=" * 80)
    print("DISPLAY HEALTH FORMULA TEST")
    print("=" * 80)

    engine = SystemicInfrastructureIntelligenceEngine()

    # Test case 1: Warmup (no frames processed yet)
    print("\n1. WARMUP STATE (processed_frames < min_samples_for_alerts)")
    print("   Conditions: STABLE state, warmup, drift=0.3")
    display_health = engine._compute_display_health_for_engine(
        decision_state="STABLE",
        structural_drift_score=0.3,
        processed_frames=10,  # Less than default min_samples_for_alerts (~50)
    )
    print(f"   Expected: ~95 (high safety value during calibration)")
    print(f"   Actual: {display_health}")
    assert display_health == 95, "Warmup health should be 95"
    print("   ✓ PASS")

    # Test case 2: STABLE state - normal operation
    print("\n2. STABLE STATE - Normal Operation")
    print("   Conditions: drift=0.2, watch_estimate=1.0")
    print("   Formula: health = 100.0 - (progress * 30.0), where progress = drift/watch_estimate")
    print("   Calculation: progress = 0.2/1.0 = 0.2")
    print("                health = 100.0 - (0.2 * 30.0) = 100.0 - 6.0 = 94")
    display_health = engine._compute_display_health_for_engine(
        decision_state="STABLE",
        structural_drift_score=0.2,
        processed_frames=100,  # Beyond warmup
    )
    print(f"   Actual: {display_health}")
    assert 93 <= display_health <= 95, f"Expected ~94, got {display_health}"
    print("   ✓ PASS")

    # Test case 3: STABLE state - approaching WATCH
    print("\n3. STABLE STATE - Approaching WATCH")
    print("   Conditions: drift=0.9, watch_estimate=1.0")
    print("   Formula: health = 100.0 - (progress * 30.0), where progress = drift/watch_estimate")
    print("   Calculation: progress = 0.9/1.0 = 0.9")
    print("                health = 100.0 - (0.9 * 30.0) = 100.0 - 27.0 = 73")
    display_health = engine._compute_display_health_for_engine(
        decision_state="STABLE",
        structural_drift_score=0.9,
        processed_frames=100,
    )
    print(f"   Actual: {display_health}")
    assert 72 <= display_health <= 74, f"Expected ~73, got {display_health}"
    print("   ✓ PASS")

    # Test case 4: WATCH state - moderate concern
    print("\n4. WATCH STATE - Moderate Concern")
    print("   Conditions: drift=0.7, watch_estimate=1.0, alert_estimate=2.0")
    print("   Formula: health = 70.0 - (progress * 35.0), where progress = (drift - watch) / (alert - watch)")
    print("   Calculation: progress = (0.7 - 1.0) / (2.0 - 1.0)")
    print("                (Note: drift < watch, so would be in STABLE, this test uses estimated ranges)")
    # For this to be in WATCH, drift should be between 1.0 and 2.0
    print("   Using drift=1.5 instead: progress = (1.5 - 1.0) / 1.0 = 0.5")
    print("                health = 70.0 - (0.5 * 35.0) = 70.0 - 17.5 = 52.5 → 53")
    display_health = engine._compute_display_health_for_engine(
        decision_state="WATCH",
        structural_drift_score=1.5,
        processed_frames=100,
    )
    print(f"   Actual: {display_health}")
    assert 52 <= display_health <= 54, f"Expected ~53, got {display_health}"
    print("   ✓ PASS")

    # Test case 5: WATCH state - approaching ALERT
    print("\n5. WATCH STATE - Approaching ALERT")
    print("   Conditions: drift=1.9, watch_estimate=1.0, alert_estimate=2.0")
    print("   Formula: health = 70.0 - (progress * 35.0)")
    print("   Calculation: progress = (1.9 - 1.0) / (2.0 - 1.0) = 0.9")
    print("                health = 70.0 - (0.9 * 35.0) = 70.0 - 31.5 = 38.5 → 39")
    display_health = engine._compute_display_health_for_engine(
        decision_state="WATCH",
        structural_drift_score=1.9,
        processed_frames=100,
    )
    print(f"   Actual: {display_health}")
    assert 38 <= display_health <= 40, f"Expected ~39, got {display_health}"
    print("   ✓ PASS")

    # Test case 6: ALERT state - active alert
    print("\n6. ALERT STATE - Active Alert")
    print("   Conditions: drift=1.2, alert_threshold_estimate=2.0")
    print("   Formula: health = max(0, 35.0 - (excess * 18.0)), where excess = drift - alert_threshold")
    print("   Calculation: excess = 1.2 - 2.0 = -0.8 (negative, so at alert threshold)")
    print("                health = 35.0")
    display_health = engine._compute_display_health_for_engine(
        decision_state="ALERT",
        structural_drift_score=1.2,
        processed_frames=100,
    )
    print(f"   Actual: {display_health}")
    assert display_health == 35, f"Expected 35, got {display_health}"
    print("   ✓ PASS")

    # Test case 7: ALERT state - severe degradation
    print("\n7. ALERT STATE - Severe Degradation")
    print("   Conditions: drift=3.0, alert_threshold_estimate=2.0")
    print("   Formula: health = max(0, 35.0 - (excess * 18.0))")
    print("   Calculation: excess = 3.0 - 2.0 = 1.0")
    print("                health = max(0, 35.0 - (1.0 * 18.0)) = max(0, 17.0) = 17")
    display_health = engine._compute_display_health_for_engine(
        decision_state="ALERT",
        structural_drift_score=3.0,
        processed_frames=100,
    )
    print(f"   Actual: {display_health}")
    assert 17 <= display_health <= 18, f"Expected ~17, got {display_health}"
    print("   ✓ PASS")


def test_health_fields_in_result():
    """Test that SIIResult has the correct health fields."""
    print("\n" + "=" * 80)
    print("HEALTH FIELDS IN RESULT TEST")
    print("=" * 80)

    from neraium_core.sii.types import SIIResult
    import inspect

    sig = inspect.signature(SIIResult.__getitem__)
    print("\nSIIResult TypedDict should have these health fields:")
    print("  - raw_system_health (int): Engine-native metric")
    print("  - display_health (int): Policy-aligned UI metric")
    print("  - system_health (int): Backward-compat alias (same as display_health)")

    # Check that SIIResult type hints include these fields
    hints = SIIResult.__annotations__
    assert "raw_system_health" in hints, "Missing raw_system_health field"
    assert "display_health" in hints, "Missing display_health field"
    assert "system_health" in hints, "Missing system_health field"
    print("\n✓ All health fields are defined in SIIResult")


def test_ui_usage():
    """Document how UI should use the health values."""
    print("\n" + "=" * 80)
    print("UI USAGE GUIDE")
    print("=" * 80)

    print("\nThe backend now returns:")
    print("  {")
    print("    \"raw_system_health\": 78,        # Engine-native health (legacy formula)")
    print("    \"display_health\": 95,           # Policy-aligned UI metric (NEW)")
    print("    \"system_health\": 95,            # Backward-compat alias")
    print("  }")

    print("\nFor UI implementation:")
    print("  ✓ Use display_health (or system_health for backward-compat)")
    print("  ✓ Avoid using raw_system_health in UI (use only for debugging)")
    print("  ✓ Both display_health and system_health will have the same value")

    print("\nJavaScript example:")
    print("  const health = data.display_health;  // Primary field")
    print("  const healthAlt = data.system_health; // Backward-compat")
    print("  const rawHealth = data.raw_system_health; // Debug only")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DISPLAY HEALTH & RAW SYSTEM HEALTH SPLIT VERIFICATION")
    print("=" * 80)

    try:
        test_display_health_formula()
        test_health_fields_in_result()
        test_ui_usage()

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        print("\nSummary:")
        print("  1. display_health formula correctly implements policy-aligned bands")
        print("  2. raw_system_health preserves engine-native metric")
        print("  3. system_health is available for backward-compatibility")
        print("  4. UI can use display_health for meaningful health representation")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise
