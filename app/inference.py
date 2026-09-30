"""Inference module for scoring single telemetry windows and comparing against SIGeCAD baseline."""
import numpy as np
import pandas as pd
from app.model import anomaly_scores, baseline_scores, robust_distances, baseline_rules_decision
from app.settings import FEATURES, TELEMETRY_FEATURES


def diagnose_anomaly_cause(indicators: list[dict]) -> str:
    """Diagnoses the most probable operational incident root cause based on feature deviations."""
    dev_map = {ind["feature"]: ind["robust_distance"] for ind in indicators}
    
    # Priority diagnostic heuristics
    if dev_map.get("memory_pct_trend", 0.0) >= 3.0 and dev_map.get("memory_pct_max", 0.0) >= 2.0:
        return "Patrón característico de Fuga de Memoria Progresiva (Memory Leak)"
    if dev_map.get("iowait_max", 0.0) >= 3.0 or dev_map.get("iowait_mean", 0.0) >= 3.0:
        return "Contención severa de almacenamiento o fallo en punto de montaje (Storage Stall)"
    if dev_map.get("temp_max_c", 0.0) >= 3.0 or dev_map.get("temp_max_c", 0.0) >= 75.0:
        return "Sobrecalentamiento térmico en chasis / procesador de nodo físico"
    if dev_map.get("cpu_std", 0.0) >= 3.0 and dev_map.get("cpu_max", 0.0) >= 2.5:
        return "Inestabilidad severa de CPU previa a degradación o caída de proceso VM"
    if dev_map.get("net_io_mb_s", 0.0) >= 3.0:
        return "Anomalía de tráfico en interfaz de red (posible inundación o ráfaga inusual)"
    
    # Highest deviation fallback
    highest_dev = max(indicators, key=lambda x: x["robust_distance"])
    return f"Desviación multivariada anómala liderada por: {highest_dev['label']}"


def inspect_reading(bundle: dict, values: dict) -> dict:
    """Analyzes an aggregated 10-minute telemetry window using both Isolation Forest and Baseline."""
    data = pd.DataFrame([values], columns=FEATURES)
    
    # Model scores
    model_score = float(anomaly_scores(bundle, data)[0])
    model_thresh = float(bundle["threshold"])
    model_alert = bool(model_score >= model_thresh)

    # Baseline scores & rules
    base_score = float(baseline_scores(bundle, data)[0])
    base_thresh = float(bundle["baseline_threshold"])
    base_alert = bool(base_score >= base_thresh)
    base_decision = baseline_rules_decision(bundle, values)

    # Feature attribution / deviations
    distances = robust_distances(bundle, data)[0]
    indicators = []
    
    for idx, feature in enumerate(FEATURES):
        ref = bundle["reference"][feature]
        val = float(values[feature])
        dist = float(distances[idx])
        meta = TELEMETRY_FEATURES[feature]

        indicators.append({
            "feature": feature,
            "label": meta["label"],
            "unit": meta["unit"],
            "value": round(val, 2),
            "reference": {
                "min": round(ref["min"], 2),
                "max": round(ref["max"], 2),
                "median": round(ref["median"], 2),
                "p01": round(ref["p01"], 2),
                "p99": round(ref["p99"], 2)
            },
            "robust_distance": round(dist, 2),
            "outside_observed_range": bool(val < ref["p01"] or val > ref["p99"])
        })

    # Sort indicators by highest anomaly deviation
    indicators.sort(key=lambda x: x["robust_distance"], reverse=True)

    diagnosis = diagnose_anomaly_cause(indicators) if (model_alert or base_alert) else "Comportamiento dentro del rango operativo normal"

    return {
        "score": round(model_score, 4),
        "threshold": round(model_thresh, 4),
        "alert": model_alert,
        "score_percentage": round(min(max((model_score - 0.3) / 0.4 * 100.0, 0.0), 100.0), 1),
        "baseline": {
            "score": round(base_score, 4),
            "threshold": round(base_thresh, 4),
            "alert": base_alert,
            "decision": base_decision
        },
        "diagnosis": diagnosis,
        "indicators": indicators,
        "resource_id": values.get("resource_id", "node:dl380-01"),
        "version": bundle["version"],
        "model_name": "Isolation Forest (Multivariado)"
    }
