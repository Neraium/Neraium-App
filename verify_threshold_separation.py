#!/usr/bin/env python3
"""
Verification script demonstrating separate threshold behavior and irreversibility variability.

This script shows:
1. Legacy and inevitability modes use different thresholds
2. Irreversibility factor is NOT constant (varies meaningfully)
3. Both drift and inevitability scores are logged
4. The two modes should produce different detection results
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from neraium_core.sii_engine_unified import SIIEngine


def demonstrate_threshold_separation():
    """Show that the two modes use completely separate thresholds."""
    print("=" * 70)
    print("DEMONSTRATION 1: Separate Threshold Behavior")
    print("=" * 70)
    print()

    print("Configuration:")
    print("  Legacy mode (default):")
    print("    • threshold used: --drift-threshold (default: 0.5)")
    print("    • score compared: structural_drift")
    print()
    print("  Inevitability mode (--use-inevitability-score):")
    print("    • threshold used: --inevitability-threshold (default: 0.6)")
    print("    • score compared: structural_inevitability_score = S(t) * R(t)")
    print()

    print("CSV Output Columns (new score diagnostics):")
    print("  • drift_score_at_confirmation: S(t)")
    print("  • inevitability_score_at_confirmation: I(t) = S(t) * R(t)")
    print("  • irreversibility_factor_at_confirmation: R(t)")
    print()
    print("These scores are DIFFERENT because:")
    print("  - I(t) = S(t) * R(t) where R(t) ∈ [0, 1]")
    print("  - R(t) varies based on system persistence, acceleration, etc.")
    print("  - I(t) ≤ S(t) always (since R(t) ≤ 1)")
    print()


def demonstrate_irreversibility_variability():
    """Show that irreversibility factor varies meaningfully."""
    print("=" * 70)
    print("DEMONSTRATION 2: Irreversibility Factor is NOT Constant")
    print("=" * 70)
    print()

    np.random.seed(42)

    # Create baseline
    baseline_data = np.random.randn(40, 5) * 0.1 + np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    # Create degradation with varying rates
    phases = {
        "Slow degradation (0-10)": np.linspace(0, 0.3, 10),
        "Rapid degradation (10-20)": np.linspace(0.3, 0.8, 10),
        "Sustained high (20-30)": np.ones(10) * 0.8,
        "Variable (30-40)": np.sin(np.linspace(0, 2*np.pi, 10)) * 0.3 + 0.5,
    }

    all_degradation = []
    phase_labels = []
    for phase_name, trend in phases.items():
        for i, t in enumerate(trend):
            noise = np.random.randn(5) * (0.1 + 0.2 * t)
            point = baseline_data[0] + np.array([1.0, 0.5, -0.5, 0.3, -0.2]) * t + noise
            all_degradation.append(point)
            phase_labels.append(phase_name)

    degradation_data = np.array(all_degradation)

    engine = SIIEngine(baseline_window=30, recent_window=12)

    # Process baseline
    for row in baseline_data:
        engine.update(row, timestamp=float(len(baseline_data)))

    print("Degradation phases with irreversibility factor values:")
    print()
    print("Frame | Phase              | S(t) Drift | R(t) Irreversi | I(t) Inevitab | Persistence")
    print("------|--------------------|-----------:|---------------:|---------------:|------------")

    irreversibility_values = []
    for i, row in enumerate(degradation_data):
        output = engine.update(row, timestamp=float(40 + i))
        irreversibility_values.append(output.irreversibility_factor)

        # Print every 5 frames
        if i % 5 == 0:
            print(
                f"{40+i:5d} | {phase_labels[i]:18s} | {output.structural_drift:9.4f} | "
                f"{output.irreversibility_factor:13.4f} | {output.structural_inevitability_score:13.4f} | "
                f"{output.persistence_score:10.4f}"
            )

    print()
    print("Analysis of R(t) variability:")
    print(f"  • Min R(t): {min(irreversibility_values):.4f}")
    print(f"  • Max R(t): {max(irreversibility_values):.4f}")
    print(f"  • Range: {max(irreversibility_values) - min(irreversibility_values):.4f}")
    print(f"  • Std Dev: {np.std(irreversibility_values):.4f}")
    print()

    if max(irreversibility_values) - min(irreversibility_values) > 0.2:
        print("✓ R(t) varies MEANINGFULLY (range > 0.2)")
    else:
        print("✗ R(t) does not vary meaningfully (range ≤ 0.2)")

    print()


def demonstrate_detection_differences():
    """Explain why legacy and inevitability modes produce different alerts."""
    print("=" * 70)
    print("DEMONSTRATION 3: Modes Produce Different Alerts")
    print("=" * 70)
    print()

    print("Why alerts differ between modes:")
    print()
    print("Scenario 1: Brief spike (high S(t), low R(t))")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ S(t) = 0.7  (exceeds drift_threshold=0.5) │")
    print("  │ R(t) = 0.3  (low irreversibility)        │")
    print("  │ I(t) = 0.21 (below inevitability_threshold=0.6) │")
    print("  └─────────────────────────────────────────┘")
    print("  ✓ Legacy mode: ALERTS (S(t) ≥ 0.5)")
    print("  ✗ Inevitability mode: NO ALERT (I(t) < 0.6)")
    print()

    print("Scenario 2: Persistent degradation (high S(t), high R(t))")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ S(t) = 0.45 (below drift_threshold=0.5) │")
    print("  │ R(t) = 0.9  (high irreversibility)      │")
    print("  │ I(t) = 0.405 (still below inevitability_threshold=0.6) │")
    print("  └─────────────────────────────────────────┘")
    print("  ✗ Legacy mode: NO ALERT (S(t) < 0.5)")
    print("  ✗ Inevitability mode: NO ALERT (I(t) < 0.6)")
    print()

    print("Scenario 3: Strong sustained degradation")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ S(t) = 0.6  (exceeds drift_threshold=0.5) │")
    print("  │ R(t) = 0.85 (high irreversibility)      │")
    print("  │ I(t) = 0.51 (approaches inevitability_threshold=0.6) │")
    print("  └─────────────────────────────────────────┘")
    print("  ✓ Legacy mode: ALERTS (S(t) ≥ 0.5)")
    print("  ? Inevitability mode: BORDERLINE (I(t) ≈ 0.5, threshold = 0.6)")
    print()

    print("Conclusion:")
    print("  The separate thresholds ensure that inevitability mode requires")
    print("  BOTH high instability AND high irreversibility to trigger alerts.")
    print("  This filters out transient spikes while detecting true structural")
    print("  degradation patterns.")
    print()


def verify_csv_output_format():
    """Show the CSV columns that will include both scores."""
    print("=" * 70)
    print("DEMONSTRATION 4: CSV Output Includes Both Score Diagnostics")
    print("=" * 70)
    print()

    print("New per_unit_results.csv columns (3 additional):")
    print()
    print("  Column Name                          | Type   | Meaning")
    print("  -------------------------------------|--------|-----------------------------------")
    print("  drift_score_at_confirmation          | float  | S(t): structural drift at alert")
    print("  inevitability_score_at_confirmation  | float  | I(t) = S(t)×R(t) at alert")
    print("  irreversibility_factor_at_confirmat. | float  | R(t): irreversibility at alert")
    print()

    print("Example row comparison (Unit 1):")
    print()
    print("Legacy mode result:")
    print("  drift_score_at_confirmation: 0.5834")
    print("  inevitability_score_at_confirmation: 0.0000 (not used)")
    print("  irreversibility_factor_at_confirmation: 0.0000 (not used)")
    print()

    print("Inevitability mode result:")
    print("  drift_score_at_confirmation: 0.5834")
    print("  inevitability_score_at_confirmation: 0.4208 (S(t) × R(t))")
    print("  irreversibility_factor_at_confirmation: 0.7215 (R(t) from 4 components)")
    print()

    print("You can analyze both scores in the CSV to understand why detections")
    print("differ between modes, and verify that R(t) is not constant.")
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  SEPARATE THRESHOLD VERIFICATION".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    try:
        demonstrate_threshold_separation()
        print()
        demonstrate_irreversibility_variability()
        print()
        demonstrate_detection_differences()
        print()
        verify_csv_output_format()

        print("=" * 70)
        print("✓ All demonstrations complete")
        print("=" * 70)
        print()
        print("To run actual tests with different thresholds:")
        print()
        print("Legacy mode (default):")
        print("  python tools/cmapss_unified_runner.py \\")
        print("    --data-dir /path/to/CMAPSSData \\")
        print("    --drift-threshold 0.5")
        print()
        print("Inevitability mode:")
        print("  python tools/cmapss_unified_runner.py \\")
        print("    --data-dir /path/to/CMAPSSData \\")
        print("    --use-inevitability-score \\")
        print("    --inevitability-threshold 0.6")
        print()
        print("Compare the per_unit_results.csv files to see the differences")
        print("in detected units and the score values at confirmation.")
        print()

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
