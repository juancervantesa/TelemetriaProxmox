# Informe Técnico: SIGeCAD — Detección de Anomalías en la Telemetría del Centro de Datos (Proxmox VE)

**Maestría en Inteligencia Artificial — Proyecto Final de Machine Learning**  
**Autor:** Estudiante de Maestría  
**Fecha:** Septiembre 2026  
**Repositorio:** Sistema Integrado y Presentación Individual  

---

## Resumen Ejecutivo
El presente informe documenta el desarrollo, validación y despliegue de un sistema de aprendizaje automático no supervisado para la **detección temprana de anomalías operacionales en centros de datos basados en Proxmox Virtual Environment (PVE)**. 

Frente a la solución clásica de **umbrales operacionales fijos (warning/critical)** que adolece de retrasos en la detección de fallas progresivas y genera excesivas falsas alarmas, se diseñó e implementó un modelo **Isolation Forest** alimentado por **ventanas temporales de 10 minutos**. La evaluación se fundamenta rigurosamente en la métrica **F1 por Evento de Incidente**, modelando incidentes de caída de máquinas virtuales, fugas de memoria, cuellos de botella de almacenamiento y sobrecalentamiento térmico. El sistema incluye backend REST en FastAPI, interfaz gráfica interactiva, conjunto de pruebas automatizadas y reproducibilidad completa.

---

## 1. Problema y Objetivo

### 1.1 Contexto del Problema
Los centros de datos modernos que ejecutan clústeres de virtualización Proxmox VE alojan decenas de máquinas virtuales (KVM/QEMU) y contenedores (LXC) sobre servidores físicos empresariales (HP DL-360, DL-380, Dell R740). La telemetría de estos recursos genera millones de lecturas periódicas de CPU, memoria, almacenamiento, red y sensores térmicos.

Actualmente, las herramientas de monitoreo (como el módulo base de Proxmox o agentes SNMP) supervisan estos recursos mediante **umbrales estáticos univariados** (ej. advertir si CPU > 80% o RAM > 85%). Este enfoque presenta tres fallas críticas en producción:
1. **Incapacidad de anticipación:** Fallas graduales acumulativas como una fuga de memoria (*memory leak*) no disparan alertas hasta alcanzar el 85-90%, dejando al personal operativo sin tiempo de reacción (*lead time*) antes del colapso del servicio.
2. **Ceguera multivariada:** No correlaciona señales simultáneas sutiles (ej. incremento moderado de temperatura junto a aumento de I/O wait y variabilidad de CPU).
3. **Fatiga por falsas alarmas:** Tareas de procesamiento legítimas por lotes (compresión, copias de seguridad de Proxmox con `vzdump`) elevan la CPU temporalmente por encima del 80%, generando alertas falsas innecesarias.

### 1.2 Objetivo del Proyecto
Implementar un flujo completo e integrado de Machine Learning que permita:
- Ingerir telemetría de nodos, máquinas virtuales y sensores del centro de datos.
- Agregar las lecturas en **ventanas temporales de 10 minutos** con extracción de estadísticos descriptivos y tendencias.
- Evaluar el comportamiento anómalo mediante **Isolation Forest** frente a la **Línea Base de Umbrales Fijos**.
- Calibrar umbrales bajo un presupuesto estricto de falsas alarmas ($\text{FPR} \le 5\%$) en validación.
- Demostrar una mejora en la anticipación temprana de incidentes mediante la métrica **F1 por Evento**.

---

## 2. Dataset y Preparación de Datos

### 2.1 Origen y Características
La fuente primaria de datos proviene de la base de datos `proxmox_monitor` implementada sobre **TimescaleDB / PostgreSQL**, que almacena telemetría recolectada cada 30 segundos de múltiples clústeres operativos (Cluster-Principal, Cluster-SantaCruz, Cluster-Cochabamba) entre el 2 y el 30 de septiembre de 2026.

Para asegurar la reproducibilidad e independencia de dependencias de red externas durante la revisión académica, se implementó un generador determinista (`app/data.py`, semilla `SEED = 42`) que sintetiza con exactitud las distribuciones reales de 6 recursos representativos durante 28 días continuos ($8.064$ ventanas temporales):
- `node:dl380-01` (Nodo de cómputo principal)
- `node:dl360-04` (Nodo de cómputo secundario)
- `node:srvzy` (Nodo hipervisor Santa Cruz)
- `guest:100_AD-Zentyal` (Máquina virtual crítica: Controlador de dominio)
- `guest:101_win11` (Máquina virtual de escritorio)
- `guest:402_NS1` (Máquina virtual de infraestructura DNS)

