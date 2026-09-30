"""End-to-end pipeline integration test."""
import json
import pandas as pd
from app.data import generate_data, validate_data, split_data
from app.model import fit_models, anomaly_scores
from app.settings import FEATURES


def test_full_pipeline_run():
    # 1. Generate full dataset covering all temporal partitions
    df, incidents = generate_data()
    assert len(df) > 0
    assert len(incidents) > 0
    
    # 2. Validate
    validate_data(df)
    
    # 3. Split
    train, val, test = split_data(df)
    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0
    assert train["is_anomaly"].sum() == 0

    # 4. Fit
    bundle = fit_models(train)
    assert bundle["forest"] is not None
    
    # 5. Score
    scores = anomaly_scores(bundle, test)
    assert len(scores) == len(test)
