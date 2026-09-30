"""Prueba de integración del pipeline completo de extremo a extremo."""
import json
import pandas as pd
from app.data import generate_data, validate_data, split_data
from app.model import fit_models, anomaly_scores
from app.settings import FEATURES


def test_full_pipeline_run():
    # 1. Generar dataset completo abarcando todas las particiones temporales
    df, incidents = generate_data()
    assert len(df) > 0
    assert len(incidents) > 0
    
    # 2. Validar esquema y consistencia
    validate_data(df)
    
    # 3. Particionar temporalmente
    train, val, test = split_data(df)
    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0
    assert train["is_anomaly"].sum() == 0

    # 4. Ajustar modelo con datos normales
    bundle = fit_models(train)
    assert bundle["forest"] is not None
    
    # 5. Evaluar puntajes sobre el conjunto de prueba
    scores = anomaly_scores(bundle, test)
    assert len(scores) == len(test)