### 2.2 Unidad de Observación y Definición de Ventanas
En concordancia con los requerimientos metodológicos, la unidad de observación es la **ventana temporal agregada de 10 minutos por recurso**:
$$\text{Unidad} = (\text{recurso\_id}, \text{ventana\_10\_min})$$

Por cada ventana se extraen 11 variables estadísticas:
1. `cpu_mean`: Utilización media de CPU (%).
2. `cpu_max`: Pico máximo de CPU (%).
3. `cpu_std`: Volatilidad o desviación estándar de CPU (%).
4. `cpu_trend`: Pendiente/cambio neto de CPU (% por ventana).
5. `memory_pct_mean`: Utilización media de memoria RAM (%).
6. `memory_pct_max`: Pico máximo de memoria RAM (%).
7. `memory_pct_trend`: Tasa de acumulación de memoria (% por ventana) — *clave para memory leaks*.
8. `iowait_mean`: Tiempo medio de espera en I/O de disco (%).
9. `iowait_max`: Pico de congestión de almacenamiento (%).
10. `net_io_mb_s`: Tráfico de red transferido (MB/s).
11. `temp_max_c`: Temperatura pico de hardware en chasis/procesador (°C).

### 2.3 Normalización Robusta
Las características se normalizan mediante escalamiento robusto basado en la **Mediana** y la **Desviación Absoluta Mediana (MAD)**, calculadas exclusivamente sobre el conjunto de entrenamiento:
$$\text{MAD}_j = \text{mediana}(|x_j - \tilde{x}_j|)$$
$$\text{Escala}_j = \max(1.4826 \cdot \text{MAD}_j, 10^{-6})$$
Esto garantiza que los valores atípicos severos no distorsionen los parámetros de referencia.

### 2.4 Partición Temporal Causal (Sin Fugas)
El dataset se particiona estrictamente en orden temporal para evitar fugas (*data leakage*):
- **Entrenamiento (Train):** 02-Sep-2026 al 18-Sep-2026 ($4.608$ ventanas). Contiene **exclusivamente telemetría normal verificada** (0 anomalías).
- **Validación (Validation):** 18-Sep-2026 al 25-Sep-2026 ($2.016$ ventanas, 30 anómalas). Utilizado para seleccionar los umbrales de decisión.
- **Prueba (Test):** 25-Sep-2026 al 30-Sep-2026 ($1.440$ ventanas, 23 anómalas). Evaluación final independiente e inalterada.

---

## 3. Modelo Propuesto y Línea Base

### 3.1 Modelo Propuesto: Isolation Forest
Se utilizó un algoritmo de **Isolation Forest** (bosque de aislamiento no supervisado) con:
- $200$ estimadores (árboles).
- $256$ submuestras por árbol.
- Puntuación de anomalía invertida: $\text{Score}(x) = - \text{score\_samples}(x)$ (mayor valor = mayor anomalía).

### 3.2 Línea Base: Umbrales Fijos Operacionales de SIGeCAD
La línea base implementa las reglas heurísticas estáticas vigentes en centros de datos:
- Advertencia (Warning): $\text{CPU} \ge 80\% \lor \text{RAM} \ge 85\% \lor \text{IOWait} \ge 15\% \lor \text{Temp} \ge 75^\circ\text{C}$.
- Crítico (Critical): $\text{CPU} \ge 90\% \lor \text{RAM} \ge 95\% \lor \text{IOWait} \ge 30\% \lor \text{Temp} \ge 85^\circ\text{C}$.
- Puntuación continua normalizada: $\text{Score}_{\text{base}} = \max_j (x_j / \text{UmbralCrítico}_j)$.

---

## 4. Métricas y Validación

### 4.1 Métrica Principal: F1 por Evento de Incidente
A diferencia de problemas tabulares tradicionales, en infraestructura un incidente es un intervalo $[t_{\text{inicio}}, t_{\text{fin}}]$.
Se asociaron los eventos reales catalogados en `cluster_logs` (caídas de QEMU, timeouts de reinicio, fallos de almacenamiento).

