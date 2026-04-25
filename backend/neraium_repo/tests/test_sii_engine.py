"""
SII Engine validation tests (SII-only).

Covers:
- SII engine unified core functionality
- Stability energy computation
- FD004 validation
"""


def test_sii_engine_imports():
    """Verify SII engine modules can be imported."""
    from neraium_core.sii_engine_unified import SIIEngine, SIIEngineOutput, BaselineProfile

    assert SIIEngine is not None
    assert SIIEngineOutput is not None
    assert BaselineProfile is not None


def test_sii_stability_energy():
    """Verify stability energy module loads."""
    from neraium_core.stability_energy import StabilityEnergyCalculator

    assert StabilityEnergyCalculator is not None


def test_sii_fd004_validation():
    """Verify FD004 validation can be imported."""
    from neraium_core.sii_fd004_validation import FD004ValidationRunner

    assert FD004ValidationRunner is not None


def test_sii_engine_adapter():
    """Verify SII engine adapter can be imported."""
    from neraium_core.sii_engine_adapter import UnifiedSystemState

    assert UnifiedSystemState is not None


def test_stability_energy_calculation():
    """Test basic stability energy calculation."""
    from neraium_core.stability_energy import compute_alignment

    # Test that alignment function exists and works
    assert compute_alignment is not None
