"""Unit tests for input schema validation, boundary enforcement, and error handling."""
import pytest
from pydantic import ValidationError
from app.schemas import WindowInput
from app.settings import SCENARIOS


def test_valid_scenario_inputs():
    """Verify that all predefined operational scenarios comply with the schema."""
    for scn in SCENARIOS:
        window = WindowInput(**scn["values"])
        assert window.cpu_mean >= 0.0
        assert window.cpu_max >= window.cpu_mean
        assert window.memory_pct_max >= window.memory_pct_mean


def test_invalid_negative_cpu():
    """Verify rejection of physically impossible negative CPU metrics."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_mean"] = -5.0
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "greater than or equal to 0" in str(exc.value)


def test_invalid_cpu_exceeds_100():
    """Verify rejection of CPU usage exceeding 100%."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_max"] = 150.0
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "less than or equal to 100" in str(exc.value)


def test_invalid_logical_inconsistency():
    """Verify rejection when peak value is strictly smaller than average value."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_mean"] = 60.0
    valid_data["cpu_max"] = 40.0  # Inconsistent: max < mean
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "cannot be lower than cpu_mean" in str(exc.value)


def test_invalid_non_numeric():
    """Verify rejection of non-numeric or string values."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["temp_max_c"] = "caliente"
    with pytest.raises(ValidationError):
        WindowInput(**valid_data)