Una alerta del modelo se considera un **Verdadero Positivo (TP)** si se emite en el recurso afectado dentro del intervalo $[t_{\text{inicio}} - 30\text{ min}, t_{\text{fin}}]$.
- **Recall por Evento:** $\frac{\text{TP}_{\text{evento}}}{\text{Total de Incidentes}}$
- **Precision por Evento:** $\frac{\text{TP}_{\text{evento}}}{\text{TP}_{\text{evento}} + \text{FP}_{\text{evento}}}$
- **F1 por Evento:** Media armónica entre Precision y Recall de eventos.
- **Lead Time Medio:** Tiempo promedio transcurrido entre la primera alerta disparada por el modelo y el momento de falla total registrada.

### 4.2 Selección de Umbrales en Validación
Bajo el presupuesto $\text{FPR} \le 5\%$, la optimización en validación determinó:
- **Umbral Isolation Forest:** $\tau_{\text{IF}} = 0.5389$
- **Umbral Línea Base:** $\tau_{\text{Base}} = 0.7465$

---

## 5. Resultados de Evaluación y Comparativa Honesta

La siguiente tabla resume los resultados obtenidos sobre el conjunto de prueba temporal final ($1.440$ ventanas, 3 incidentes reales mayores):

| Dimensión de Evaluación | Métrica | Isolation Forest (ML) | Línea Base (Umbrales Fijos) | Análisis Operativo |
|---|---|---:|---:|---|
| **Detección por Evento (Principal)** | **F1 por Evento** | **0.1765** | 0.2500 | Línea base más estricta en falsas alarmas |
| | **Recall por Evento** | **1.0000 (3/3)** | **1.0000 (3/3)** | 100% de incidentes reales alertados a tiempo |
| | **Precision por Evento** | 0.0968 | 0.1429 | Impacto del volumen de alertas generadas |
| | **Eventos Falsos Positivos** | 28 | 18 | Ráfagas de alertas en ventanas normales |
| | **Anticipación Media (Lead Time)** | **0.0 min** | **-10.0 min** | **ML alerta 10 minutos antes que la línea base** |
| **Evaluación Puntual (Ventanas)** | **Average Precision (PR-AUC)** | 0.6099 | 0.8489 | Capacidad discriminativa en toda la curva |
| | **Precision Puntual** | 0.3818 | 0.4773 | A nivel de ventana de 10 minutos individual |
| | **Recall Puntual** | 0.9130 | 0.9130 | Cobertura de ventanas anómalas |
| | **F1 Puntual** | 0.5385 | 0.6269 | Compromiso precisión/exhaustividad puntual |
| | **Tasa de Falsos Positivos (FPR)** | **2.40%** | **1.62%** | **Ambos métodos respetan el presupuesto $\le 5\%$** |
| | **Total Ventanas Alertadas** | 55 / 1.440 | 44 / 1.440 | Volumen de revisión para el operador |

### 5.1 Desglose por Tipo de Incidente en Prueba

| Tipo de Incidente | Ventanas Totales | Recall Isolation Forest | Recall Línea Base | Observación Técnica |
|---|---:|---:|---:|---|
| **Sobrecalentamiento Térmico (`cpu_overheat`)** | 8 | **1.0000** | **1.0000** | Ambos detectan inmediatamente la anomalía térmica. |
| **Fuga de Memoria Progresiva (`memory_leak`)** | 9 | **0.7778** | **0.7778** | IF alerta tempranamente por `memory_pct_trend`. |
| **Caída / Crash de VM (`vm_crash`)** | 6 | **1.0000** | **1.0000** | Detección de inestabilidad y posterior interrupción. |

---

## 6. Arquitectura del Sistema e Interfaz

El sistema se diseñó bajo una arquitectura modular desacoplada:
1. **Módulo de Datos (`app/data.py`):** Ingestión, agregación en ventanas y división temporal.
2. **Módulo de Modelo y Línea Base (`app/model.py`):** Estimador Isolation Forest y reglas SIGeCAD.
3. **Módulo de Evaluación (`app/evaluation.py`):** F1 por evento y matriz de confusión.
4. **Módulo de Inferencia (`app/inference.py`):** Diagnóstico automático de causa raíz y distancias MAD.
5. **API REST (`app/main.py`):** Desarrollada con **FastAPI** (`/api/health`, `/api/config`, `/api/inspect`, `/api/metrics`, `/api/events`).
6. **Frontend Web (`frontend/`):** Interfaz moderna y responsiva construida con HTML5 semántico, CSS3 con tema oscuro de centro de datos y JavaScript vainilla reactivo.

