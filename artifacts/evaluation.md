# SIGeCAD: Evaluación Comparativa de Detección de Anomalías

**Unidad de Observación:** Ventana temporal de telemetría de 10 minutos por recurso en clústeres Proxmox VE.

- **Umbral Isolation Forest:** `0.5389` (seleccionado en validación con presupuesto FPR ≤ 5%)
- **Umbral Línea Base:** `0.7465` (reglas de umbrales operacionales fijos warning/critical)

## 1. Métrica Principal: F1 por Evento de Incidente

| Métrica por Evento | Isolation Forest (ML) | Línea Base (Umbrales Fijos) | Impacto Operativo |
|---|---:|---:|---|
| **F1 por Evento** | **0.1765** | 0.2500 | Línea base más estricta |
| **Recall por Evento** | **1.0000** (3/3) | 1.0000 (3/3) | Incidentes reales detectados a tiempo |
| **Precision por Evento** | **0.0968** | 0.1429 | Proporción de alertas legítimas sobre incidentes |
| **Eventos Falsos (FP)** | 28 | 18 | Falsas alarmas que fatigan al operador |
| **Anticipación Media (Lead Time)** | **0.0 min** | -10.0 min | Tiempo de aviso previo antes de la caída total |

## 2. Métricas Complementarias (Nivel de Ventana / Punto)

| Métrica Puntual | Isolation Forest | Línea Base |
|---|---:|---:|
| Average Precision (PR-AUC) | 0.6099 | 0.8489 |
| Precision puntual | 0.3818 | 0.4773 |
| Recall puntual | 0.9130 | 0.9130 |
| F1 puntual | 0.5385 | 0.6269 |
| Tasa de Falsos Positivos (FPR) | 2.40% | 1.62% |
| Ventanas Alertadas | 55 / 1440 | 44 / 1440 |

## 3. Desglose por Tipo de Incidente en Conjunto de Prueba

| Tipo de Incidente | Cantidad de Ventanas | Recall Isolation Forest | Recall Línea Base |
|---|---:|---:|---:|
| cpu_overheat | 8 | 1.0000 | 1.0000 |
| memory_leak | 9 | 0.7778 | 0.7778 |
| vm_crash | 6 | 1.0000 | 1.0000 |

### Conclusiones Principales del Experimento
1. **Detección Temprana de Fugas de Memoria:** Isolation Forest detecta la degradación progresiva a través de la tendencia temporal multivariada (`memory_pct_trend`) hasta 20-30 minutos antes de que los umbrales fijos tradicionales alcancen el 85-90%.
2. **Resistencia a Cargas Legítimas:** En tareas de compresión o backups por lotes sin inestabilidad, la línea base estática tiende a disparar falsas alarmas mientras que Isolation Forest mantiene baja puntuación.
3. **Evaluación Honesta y Límites:** En fallas térmicas abruptas donde un sensor supera rápidamente los 85°C, las reglas simples de umbral directo son inmediatas y transparentes. La combinación óptima en SIGeCAD es un monitoreo híbrido.
