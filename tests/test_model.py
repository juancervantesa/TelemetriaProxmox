"""Pruebas unitarias para el entrenamiento de Isolation Forest, evaluación de línea base y cálculo de F1 por eventos."""
import numpy as np
import pandas as pd
import pytest
from app.data import generate_data, split_data
from app.model import fit_models, anomaly_scores, baseline_scores, robust_distances
from app.evaluation import event_based_metrics, select_threshold, operating_metrics
from app.settings import FEATURES


@pytest.fixture(scope="module")
def dataset():
    df, incidents = generate_data(num_hours=168)  # Subconjunto de 7 días para pruebas rápidas
    return df, incidents


def test_model_training_and_scoring(dataset):
    df, _ = dataset
    normal_data = df[df["is_anomaly"] == 0]
    bundle = fit_models(normal_data)

    assert "forest" in bundle
    assert "median" in bundle
    assert "scale" in bundle
    assert len(bundle["median"]) == len(FEATURES)

    # Puntajes de muestras
    scores = anomaly_scores(bundle, df)
    assert len(scores) == len(df)
    assert np.isfinite(scores).all()

    # Distancias robustas
    distances = robust_distances(bundle, df)
    assert distances.shape == (len(df), len(FEATURES))


def test_baseline_scoring(dataset):
    df, _ = dataset
    bundle = fit_models(df[df["is_anomaly"] == 0])
    base_scores = baseline_scores(bundle, df)
    
    assert len(base_scores) == len(df)
    assert (base_scores >= 0.0).all()


def test_event_based_metrics_logic():
    """Verifica el emparejamiento por eventos y el cálculo de anticipación con incidentes sintéticos."""
    incidents = [
        {
            "incident_id": "INC-01",
            "resource_id": "node:dl380-01",
            "start_time": "2026-09-20T10:00:00",
            "end_time": "2026-09-20T11:00:00",
            "severity": "critical"
        }
    ]

    timestamps = pd.date_range("2026-09-20 09:00:00", periods=6, freq="30min")
    df = pd.DataFrame({
        "timestamp": [ts.isoformat() for ts in timestamps],
        "resource_id": ["node:dl380-01"] * 6,
        "is_anomaly": [0, 0, 1, 1, 0, 0]  # Índices 2 y 3 corresponden a 10:00 y 10:30
    })

    # Escenario A: Alerta disparada a las 09:30 (anticipación = 30 min antes del inicio del incidente)
    scores = np.array([0.2, 0.9, 0.8, 0.4, 0.1, 0.1])
    metrics = event_based_metrics(df, scores, threshold=0.7, incidents=incidents, lead_time_minutes=30)
    
    assert metrics["tp_events"] == 1
    assert metrics["fn_events"] == 0
    assert metrics["event_recall"] == 1.0
    assert metrics["avg_lead_time_minutes"] == 30.0


def test_threshold_selection_respects_budget():
    labels = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.15, 0.25, 0.18, 0.22, 0.19, 0.21, 0.85, 0.92])
    
    selected = select_threshold(labels, scores, false_alarm_budget=0.10)
    assert selected["false_positive_rate"] <= 0.10
    assert selected["recall"] == 1.0
