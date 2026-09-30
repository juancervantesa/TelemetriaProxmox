"""Métricas de evaluación: F1 por eventos, anticipación temporal (lead time), métricas puntuales y selección de umbrales en validación."""
import numpy as np
import pandas as pd
from datetime import timedelta
from sklearn.metrics import average_precision_score, confusion_matrix, precision_score, recall_score, f1_score


def operating_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    """Calcula la matriz de confusión puntual y las métricas de clasificación por ventana."""
    labels = np.asarray(labels, dtype=int)
    predictions = np.asarray(scores) >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    
    precision = float(precision_score(labels, predictions, zero_division=0))
    recall = float(recall_score(labels, predictions, zero_division=0))
    f1 = float(f1_score(labels, predictions, zero_division=0))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr,
        "alerts": int(predictions.sum()),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def event_based_metrics(
    data: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
    incidents: list[dict],
    lead_time_minutes: int = 30
) -> dict:
    """Calcula F1 por eventos, retardo de detección y tiempo de anticipación (lead time).
    
    Un evento se considera Verdadero Positivo (TP) si se dispara al menos una alerta
    en el recurso afectado entre (inicio_incidente - lead_time) y fin_incidente.
    """
    df = data.copy()
    df["score"] = scores
    df["alert"] = (scores >= threshold).astype(int)
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"])

    data_min_time = df["timestamp_dt"].min()
    data_max_time = df["timestamp_dt"].max()

    # Filtrar incidentes comprendidos en el intervalo temporal de este conjunto
    eval_incidents = []
    for inc in incidents:
        t_start = pd.Timestamp(inc["start_time"])
        t_end = pd.Timestamp(inc["end_time"])
        if t_start >= data_min_time and t_start <= data_max_time:
            eval_incidents.append(inc)

    tp_events = 0
    fn_events = 0
    incident_details = []
    alerted_incident_windows = set()

    for inc in eval_incidents:
        res_id = inc["resource_id"]
        t_start = pd.Timestamp(inc["start_time"])
        t_end = pd.Timestamp(inc["end_time"])
        t_lead = t_start - timedelta(minutes=lead_time_minutes)

        # Ventanas asociadas a este incidente en el recurso específico
        mask = (
            (df["resource_id"] == res_id) &
            (df["timestamp_dt"] >= t_lead) &
            (df["timestamp_dt"] <= t_end)
        )
        matching_windows = df[mask]
        matching_indices = set(matching_windows.index)
        alerted_incident_windows.update(matching_indices)

        alerts_fired = matching_windows[matching_windows["alert"] == 1]

        if not alerts_fired.empty:
            tp_events += 1
            first_alert_time = alerts_fired["timestamp_dt"].min()
            lead_time = (t_start - first_alert_time).total_seconds() / 60.0
            incident_details.append({
                "incident_id": inc["incident_id"],
                "resource_id": res_id,
                "detected": True,
                "first_alert": first_alert_time.isoformat(),
                "start_time": inc["start_time"],
                "lead_time_minutes": round(lead_time, 1),
                "severity": inc.get("severity", "critical")
            })
        else:
            fn_events += 1
            incident_details.append({
                "incident_id": inc["incident_id"],
                "resource_id": res_id,
                "detected": False,
                "first_alert": None,
                "start_time": inc["start_time"],
                "lead_time_minutes": 0.0,
                "severity": inc.get("severity", "critical")
            })

    # Agrupar alertas falsas fuera de ventanas de incidentes en eventos de Falsos Positivos
    non_incident_alerts = df[(df["alert"] == 1) & (~df.index.isin(alerted_incident_windows))]
    
    # Agrupar falsas alarmas contiguas por recurso en eventos FP diferenciados
    fp_events = 0
    for res_id, group in non_incident_alerts.groupby("resource_id"):
        sorted_ts = group["timestamp_dt"].sort_values()
        clusters = (sorted_ts.diff() > timedelta(minutes=30)).cumsum()
        fp_events += clusters.nunique() if not sorted_ts.empty else 0

    total_actual_events = tp_events + fn_events
    event_precision = float(tp_events / (tp_events + fp_events)) if (tp_events + fp_events) > 0 else 0.0
    event_recall = float(tp_events / total_actual_events) if total_actual_events > 0 else 0.0
    event_f1 = (
        float(2 * event_precision * event_recall / (event_precision + event_recall))
        if (event_precision + event_recall) > 0 else 0.0
    )

    lead_times = [d["lead_time_minutes"] for d in incident_details if d["detected"]]
    avg_lead_time = float(np.mean(lead_times)) if lead_times else 0.0

    return {
        "event_precision": round(event_precision, 4),
        "event_recall": round(event_recall, 4),
        "event_f1": round(event_f1, 4),
        "tp_events": tp_events,
        "fn_events": fn_events,
        "fp_events": fp_events,
        "total_incidents": total_actual_events,
        "avg_lead_time_minutes": round(avg_lead_time, 1),
        "incident_details": incident_details
    }


def select_threshold(labels: np.ndarray, scores: np.ndarray, false_alarm_budget: float) -> dict:
    """Selecciona el umbral operacional en validación maximizando el recall sujeto al presupuesto de FPR."""
    labels, scores = np.asarray(labels, dtype=int), np.asarray(scores, dtype=float)
    if set(labels) != {0, 1} or not np.isfinite(scores).all():
        raise ValueError("Threshold selection requires binary labels and finite scores.")
    
    candidates = np.append(np.unique(scores), np.nextafter(scores.max(), np.inf))
    feasible = []
    
    for threshold in candidates:
        metrics = operating_metrics(labels, scores, threshold)
        if metrics["false_positive_rate"] <= false_alarm_budget:
            feasible.append({"threshold": float(threshold), **metrics})
            
    if not feasible:
        # Fallback al candidato más estricto
        return {"threshold": float(scores.max()), **operating_metrics(labels, scores, float(scores.max()))}

    # Mejor punto de operación: mayor recall, desempate por precisión, luego umbral más alto
    return max(feasible, key=lambda item: (item["recall"], item["precision"], item["threshold"]))


def evaluate(
    data: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
    incidents: list[dict]
) -> dict:
    """Calcula el informe integral de evaluación combinando métricas puntuales y basadas en eventos."""
    labels = data["is_anomaly"].to_numpy()
    point_metrics = operating_metrics(labels, scores, threshold)
    event_metrics = event_based_metrics(data, scores, threshold, incidents)
    avg_prec = float(average_precision_score(labels, scores))

    return {
        **point_metrics,
        "average_precision": round(avg_prec, 4),
        "event_based": event_metrics,
        "prevalence": float(np.mean(labels)),
        "windows_evaluated": len(labels)
    }
