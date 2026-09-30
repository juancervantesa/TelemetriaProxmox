"""Pruebas unitarias para la validación de esquemas de entrada, límites y manejo de errores."""
import pytest
from pydantic import ValidationError
from app.schemas import WindowInput
from app.settings import SCENARIOS


def test_valid_scenario_inputs():
    """Verifica que todos los escenarios operacionales predefinidos cumplan estrictamente el esquema."""
    for scn in SCENARIOS:
        window = WindowInput(**scn["values"])
        assert window.cpu_mean >= 0.0
        assert window.cpu_max >= window.cpu_mean
        assert window.memory_pct_max >= window.memory_pct_mean


def test_invalid_negative_cpu():
    """Verifica el rechazo ante valores negativos físicamente imposibles de CPU."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_mean"] = -5.0
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "greater than or equal to 0" in str(exc.value)


def test_invalid_cpu_exceeds_100():
    """Verifica el rechazo de porcentajes de CPU superiores al 100%."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_max"] = 150.0
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "less than or equal to 100" in str(exc.value)


def test_invalid_logical_inconsistency():
    """Verifica el rechazo cuando el valor pico es estrictamente menor que el promedio."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["cpu_mean"] = 60.0
    valid_data["cpu_max"] = 40.0  # Inconsistent: max < mean
    with pytest.raises(ValidationError) as exc:
        WindowInput(**valid_data)
    assert "cannot be lower than cpu_mean" in str(exc.value)


def test_invalid_non_numeric():
    """Verifica el rechazo ante tipos de datos no numéricos o cadenas de texto."""
    valid_data = SCENARIOS[0]["values"].copy()
    valid_data["temp_max_c"] = "caliente"
    with pytest.raises(ValidationError):
        WindowInput(**valid_data)
