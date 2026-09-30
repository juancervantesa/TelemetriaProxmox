"""Modelo de detección de anomalías Isolation Forest y línea base de umbrales fijos de SIGeCAD."""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from app.settings import FEATURES, SEED, BASELINE_THRESHOLDS


def fit_models(train: pd.DataFrame) -> dict:
    """Entrena el estimador Isolation Forest exclusivamente con ventanas operacionales normales."""
    values = train[FEATURES]
    
    # Ajustar el estimador Isolation Forest
    forest = IsolationForest(
        n_estimators=200,
        max_samples=256,
        contamination="auto",
        random_state=SEED,
        n_jobs=-1
    )
    forest.fit(values)

    # Calcular estadísticas de escalado robusto (mediana y MAD) para la atribución de variables
    median = values.median().to_numpy()
    mad = np.median(np.abs(values.to_numpy() - median), axis=0)
    scale = np.maximum(1.4826 * mad, 1e-6)

    # Rangos de referencia a partir de la telemetría normal observada
    reference = {
        feature: {
            "min": float(values[feature].min()),
            "max": float(values[feature].max()),
            "p01": float(values[feature].quantile(0.01)),
            "p99": float(values[feature].quantile(0.99)),
            "median": float(values[feature].median()),
            "mean": float(values[feature].mean()),
            "std": float(values[feature].std()),
        }
        for feature in FEATURES
    }

    return {
        "forest": forest,
        "median": median,
        "scale": scale,
        "reference": reference,
        "baseline_thresholds": BASELINE_THRESHOLDS,
    }


def anomaly_scores(bundle: dict, data: pd.DataFrame) -> np.ndarray:
    """Calcula puntajes continuos de anomalía a partir de Isolation Forest.
    
    Invierte el score_samples de scikit-learn para que valores mayores representen mayor grado de anomalía.
    """
    return -bundle["forest"].score_samples(data[FEATURES])


def robust_distances(bundle: dict, data: pd.DataFrame) -> np.ndarray:
    """Calcula la desviación en unidades MAD (Desviación Absoluta respecto a la Mediana) por variable."""
    return np.abs((data[FEATURES].to_numpy() - bundle["median"]) / bundle["scale"])


def baseline_scores(bundle: dict, data: pd.DataFrame) -> np.ndarray:
    """Calcula el puntaje continuo de línea base basado en las proporciones de umbral fijo de SIGeCAD.
    
    Un puntaje >= 1.0 indica que al menos una métrica superó el umbral crítico.
    Un puntaje >= 0.85 indica que al menos una métrica superó el umbral de advertencia.
    """
    ratios = []
    crit_thresholds = bundle["baseline_thresholds"]["critical"]
    for feature, threshold in crit_thresholds.items():
        if feature in data.columns:
            ratios.append(data[feature].to_numpy() / threshold)
    if not ratios:
        return np.zeros(len(data))
    return np.max(np.array(ratios), axis=0)


def baseline_rules_decision(bundle: dict, values: dict) -> dict:
    """Evalúa la lógica estricta de advertencia/crítico ante umbrales fijos para una lectura individual."""
    warnings = []
    criticals = []
    
    warn_cfg = bundle["baseline_thresholds"]["warning"]
    crit_cfg = bundle["baseline_thresholds"]["critical"]

    for feature, crit_val in crit_cfg.items():
        val = float(values.get(feature, 0.0))
        warn_val = warn_cfg.get(feature, crit_val * 0.85)
        if val >= crit_val:
            criticals.append({"feature": feature, "value": val, "threshold": crit_val, "severity": "critical"})
        elif val >= warn_val:
            warnings.append({"feature": feature, "value": val, "threshold": warn_val, "severity": "warning"})

    is_alert = len(criticals) > 0 or len(warnings) > 0
    status = "critical" if criticals else ("warning" if warnings else "normal")

    return {
        "alert": is_alert,
        "status": status,
        "critical_violations": criticals,
        "warning_violations": warnings
    }
