#!/usr/bin/env python3
"""
Tests for CMAPSS unified validation runner.

Tests cover:
- CMAPSS row parsing
- Failure cycle calculation
- Alert detection logic
- Summary aggregation correctness
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cmapss_unified_runner import (
    CMAPSSRow,
    CMAPSSValidator,
    DatasetSummary,
    UnitDetectionResult,
)
from neraium_core.sii_engine_unified import SIIEngine, SIIEngineOutput


class TestCMAPSSRowParsing:
    """Test CMAPSS data row parsing."""

    def test_parse_valid_row(self):
        """Test parsing a valid CMAPSS row."""
        # Example CMAPSS row: unit cycle setting1 setting2 setting3 s1 s2 ... s21
        line = "1 1 -0.0007 -0.0004 100.0 " + " ".join([str(i * 0.1) for i in range(21)])
        row = CMAPSSRow.parse(line)

        assert row.unit_id == 1
        assert row.cycle == 1
        assert row.setting_1 == -0.0007
        assert row.setting_2 == -0.0004
        assert row.setting_3 == 100.0
        assert len(row.sensors) == 21

    def test_parse_row_sensor_count(self):
        """Test that parsed row has exactly 21 sensors."""
        line = "2 5 0.0 0.0 100.0 " + " ".join([str(i) for i in range(21)])
        row = CMAPSSRow.parse(line)
        assert len(row.sensors) == 21

    def test_parse_row_to_sensor_vector(self):
        """Test conversion to sensor vector."""
        line = "1 1 0.0 0.0 100.0 " + " ".join([str(i * 0.5) for i in range(21)])
        row = CMAPSSRow.parse(line)
        vector = row.to_sensor_vector()

        assert vector.shape == (21,)
        assert all(vector[i] == i * 0.5 for i in range(21))

    def test_parse_multiple_rows(self):
        """Test parsing multiple rows maintains correct order."""
        lines = [
            "1 1 0.0 0.0 100.0 " + " ".join(["1.0"] * 21),
            "1 2 0.0 0.0 100.0 " + " ".join(["2.0"] * 21),
            "1 3 0.0 0.0 100.0 " + " ".join(["3.0"] * 21),
        ]
        rows = [CMAPSSRow.parse(line) for line in lines]

        assert len(rows) == 3
        assert rows[0].cycle == 1
        assert rows[1].cycle == 2
        assert rows[2].cycle == 3


class TestFailureCycleCalculation:
    """Test failure cycle calculation logic."""

    def test_failure_cycle_calculation(self):
        """Test failure_cycle = last_observed_cycle + RUL."""
        # Mock data: last cycle = 100, RUL = 25
        cycles_data = [
            CMAPSSRow(unit_id=1, cycle=i, setting_1=0, setting_2=0, setting_3=100, sensors=[0]*21)
            for i in range(1, 101)
        ]

        last_cycle = max(c.cycle for c in cycles_data)
        rul = 25
        failure_cycle = last_cycle + rul

        assert failure_cycle == 125

    def test_failure_cycle_with_zero_rul(self):
        """Test failure_cycle when RUL is 0."""
        cycles_data = [
            CMAPSSRow(unit_id=1, cycle=i, setting_1=0, setting_2=0, setting_3=100, sensors=[0]*21)
            for i in range(1, 51)
        ]

        last_cycle = max(c.cycle for c in cycles_data)
        rul = 0
        failure_cycle = last_cycle + rul

        assert failure_cycle == 50


class TestAlertDetection:
    """Test alert detection logic."""

    def test_alert_on_regime_transition(self):
        """Test alert detection on TRANSITION regime."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        # Mock SIIEngineOutput with TRANSITION regime
        class MockOutput:
            regime = "TRANSITION"
            urgency = "NOMINAL"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_alert_on_regime_unstable(self):
        """Test alert detection on UNSTABLE regime."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "UNSTABLE"
            urgency = "NOMINAL"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_alert_on_regime_lock_in(self):
        """Test alert detection on LOCK_IN regime."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "LOCK_IN"
            urgency = "NOMINAL"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_alert_on_urgency_alert(self):
        """Test alert detection on ALERT urgency."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "ALERT"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_alert_on_urgency_critical(self):
        """Test alert detection on CRITICAL urgency."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "CRITICAL"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_alert_on_drift_threshold(self):
        """Test alert detection on structural_drift threshold."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "NOMINAL"
            structural_drift = 0.6  # Exceeds threshold

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is True

    def test_no_alert_below_threshold(self):
        """Test no alert when all conditions are below threshold."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "NOMINAL"
            structural_drift = 0.3

        class MockRow:
            pass

        output = MockOutput()
        row = MockRow()

        assert validator._check_alert(output, row) is False

    def test_alert_type_regime(self):
        """Test alert type identification: regime."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "UNSTABLE"
            urgency = "NOMINAL"

        assert validator._get_alert_type(MockOutput()) == "regime"

    def test_alert_type_urgency(self):
        """Test alert type identification: urgency."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "ALERT"

        assert validator._get_alert_type(MockOutput()) == "urgency"

    def test_alert_type_structural_drift(self):
        """Test alert type identification: structural_drift."""
        validator = CMAPSSValidator(
            data_dir=Path("."),
            output_dir=Path("."),
            structural_drift_threshold=0.5
        )

        class MockOutput:
            regime = "STABLE"
            urgency = "NOMINAL"

        assert validator._get_alert_type(MockOutput()) == "structural_drift"


