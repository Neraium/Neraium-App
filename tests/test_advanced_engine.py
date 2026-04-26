"""Integration tests for AdvancedSIIEngine."""

import numpy as np
import pytest
from neraium_core.sii_engine_advanced import (
    AdvancedSIIEngine,
    AdvancedSIIOutput,
    DegradationMode,
)


class TestAdvancedSIIEngine:
    """Test AdvancedSIIEngine functionality."""

    def test_engine_instantiation(self):
        """Test engine can be created."""
        engine = AdvancedSIIEngine(
            baseline_window=50,
            recent_window=12,
            system_type="generic",
        )
        assert engine.baseline_window == 50
        assert engine.system_type == "generic"

    def test_warmup_phase(self):
        """Test warmup phase produces zero instability."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)  # 21 sensors
            output = engine.update(x_t, float(cycle))

            assert output.regime == "WARMUP"
            assert output.instability_score == 0.0
            assert isinstance(output, AdvancedSIIOutput)

    def test_post_warmup_computation(self):
        """Test advanced metrics computed after warmup."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup: metrics should be computed
        for cycle in range(51, 100):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

            assert output.regime != "WARMUP"
            # Check all advanced metrics are present
            assert hasattr(output, "drift_fast")
            assert hasattr(output, "drift_medium")
            assert hasattr(output, "drift_slow")
            assert hasattr(output, "novelty_score")
            assert hasattr(output, "degradation_mode")
            assert hasattr(output, "ensemble_agreement")
            assert hasattr(output, "top_sensors")
            assert isinstance(output.degradation_mode, DegradationMode)

    def test_novelty_detection(self):
        """Test novelty score computation."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup with normal data
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup with normal data - novelty should be low
        normal_novelties = []
        for cycle in range(51, 70):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))
            normal_novelties.append(output.novelty_score)

        # Inject outliers
        outlier_novelties = []
        for cycle in range(70, 90):
            x_t = np.random.normal(5, 1, 21)  # Shifted mean
            output = engine.update(x_t, float(cycle))
            outlier_novelties.append(output.novelty_score)

        avg_normal = np.mean(normal_novelties)
        avg_outlier = np.mean(outlier_novelties)

        # Outliers should have higher novelty
        assert avg_outlier >= avg_normal

    def test_multiscale_drift(self):
        """Test multi-scale drift computation."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup with degradation trend
        for cycle in range(51, 150):
            # Gradual degradation
            x_t = np.random.normal(0.02 * (cycle - 50), 1, 21)
            output = engine.update(x_t, float(cycle))

            # All scales should be non-negative
            assert output.drift_fast >= 0.0
            assert output.drift_medium >= 0.0
            assert output.drift_slow >= 0.0

    def test_sensor_diagnostics(self):
        """Test top sensors output."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup
        for cycle in range(51, 100):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Should have sensor diagnostics
        assert isinstance(output.top_sensors, list)
        assert len(output.top_sensors) > 0  # Should have at least some sensors

        if len(output.top_sensors) > 0:
            sensor = output.top_sensors[0]
            assert hasattr(sensor, "sensor_id")
            assert hasattr(sensor, "contribution_to_instability")
            assert hasattr(sensor, "health_score")

    def test_ensemble_agreement(self):
        """Test ensemble agreement computation."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup
        for cycle in range(51, 100):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

            # Ensemble agreement should be between 0 and 1
            assert 0.0 <= output.ensemble_agreement <= 1.0

    def test_rul_estimation(self):
        """Test RUL estimation."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup with degradation
        rul_available = False
        for cycle in range(51, 150):
            x_t = np.random.normal(0.02 * (cycle - 50), 1, 21)
            output = engine.update(x_t, float(cycle))

            if output.rul is not None:
                rul_available = True
                assert output.rul.median_cycles > 0
                assert output.rul.p10_cycles <= output.rul.median_cycles
                assert output.rul.median_cycles <= output.rul.p90_cycles
                assert 0.0 <= output.rul.confidence <= 1.0

        # Should have generated RUL estimate at some point
        assert rul_available

    def test_degradation_mode_classification(self):
        """Test degradation mode is classified."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup
        for cycle in range(1, 51):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Post-warmup
        for cycle in range(51, 100):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

            assert isinstance(output.degradation_mode, DegradationMode)
            assert output.degradation_mode in DegradationMode

    def test_output_serialization(self):
        """Test AdvancedSIIOutput can be converted to dict."""
        engine = AdvancedSIIEngine(baseline_window=50, recent_window=12)
        np.random.seed(42)

        # Warmup and post-warmup
        for cycle in range(1, 100):
            x_t = np.random.normal(0, 1, 21)
            output = engine.update(x_t, float(cycle))

        # Convert to dict (should work without errors)
        output_dict = output.to_dict()
        assert isinstance(output_dict, dict)
        assert "instability_score" in output_dict
        assert "novelty_score" in output_dict
        assert "degradation_mode" in output_dict

    def test_system_type_thresholds(self):
        """Test different system types have different thresholds."""
        engine_generic = AdvancedSIIEngine(system_type="generic")
        engine_bearing = AdvancedSIIEngine(system_type="bearing")
        engine_critical = AdvancedSIIEngine(system_type="critical_system")

        assert engine_generic.thresholds != engine_bearing.thresholds
        assert engine_bearing.thresholds != engine_critical.thresholds

        for system_type in ["pump", "bearing", "compressor", "motor", "precision_machine", "critical_system", "generic"]:
            engine = AdvancedSIIEngine(system_type=system_type)
            assert "TRANSITION" in engine.thresholds
            assert "UNSTABLE" in engine.thresholds
            assert "LOCK_IN" in engine.thresholds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
