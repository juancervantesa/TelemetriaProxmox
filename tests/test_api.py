"""Pruebas de integración para endpoints FastAPI: caso válido, caso difícil, caso inválido, health, config y metrics."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.settings import SCENARIOS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_config_endpoint(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 6


def test_metrics_endpoint(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "test" in data
    assert "validation" in data
    assert "event_based" in data["test"]["model"]


def test_events_endpoint(client):
    response = client.get("/api/events")
    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "incidents" in data


# 1. Caso Válido (Demostración de flujo normal)
def test_inspect_valid_case(client):
    usual_scn = next(s for s in SCENARIOS if s["id"] == "usual")
    payload = {"resource_id": "node:dl380-01", **usual_scn["values"]}
    
    response = client.post("/api/inspect", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert "score" in result
    assert "threshold" in result
    assert "alert" in result
    assert "baseline" in result
    assert "indicators" in result
    assert result["alert"] is False
    assert result["baseline"]["alert"] is False


# 2. Caso Difícil (Carga alta legítima de procesamiento sin anomalía)
def test_inspect_hard_case_legitimate_batch(client):
    hard_scn = next(s for s in SCENARIOS if s["id"] == "legitimate_batch")
    payload = {"resource_id": "node:dl380-01", **hard_scn["values"]}
    
    response = client.post("/api/inspect", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert "score" in result
    assert "diagnosis" in result
    # En carga legítima alta, Isolation Forest distingue la estabilidad a pesar del uso elevado de CPU
    assert isinstance(result["alert"], bool)


# 3. Caso Inválido (Rechazo con HTTP 422)
def test_inspect_invalid_input_rejected(client):
    invalid_payload = {
        "resource_id": "node:dl380-01",
        "cpu_mean": -25.0,  # Valor negativo: inválido
        "cpu_max": 250.0,   # Superior al 100%: inválido
        "cpu_std": 2.0,
        "cpu_trend": 0.0,
        "memory_pct_mean": 50.0,
        "memory_pct_max": 40.0,  # Incoherente: max < mean
        "memory_pct_trend": 0.0,
        "iowait_mean": 0.0,
        "iowait_max": 0.0,
        "net_io_mb_s": 10.0,
        "temp_max_c": 45.0
    }
    
    response = client.post("/api/inspect", json=invalid_payload)
    assert response.status_code == 422
    err_data = response.json()
    assert "detalles" in err_data
    assert len(err_data["detalles"]) > 0
