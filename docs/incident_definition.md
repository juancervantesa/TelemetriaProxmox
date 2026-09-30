# Especificación y Construcción de Eventos de Incidente — SIGeCAD

## 1. Definición Formal de Incidente Operativo

En el contexto de la infraestructura de virtualización de centros de datos, un **incidente operativo** se define como:
> *"Una anomalía o degradación en el comportamiento de un recurso físico o virtual que compromete la disponibilidad, rendimiento o integridad de los servicios alojados en el hipervisor."*

Matemáticamente, un evento de incidente $I$ se modela como una tupla estructurada:
$$I = \langle \text{id}, \text{recurso}, \text{tipo}, t_{\text{inicio}}, t_{\text{fin}}, \text{severidad}, \text{evidencia} \rangle$$

Donde:
- $\text{recurso} \in \{\text{nodo}, \text{máquina virtual}, \text{sensor}\}$.
- $t_{\text{inicio}}, t_{\text{fin}}$ definen el intervalo continuo de manifestación del incidente.
- $\text{tipo} \in \{\text{memory\_leak}, \text{storage\_stall}, \text{cpu\_overheat}, \text{vm\_crash}\}$.
- $\text{severidad} \in \{\text{warning}, \text{high}, \text{critical}\}$.

---

## 2. Construcción a partir de la Telemetría de Proxmox

Para construir la verdad terreno (*ground truth*) a partir de la base de datos `proxmox_monitor`, se aplican tres fuentes de correlación:

### A. Registros Críticos de Tareas (`cluster_logs`)
Proxmox registra en `cluster_logs` todas las llamadas a su API de administración con su código de salida y mensaje de error. Se extraen eventos con severidad `ERROR` y `WARNING`:
- **Timeout en apagado/reinicio:** `qmreboot: VM quit/powerdown failed - got timeout`.
- **Fallo de inicialización de QEMU:** `qmstart: start failed: QEMU exited with code 1`.
- **Fallo de punto de montaje de almacenamiento:** `unable to activate storage 'local1' - directory is expected to be a mount point but is not mounted`.
- **Fallo en copia de seguridad vzdump:** `could not activate storage 'PBS_Storage': storage is not available`.

### B. Sensores Físicos Redfish/IPMI (`hardware_sensors`)
- Infracción de umbrales térmicos en chasis DL-360 / DL-380:
  $$\text{reading\_value} \ge \text{warning\_threshold} \quad (75^\circ\text{C}) \quad \lor \quad \text{status} \ne \text{'OK'}$$

### C. Transiciones No Planificadas en Telemetría de Invitados (`guest_metrics`)
- Máquinas virtuales que pasan del estado `running` al estado `stopped` sin una tarea administrativa legítima de parada registrada en el clúster.

---

## 3. Algoritmo de Fusión y Agrupación Temporal

Los registros de errores individuales en registros o sensores suelen repetirse de forma consecutiva (por ejemplo, reintentos de `qmstart` cada 2 minutos tras una caída).

Para evitar fragmentar un único incidente en decenas de alertas artificiales, se aplica un **algoritmo de agrupamiento por densidad temporal**:
1. Se ordenan cronológicamente las evidencias de error pertenecientes al mismo recurso $R$.
2. Si la distancia temporal entre dos evidencias sucesivas es menor o igual a $\Delta t_{\text{fusión}} \le 15\text{ minutos}$, se consideran parte del mismo incidente:
   $$t_{k+1} - t_k \le 15\text{ min} \implies I_{\text{actual}} = I_{\text{actual}} \cup \{e_{k+1}\}$$
3. El inicio del evento es la primera evidencia $t_{\text{inicio}} = \min(t_k)$ y el fin es $t_{\text{fin}} = \max(t_k) + t_{\text{cooldown}}$.

---

## 4. Catálogo de Incidentes en el Experimento

| ID Incidente | Partición | Recurso Afectado | Tipo de Incidente | Intervalo Temporal | Severidad | Descripción del Fallo Operacional |
|---|---|---|---|---|---|---|
| **INC-VAL-01** | Validación | `guest:100_AD-Zentyal` | `memory_leak` | 19-Sep 08:00 a 14:00 | Alta | Fuga progresiva de memoria en servicio de directorio activo. |
| **INC-VAL-02** | Validación | `node:dl380-01` | `storage_stall` | 21-Sep 18:00 a 21:30 | Crítica | Saturación extrema de I/O wait por congestión de enlace Ceph. |
| **INC-VAL-03** | Validación | `node:dl360-04` | `cpu_overheat` | 23-Sep 11:00 a 15:00 | Media | Alarma térmica por reducción de RPM en ventilador frontal. |
| **INC-TEST-01** | Prueba | `guest:100_AD-Zentyal` | `vm_crash` | 29-Sep 14:30 a 17:00 | Crítica | Fallo de qmreboot y caída QEMU por almacenamiento no montado. |
| **INC-TEST-02** | Prueba | `node:srvzy` | `storage_stall` | 30-Sep 09:30 a 11:30 | Crítica | Desconexión de storage local1 provocando retención masiva de I/O. |
| **INC-TEST-03** | Prueba | `guest:101_win11` | `memory_leak` | 27-Sep 02:00 a 06:00 | Alta | Sobrecarga de memoria acumulativa durante respaldo nocturno vzdump. |
| **INC-TEST-04** | Prueba | `node:dl360-04` | `cpu_overheat` | 28-Sep 13:00 a 16:30 | Media | Sobrecalentamiento sostenido en procesador con lectura > 80°C. |

---

## 5. Regla de Asociación y Ventana de Anticipación (*Lead Time*)

Para asociar una ventana de predicción anómala a un incidente:
- Se define una **ventana de anticipación (Lead Time)** de hasta 30 minutos antes del inicio registrado del colapso:
  $$t_{\text{alerta}} \in [t_{\text{inicio}} - 30\text{ min}, t_{\text{fin}}]$$
- Si una alerta se produce dentro de esta franja, el incidente se marca como **Verdadero Positivo (TP)** y se calcula:
  $$\text{Lead Time} = t_{\text{inicio}} - t_{\text{alerta}}$$
  Lo cual cuantifica el tiempo con el que el equipo de soporte cuenta para mitigar el incidente antes de la interrupción total del servicio.
