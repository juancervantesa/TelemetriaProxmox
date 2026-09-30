# Metodología y Selección de Modelos — SIGeCAD

## 1. El Problema y la Solución Actual (Línea Base)

El monitoreo operacional clásico en plataformas de virtualización (como Proxmox VE, Zabbix o Nagios) se basa en **umbrales estáticos univariados**:
- Regla Warning: Si $\text{CPU} \ge 80\%$ ó $\text{RAM} \ge 85\%$ ó $\text{IOWait} \ge 15\%$ ó $\text{Temp} \ge 75^\circ\text{C}$.
- Regla Critical: Si $\text{CPU} \ge 90\%$ ó $\text{RAM} \ge 95\%$ ó $\text{IOWait} \ge 30\%$ ó $\text{Temp} \ge 85^\circ\text{C}$.

### Limitaciones de la Solución Actual:
1. **Falta de anticipación en fallas progresivas:** Una fuga de memoria (*memory leak*) que crece de forma lineal y constante (+20% por hora) no dispara alertas hasta que la RAM roza el 85%, momento en el que el margen de maniobra del operador es mínimo.
2. **Ceguera multivariada:** No detecta combinaciones anómalas pero de valores moderados individuales (por ejemplo: CPU al 60%, I/O Wait al 12% y Temperatura al 72°C al mismo tiempo).
3. **Falsas alarmas en cargas legítimas:** Procesos por lotes normales (como copias de seguridad de Proxmox con `vzdump` o tareas de compresión) elevan la CPU por encima del 85% sin representar una falla real, saturando a los operadores con notificaciones innecesarias.

---

## 2. Modelo Propuesto: Isolation Forest Multivariado

El modelo seleccionado es un **Isolation Forest** (bosque de aislamiento no supervisado):
- **Fundamento matemático:** Las instancias anómalas son "pocas y diferentes", por lo que requieren significativamente menos particiones aleatorias en árboles de decisión binarios para ser aisladas cerca de la raíz.
- **Hiperparámetros fijados en el experimento:**
  - $N_{\text{estimators}} = 200$ árboles.
  - $S_{\text{samples}} = 256$ submuestras por árbol (garantiza resistencia frente al enmascaramiento o *swamping*).
  - $\text{Contamination} = \text{"auto"}$.
  - Semilla determinista: $\text{random\_state} = 42$.
- **Cálculo del puntaje de anomalía:**
  $$\text{Score}(x) = - \text{score\_samples}(x)$$
  Invertimos el signo del estimador de scikit-learn para que un valor más alto represente consistentemente mayor grado de anomalía.

---

## 3. Calibración de Umbrales con Presupuesto de Falsas Alarmas

En aprendizaje no supervisado sin etiquetas durante el entrenamiento, el modelo produce un puntaje continuo, no una decisión binaria. Para convertir el puntaje en una alerta operativa $\{0, 1\}$, se selecciona el umbral $\tau$ sobre el **conjunto de validación**.

### Criterio de Selección:
Fijamos un **presupuesto máximo de tasa de falsas alarmas (FPR)**:
$$\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}} \le 5\%$$

El algoritmo evalúa todos los puntajes candidatos en validación y selecciona el umbral $\tau^*$ que:
1. Satisface $\text{FPR}(\tau^*) \le 0.05$.
2. Maximiza la sensibilidad o cobertura ($\text{Recall}$).
3. En caso de empate, desempata por mayor precisión y mayor margen de separación.

Tanto para Isolation Forest como para la Línea Base, **el umbral queda congelado al finalizar la validación** y se evalúa de manera estricta y sin modificaciones sobre el conjunto de prueba.

---

## 4. Métrica Principal: F1 por Evento de Incidente

### ¿Por qué NO usar únicamente F1 a nivel de punto/ventana?
En series temporales de infraestructura, un incidente real suele extenderse a lo largo de varias horas (por ejemplo, 12 ventanas consecutivas de 10 minutos).
- Si un modelo emite alerta temprana en las dos primeras ventanas (alertando con éxito al administrador antes del colapso), pero no en las 10 posteriores porque el sistema ya se estabilizó en modo degradado, la métrica tradicional punto a punto clasificaría esas 10 ventanas como "Falsos Negativos (FN)", arrojando un F1 engañosamente bajo.
- Operativamente, **lo que le importa al centro de datos es la detección completa y oportuna del incidente**.

### Definición Formal de F1 por Evento:
Para un incidente $I_k = [t_{\text{inicio}}, t_{\text{fin}}]$ en el recurso $R_k$:
- **True Positive (TP_evento):** El sistema emitió al menos una alerta en el recurso $R_k$ dentro del intervalo $[t_{\text{inicio}} - t_{\text{lead}}, t_{\text{fin}}]$.
- **False Negative (FN_evento):** El incidente $I_k$ ocurrió y el sistema no disparó ninguna alerta en ese intervalo.
- **False Positive (FP_evento):** Ráfaga de alertas generadas en un recurso durante un periodo normal sin ningún incidente asociado.

$$\text{Recall}_{\text{evento}} = \frac{\text{TP}_{\text{evento}}}{\text{Total de Incidentes}}$$
$$\text{Precision}_{\text{evento}} = \frac{\text{TP}_{\text{evento}}}{\text{TP}_{\text{evento}} + \text{FP}_{\text{evento}}}$$
$$\text{F1}_{\text{evento}} = \frac{2 \cdot \text{Precision}_{\text{evento}} \cdot \text{Recall}_{\text{evento}}}{\text{Precision}_{\text{evento}} + \text{Recall}_{\text{evento}}}$$

### Métrica de Anticipación: Lead Time Medio
Por cada incidente detectado con éxito ($TP$), se calcula el tiempo de anticipación:
$$\text{Lead Time} = t_{\text{inicio}} - t_{\text{primera\_alerta}}$$
Un valor positivo representa minutos ganados por el equipo de operaciones antes de la falla visible o caída del servicio.
