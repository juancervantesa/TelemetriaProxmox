# Especificación de la API REST — SIGeCAD

La API está implementada con **FastAPI** y expone servicios para inferencia en tiempo real, metadatos de configuración, resultados de evaluación e inspección de incidentes.

Base URL local: `http://127.0.0.1:8994`

---

## 1. Estado del Sistema (`GET /api/health`)
Verifica la disponibilidad del servicio y la carga del modelo en memoria.

### Respuesta Exitosa (`200 OK`):
```json
{
  "status": "ok",
  "system": "SIGeCAD Data Center Telemetry Anomaly Detector",
  "version": "sigecad-iforest-v1-a1b2c3d4",
  "features_count": 11
}
```

---

## 2. Metadatos de Configuración (`GET /api/config`)
Retorna los metadatos de las 11 variables de telemetría, rangos, unidades, umbrales de la línea base y escenarios operacionales preconfigurados.

### Respuesta Exitosa (`200 OK`):
```json
{
  "features": {
    "cpu_mean": { "label": "CPU promedio", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 24.5 },
    "cpu_max": { "label": "CPU pico", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 35.0 }
  },
  "feature_order": ["cpu_mean", "cpu_max", "cpu_std", "cpu_trend", "memory_pct_mean", "memory_pct_max", "memory_pct_trend", "iowait_mean", "iowait_max", "net_io_mb_s", "temp_max_c"],
  "baseline_thresholds": {
    "warning": { "cpu_max": 80.0, "memory_pct_max": 85.0, "iowait_max": 15.0, "temp_max_c": 75.0 },
    "critical": { "cpu_max": 90.0, "memory_pct_max": 95.0, "iowait_max": 30.0, "temp_max_c": 85.0 }
  },
  "scenarios": [...]
}
```

---

## 3. Inspección de Ventana de Telemetría (`POST /api/inspect`)
Ejecuta la inferencia de Isolation Forest y evalúa la Línea Base sobre una ventana de 10 minutos.

### Solicitud (`POST /api/inspect`):
```json
{
  "resource_id": "guest:100_AD-Zentyal",
  "cpu_mean": 32.0,
  "cpu_max": 42.0,
  "cpu_std": 4.1,
  "cpu_trend": 1.2,
  "memory_pct_mean": 74.0,
  "memory_pct_max": 82.5,
  "memory_pct_trend": 24.5,
  "iowait_mean": 0.8,
  "iowait_max": 2.5,
  "net_io_mb_s": 15.0,
  "temp_max_c": 50.5
}
```

### Respuesta Exitosa (`200 OK`):
```json
{
  "score": 0.5842,
  "threshold": 0.5389,
  "alert": true,
  "score_percentage": 71.1,
  "baseline": {
    "score": 0.8684,
    "threshold": 0.7465,
    "alert": true,
    "decision": {
      "alert": false,
      "status": "normal",
      "critical_violations": [],
      "warning_violations": []
    }
  },
  "diagnosis": "Patrón característico de Fuga de Memoria Progresiva (Memory Leak)",
  "indicators": [
    {
      "feature": "memory_pct_trend",
      "label": "Tendencia RAM (pendiente)",
      "unit": "%/10m",
      "value": 24.5,
      "reference": { "min": -7.8, "max": 7.9, "median": 0.0, "p01": -3.2, "p99": 3.4 },
      "robust_distance": 22.45,
      "outside_observed_range": true
    }
  ],
  "resource_id": "guest:100_AD-Zentyal",
  "version": "sigecad-iforest-v1-a1b2c3d4",
  "model_name": "Isolation Forest (Multivariado)"
}
```

### Respuesta de Error de Validación (`422 Unprocessable Entity`):
Ocurre si se ingresan valores negativos, fuera de límites físicos o inconsistentes:
```json
{
  "error": "Error de validación en la ventana de telemetría ingresada",
  "detalles": [
    {
      "field": "body -> cpu_mean",
      "message": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

---

## 4. Métricas Formales de Evaluación (`GET /api/metrics`)
Retorna el informe completo con el cálculo de F1 por Evento, precisión, recall, FPR y lead time sobre las particiones de validación y prueba.

---

## 5. Catálogo de Incidentes (`GET /api/events`)
Retorna el listado de incidentes evaluados en el conjunto de prueba junto con el resultado de detección y tiempo de anticipación alcanzado.