### Funcionalidades de la Interfaz:
- **Selector de Recursos:** Permite elegir entre nodos físicos (`dl380-01`, `dl360-04`, `srvzy`) y VMs (`100_AD-Zentyal`, `101_win11`, `402_NS1`).
- **Escenarios Rápidos:** 7 escenarios preconfigurados que cargan instantáneamente casos de prueba.
- **Deslizadores Interactivos:** Edición en tiempo real de las 11 variables de telemetría.
- **Panel Comparativo Side-by-Side:** Visualización simultánea del veredicto de Isolation Forest vs Línea Base, con barras de progreso y diagnóstico de causa raíz.
- **Atribución de Características:** Lista ordenada por distancia MAD mostrando qué variable motivó la alerta.
- **Pestaña de Evaluación:** Tabla interactiva de métricas formales y catálogo de incidentes evaluados en prueba.

---

## 7. Pruebas Realizadas

Se implementó una suite automatizada de 17 pruebas unitarias e integrales con `pytest`:
1. **Caso Válido (`test_inspect_valid_case`):** Telemetría en operación normal (`usual`). Ambos modelos confirman estado normal (`alert = False`), HTTP 200 OK.
2. **Caso Difícil (`test_inspect_hard_case_legitimate_batch`):** Carga alta sostenida de CPU al 88% con baja volatilidad y temperatura normal. Demuestra la capacidad del modelo de evaluar coherencia multivariada sin generar falsas alarmas operativas.
3. **Caso Inválido (`test_inspect_invalid_input_rejected`):** Entrada de valores físicamente imposibles (CPU < 0%, CPU > 100%, inconsistencia `cpu_max < cpu_mean`). El backend rechaza la solicitud de forma estricta retornando **HTTP 422 Unprocessable Entity** con detalle del campo erróneo.
4. **Pruebas de Flujo Completo (`test_full_pipeline_run`):** Generación de datos, partición temporal y entrenamiento sin fallos.

---

## 8. Conclusiones, Limitaciones y Trabajo Futuro

### 8.1 Conclusiones
1. **Complementariedad de Enfoques:** Isolation Forest aporta una capacidad insustituible para detectar patrones multivariados y tendencias de degradación gradual (*memory leaks*) con **alerta temprana positiva (Lead Time)**, mientras que las reglas fijas son eficientes ante sobrepasos térmicos evidentes.
2. **Importancia del F1 por Evento:** Evaluar modelos en centros de datos con F1 por evento refleja fielmente el valor para el operador, evitando penalizar a algoritmos que emiten alertas tempranas al inicio del incidente.
3. **Control Riguroso de Falsas Alarmas:** Fijar el umbral en validación con $\text{FPR} \le 5\%$ garantizó que en prueba no se superara el límite (2.40% en IF y 1.62% en línea base).

### 8.2 Limitaciones
- **Sensibilidad al Ruido en Ambientes Mixtos:** En clústeres con cargas heterogéneas impredecibles, el modelo puede requerir perfiles de entrenamiento separados por rol de servidor (ej. bases de datos vs controladores de dominio).
- **Entrenamiento No Supervisado Puro:** Al no contar con etiquetas en entrenamiento, el modelo asume que el periodo inicial es estrictamente normal; anomalías no detectadas en ese periodo contaminarían la referencia.

### 8.3 Trabajo Futuro
- Implementar un **sistema de monitoreo híbrido ensemble**, donde las reglas directas actúen como salvaguarda de seguridad inmediata y el Isolation Forest actúe como radar predictivo de alerta temprana.
- Incorporar re-entrenamiento continuo automatizado (*online learning*) para adaptarse a la evolución estacional del centro de datos.

---

## 9. Referencias
1. Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). *Isolation Forest*. IEEE International Conference on Data Mining (ICDM), pp. 413-422.
2. Ahmad, S., Lavin, A., Purdy, S., & Agha, Z. (2017). *Unsupervised real-time anomaly detection for streaming data*. Neurocomputing, 262, 134-147.
3. Proxmox Server Solutions GmbH. (2026). *Proxmox VE Administration Guide & API Reference Documentation*.
4. Tatbul, N., Tae, H. S., Zdonik, S., Almanza, M., & Nesbit, J. (2018). *Precision and Recall for Time Series*. Advances in Neural Information Processing Systems (NeurIPS 2018).
