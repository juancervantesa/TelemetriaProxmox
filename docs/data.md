# Diccionario de Datos y Metodología de Ventanas Temporales — SIGeCAD

## 1. Origen y Contexto de los Datos
El conjunto de datos captura la telemetría operacional en tiempo real de centros de datos que ejecutan **Proxmox Virtual Environment (PVE)** sobre hardware de servidor empresarial (HP ProLiant DL-360, DL-380 y Dell PowerEdge R740), organizada en clústeres distribuidos (Cluster-Principal, Cluster-SantaCruz, Cluster-Cochabamba, etc.).

La base de datos original del proyecto, denominada `proxmox_monitor` y gestionada en **TimescaleDB / PostgreSQL**, ingesta periódicamente:
- **`node_metrics`:** Métricas a nivel de hipervisor/host (CPU, memoria, iowait, swap, uptime, disco). Frecuencia: cada 30 segundos.
- **`guest_metrics`:** Métricas a nivel de máquinas virtuales KVM/QEMU y contenedores LXC (CPU, memoria asignada/usada, E/S de disco, tráfico de red entrante/saliente). Frecuencia: cada 30 segundos.
- **`hardware_sensors`:** Métricas de telemetría de chasis y procesador vía BMC / Redfish / IPMI (temperatura de núcleos, revoluciones de ventiladores, consumo en Watts). Frecuencia: cada 300 segundos (5 minutos).
- **`cluster_logs`:** Registro cronológico de tareas del clúster, cambios de estado y eventos de error o alerta (`qmstart`, `qmreboot`, `vzdump`, caídas de procesos, desmontajes de storage).

Para garantizar máxima reproducibilidad pedagógica y permitir que cualquier evaluador ejecute el sistema sin requerir la infraestructura de bases de datos activa, se incluye un **generador sintético determinista** (`app/data.py`, semilla `SEED = 42`) que modela matemáticamente los ciclos diarios de carga, la correlación entre métricas y la inyección controlada de incidentes reales documentados.

---

## 2. Definición de la Unidad de Observación: Ventana Temporal

En el monitoreo tradicional de centros de datos, inspeccionar lecturas individuales cada 30 segundos genera una tasa excesiva de **falsas alarmas**, causadas por ráfagas cortas e inofensivas de procesamiento (por ejemplo, el arranque de un cron job o un chequeo de integridad).

Por ello, la **unidad de observación** se define como una **ventana temporal agregada de 10 minutos** para un recurso específico:
$$\text{Unidad} = (\text{recurso\_id}, \text{ventana\_10\_min})$$

- **Duración de la ventana ($W$):** 10 minutos ($20$ muestras por ventana en telemetría de 30 s).
- **Desplazamiento ($S$):** 2 minutos para monitoreo en vivo (ventana deslizante / *sliding window*); 30 minutos entre ventanas en el dataset tabular de evaluación para garantizar independencia estadística entre ventanas adyacentes.

---

## 3. Variables Resumidas Extraídas por Ventana (Features)

Por cada ventana de 10 minutos se extraen 11 características estadísticas multivariadas:

| Variable | Nombre en Sistema | Tipo | Unidad | Rango Físico | Descripción Operacional |
|---|---|---|---|---|---|
| **CPU Promedio** | `cpu_mean` | Float | % | [0.0, 100.0] | Nivel medio de utilización de procesador durante la ventana. |
| **CPU Pico** | `cpu_max` | Float | % | [0.0, 100.0] | Consumo máximo puntual de CPU alcanzado en los 10 minutos. |
| **Variabilidad CPU** | `cpu_std` | Float | % | [0.0, 50.0] | Desviación estándar del uso de CPU; mide inestabilidad y oscilaciones erráticas. |
| **Tendencia CPU** | `cpu_trend` | Float | %/10m | [-50.0, 50.0] | Pendiente o cambio neto ($\Delta$) entre el final y el inicio de la ventana. |
| **Memoria RAM Promedio** | `memory_pct_mean` | Float | % | [0.0, 100.0] | Porcentaje medio de memoria RAM ocupada en relación al total del recurso. |
| **Memoria RAM Pico** | `memory_pct_max` | Float | % | [0.0, 100.0] | Porcentaje máximo de saturación de memoria RAM. |
| **Tendencia RAM** | `memory_pct_trend` | Float | %/10m | [-50.0, 50.0] | Tasa de acumulación neta de memoria; **variable crítica para detectar *memory leaks***. |
| **I/O Wait Promedio** | `iowait_mean` | Float | % | [0.0, 100.0] | Porcentaje de tiempo que la CPU estuvo ociosa esperando respuestas del subsistema de disco. |
| **I/O Wait Pico** | `iowait_max` | Float | % | [0.0, 100.0] | Pico de contención de disco; alerta cuellos de botella de SAN, NFS o Ceph. |
| **Tráfico de Red** | `net_io_mb_s` | Float | MB/s | [0.0, 500.0] | Tasa media agregada de transferencia de red (in + out). |
| **Temperatura Máxima** | `temp_max_c` | Float | °C | [15.0, 120.0] | Temperatura máxima registrada por los sensores térmicos del chasis o CPU. |

---

## 4. Normalización y Escalamiento Robusto

Dado que diferentes tipos de recursos tienen capacidades dispares (nodos físicos de 128 GB de RAM vs VMs ligeras de 2 GB), la telemetría se normaliza mediante:
1. **Unidades relativas porcentuales:** Memoria y CPU se expresan siempre como fracción de la capacidad total del recurso.
2. **Escalamiento Robusto (RobustScaler):** Para cada variable $x_j$, se calcula la mediana $\tilde{x}_j$ y la desviación absoluta mediana ($MAD_j$) calculada exclusivamente sobre el conjunto de entrenamiento normal:
   $$MAD_j = \text{mediana}(|x_j - \tilde{x}_j|)$$
   $$\text{Escala}_j = \max(1.4826 \cdot MAD_j, 10^{-6})$$
   $$\text{Distancia MAD} = \left|\frac{x_j - \tilde{x}_j}{\text{Escala}_j}\right|$$

Este escalamiento previene que valores extremos o colapsos operativos distorsionen la escala base del modelo.

---

## 5. Particiones Temporales (Sin Fugas)

Para respetar rigurosamente la causalidad temporal y evitar fugas de información (*data leakage*):
- **Entrenamiento (Train):** Telemetría anterior al `2026-09-18T00:00:00` (16 días continuos, 4.608 ventanas). Contiene **exclusivamente datos normales verificados**.
- **Validación (Validation):** Desde `2026-09-18T00:00:00` hasta `2026-09-25T00:00:00` (7 días, 2.016 ventanas, 30 anómalas). Se utiliza exclusivamente para calibrar los umbrales de decisión bajo un presupuesto fijo de falsas alarmas (FPR $\le 5\%$).
- **Prueba (Test):** Posterior al `2026-09-25T00:00:00` (5 días, 1.440 ventanas, 23 anómalas). Conjunto intocado utilizado únicamente para evaluar el modelo final y compararlo con la línea base.
