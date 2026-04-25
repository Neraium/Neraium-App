#!/usr/bin/env python3
"""Simple production example for the Neraium Structural Engine.

This example demonstrates how to use the engine in production:
1. Create engine with configuration
2. Feed frames one at a time
3. Collect and use results

Run with:
    python examples/production_example.py
"""

import json
from datetime import datetime, timedelta

from neraium_core.engine.production import ProductionEngine, InputFrame
from neraium_core.engine.config import ProductionEngineConfig, ProductionLoggingConfig
from neraium_core.engine.logging_setup import setup_logging


def main():
    """Run production example."""
    # Setup logging
    logging_config = ProductionLoggingConfig(level="INFO")
    setup_logging(logging_config)

    # Create engine with defaults (or from env vars)
    config = ProductionEngineConfig()
    engine = ProductionEngine(config=config, logging_config=logging_config)

    print("=" * 70)
    print("Neraium Structural Engine - Production Example")
    print("=" * 70)
    print()

    # Simulate streaming sensor data
    unit_id = "turbine-001"
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    num_frames = 50

    print(f"Simulating {num_frames} frames of sensor data for unit: {unit_id}")
    print()

    results_log = []

    for i in range(num_frames):
        # Create synthetic sensor data
        timestamp = (base_time + timedelta(seconds=i * 60)).timestamp()

        # Simple synthetic data: normal with increasing noise after frame 30
        sensors = {
            "vibration": 0.5 + (0.1 * (i % 10)) + (0.3 if i > 30 else 0),
            "temperature": 65.0 + (i % 5) + (5.0 if i > 30 else 0),
            "pressure": 100.0 - (i % 3) + (10.0 if i > 30 else 0),
        }

        # Create frame
        frame = InputFrame(
            timestamp=timestamp,
            unit_id=unit_id,
            sensors=sensors,
        )

        # Process frame
        try:
            result = engine.process_frame(frame)

            # Log result
            results_log.append(result.to_dict())

            # Print summary
            if (i + 1) % 10 == 0 or i == 0:
                print(
                    f"Frame {i+1:3d}: "
                    f"state={result.state:6s} "
                    f"drift={result.drift_score:.3f} "
                    f"health={result.health_percentage:3d}% "
                    f"sensors={result.sensor_count}"
                )

        except Exception as e:
            print(f"Error processing frame {i}: {e}")
            raise

    print()
    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)
    print()

    # Summary statistics
    states = [r["state"] for r in results_log]
    state_counts = {s: states.count(s) for s in {"STABLE", "WATCH", "ALERT"}}

    print("Summary Statistics:")
    print(f"  Total frames processed: {len(results_log)}")
    print("  State distribution:")
    for state, count in sorted(state_counts.items()):
        pct = (count / len(results_log)) * 100
        print(f"    - {state}: {count} ({pct:.1f}%)")

    avg_drift = sum(r["drift_score"] for r in results_log) / len(results_log)
    avg_health = sum(r["health_percentage"] for r in results_log) / len(results_log)
    print(f"  Average drift score: {avg_drift:.3f}")
    print(f"  Average health: {avg_health:.1f}%")

    print()
    print("Engine diagnostics:")
    diag = engine.get_diagnostics()
    print(f"  Units tracked: {diag['units_tracked']}")
    print(f"  Frames in engine buffer: {diag['engine_frames_stored']}")

    print()
    print("Sample output (last 3 frames):")
    print()
    for result in results_log[-3:]:
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