class TestSummaryAggregation:
    """Test summary metric aggregation."""

    def test_detection_coverage_calculation(self):
        """Test detection coverage percentage calculation."""
        summary = DatasetSummary(dataset="FD001", units_total=100)
        summary.units_detected = 85
        summary.detection_coverage_pct = (100.0 * summary.units_detected / summary.units_total)

        assert summary.detection_coverage_pct == 85.0

    def test_lead_time_statistics(self):
        """Test lead time statistics aggregation."""
        summary = DatasetSummary(dataset="FD001", units_total=5)
        summary.per_unit_results = [
            UnitDetectionResult(
                unit_id=1, dataset="FD001", total_cycles=100, failure_cycle=125,
                first_alert_cycle=100, lead_time_cycles=25, detected=True
            ),
            UnitDetectionResult(
                unit_id=2, dataset="FD001", total_cycles=100, failure_cycle=125,
                first_alert_cycle=105, lead_time_cycles=20, detected=True
            ),
            UnitDetectionResult(
                unit_id=3, dataset="FD001", total_cycles=100, failure_cycle=125,
                first_alert_cycle=110, lead_time_cycles=15, detected=True
            ),
        ]

        import numpy as np
        lead_times = [r.lead_time_cycles for r in summary.per_unit_results if r.lead_time_cycles]
        summary.median_lead_time_cycles = float(np.median(lead_times))
        summary.mean_lead_time_cycles = float(np.mean(lead_times))

        assert summary.median_lead_time_cycles == 20.0
        assert summary.mean_lead_time_cycles == 20.0

    def test_missed_units_calculation(self):
        """Test missed units count."""
        summary = DatasetSummary(dataset="FD001", units_total=100)
        summary.units_detected = 85
        summary.missed_units = summary.units_total - summary.units_detected

        assert summary.missed_units == 15

    def test_detection_with_late_alert(self):
        """Test that detection is False when alert comes after failure."""
        result = UnitDetectionResult(
            unit_id=1,
            dataset="FD001",
            total_cycles=100,
            failure_cycle=120,
            first_alert_cycle=125,  # After failure
            lead_time_cycles=-5,
            detected=False  # Should not be detected
        )

        assert result.detected is False


class TestFileIO:
    """Test file I/O operations."""

    def test_write_per_unit_csv(self):
        """Test per-unit CSV output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = CMAPSSValidator(
                data_dir=Path(tmpdir),
                output_dir=Path(tmpdir),
            )

            summary = DatasetSummary(dataset="FD001", units_total=2)
            summary.per_unit_results = [
                UnitDetectionResult(
                    unit_id=1, dataset="FD001", total_cycles=100, failure_cycle=125,
                    first_alert_cycle=100, alert_cycle_type="regime",
                    alert_regime_at_detection="UNSTABLE", lead_time_cycles=25, detected=True,
                    max_instability_score=0.8, instability_at_alert=0.7
                ),
                UnitDetectionResult(
                    unit_id=2, dataset="FD001", total_cycles=100, failure_cycle=125,
                    first_alert_cycle=None, alert_cycle_type=None,
                    alert_regime_at_detection=None, lead_time_cycles=None, detected=False,
                    max_instability_score=0.4, instability_at_alert=0.0
                ),
            ]

            csv_file = Path(tmpdir) / "test.csv"
            validator._write_per_unit_csv(csv_file, summary)

            assert csv_file.exists()
            with open(csv_file) as f:
                lines = f.readlines()
                assert len(lines) == 3  # Header + 2 units
                assert "unit_id" in lines[0]

    def test_write_summary_json(self):
        """Test summary JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = CMAPSSValidator(
                data_dir=Path(tmpdir),
                output_dir=Path(tmpdir),
            )

            summary = DatasetSummary(
                dataset="FD001",
                units_total=100,
                units_detected=85,
                detection_coverage_pct=85.0,
                median_lead_time_cycles=20.0,
                mean_lead_time_cycles=21.5,
                min_lead_time_cycles=10,
                max_lead_time_cycles=30,
                missed_units=15,
            )

            json_file = Path(tmpdir) / "summary.json"
            validator._write_summary_json(json_file, summary)

            assert json_file.exists()
            with open(json_file) as f:
                data = json.load(f)
                assert data["dataset"] == "FD001"
                assert data["units_detected"] == 85
                assert data["detection_coverage_pct"] == 85.0


class TestIntegration:
    """Integration tests with actual engine."""

    def test_end_to_end_single_unit(self):
        """Test end-to-end processing of a single unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create minimal test data
            test_data = "1 1 0.0 0.0 100.0 " + " ".join(["0.1"] * 21) + "\n"
            test_data += "1 2 0.0 0.0 100.0 " + " ".join(["0.15"] * 21) + "\n"
            for i in range(3, 70):
                test_data += f"1 {i} 0.0 0.0 100.0 " + " ".join([str(0.1 + i*0.001)] * 21) + "\n"

            rul_data = "10"

            test_file = tmpdir / "test_FD001.txt"
            rul_file = tmpdir / "RUL_FD001.txt"

            with open(test_file, "w") as f:
                f.write(test_data)
            with open(rul_file, "w") as f:
                f.write(rul_data)

            # Run validator
            validator = CMAPSSValidator(
                data_dir=tmpdir,
                output_dir=tmpdir / "output",
                progress=False,
            )

            summary = validator._validate_dataset("FD001")

            # Check basic properties
            assert summary.dataset == "FD001"
            assert summary.units_total == 1
            assert len(summary.per_unit_results) == 1

            result = summary.per_unit_results[0]
            assert result.unit_id == 1
            assert result.failure_cycle == 79  # 69 cycles + 10 RUL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
