# Guion y Estructura de Diapositivas — Presentación Individual (5 Minutos)

**Proyecto:** SIGeCAD — Detección de Anomalías en Telemetría de Centro de Datos (Proxmox VE)  
**Modalidad:** Exposición oral con demostración de sistema funcional en vivo  
**Límite de Tiempo:** Exactamente 5 minutos  

---

## Estructura de las 5 Diapositivas

```
[ Diapositiva 1 ] · Portada y Contexto del Problema (SIGeCAD en Proxmox)
[ Diapositiva 2 ] · Metodología: Ventanas, Isolation Forest y F1 por Evento
[ Diapositiva 3 ] · Tabla de Resultados: Comparativa Honesta vs Línea Base
[ Diapositiva 4 ] · Demostración en Vivo del Sistema (Frontend + API + Inferencia)
[ Diapositiva 5 ] · Conclusiones, Limitaciones y Repositorio Git
```

---

## Guion Detallado con Cronómetro

### Minuto 0:00 - 1:00 · Problema y Solución Actual
*(Diapositiva 1)*
> "Buenos días, profesor y compañeros. Mi proyecto se titula **Detección de anomalías en la telemetría del centro de datos — SIGeCAD**.
> 
> En centros de datos basados en **Proxmox VE**, administramos decenas de máquinas virtuales y nodos físicos de alta criticidad. La solución tradicional de la industria monitorea mediante **umbrales estáticos univariados** (por ejemplo: alertar si la CPU supera el 80% o la RAM el 85%).
> 
> Sin embargo, este enfoque tiene dos grandes fallas operacionales:
> 1. No detecta anomalías multivariadas ni degradaciones progresivas como **fugas de memoria (*memory leaks*)**, donde el consumo sube constantemente pero no alerta hasta que el servidor está a punto de colapsar.
> 2. Genera fatiga de alertas por falsas alarmas cuando hay tareas legítimas pesadas, como backups nocturnos de Proxmox con `vzdump`."

---

### Minuto 1:00 - 2:00 · Metodología, Dataset y Resultados Frente a la Línea Base
*(Diapositivas 2 y 3)*
> "Para resolverlo, definimos como **unidad de observación la ventana temporal agregada de 10 minutos por recurso**, extrayendo 11 métricas clave de nivel medio, picos, variabilidad y tendencias direccionales.
> 
> Usamos un modelo no supervisado **Isolation Forest** entrenado exclusivamente sobre un periodo de telemetría puramente normal previo al 18 de septiembre. Calibramos el umbral de decisión en el conjunto de validación fijando un presupuesto de falsas alarmas menor al 5%.
> 
> La métrica principal es el **F1 por Evento de Incidente**, evaluando si el modelo alerta dentro del incidente o con anticipación (*Lead Time*).
> 
> En el conjunto de prueba independiente:
> - Ambos métodos alcanzaron un **Recall por Evento del 100%**, detectando todos los incidentes críticos reales.
> - La **Línea Base** obtuvo un F1 por evento ligeramente superior (0.25 vs 0.17) debido a menor número de falsos positivos en el umbral seleccionado.
> - Sin embargo, **Isolation Forest demostró una ventaja operativa crucial: alertó con un Lead Time de anticipación promedio 10 minutos antes** que los umbrales fijos en fallas progresivas de memoria y cuellos de botella de disco."

---

### Minuto 2:00 - 3:00 · Demostración en Vivo: Caso Válido y Detección
*(Pasar al navegador con http://127.0.0.1:8994)*
> "A continuación, vemos la interfaz del sistema conectada en tiempo real al backend FastAPI y al modelo.
> 
> 1. Primero, cargo el **Caso Válido: Operación Normal de Servicio**.
> Al presionar *Analizar ventana*, observamos que tanto Isolation Forest (puntaje 0.42 frente al umbral 0.53) como la Línea Base coinciden en un estado **NORMAL**. Las 11 variables se encuentran dentro de las referencias históricas esperadas.
> 
> 2. Ahora selecciono el escenario de **Fuga de Memoria Progresiva en una VM**.
> Observen cómo la RAM promedio está en 74% y el pico en 82.5% —ambos por debajo del umbral estático de 85% de la línea base, por lo que la línea base permanece apagada—. Sin embargo, **Isolation Forest detecta inmediatamente la anomalía** (puntaje 0.58 > 0.53) y el diagnóstico explica que la causa es la pendiente acelerada de acumulación de memoria (`memory_pct_trend`)."

---

### Minuto 3:00 - 4:00 · Demostración en Vivo: Caso Difícil y Manejo de Errores
*(Continuar en la interfaz)*
> "3. Veamos ahora el **Caso Difícil: Tarea de Compresión Legítima**.
> Aquí la CPU está al 88%, lo cual dispararía una falsa alarma en sistemas tradicionales. Sin embargo, como la variabilidad es baja (desviación 1.2%), la temperatura es normal (64°C) y la memoria es estable, el modelo reconoce la coherencia del proceso y evita una falsa alarma crítica.
> 
> 4. Finalmente, demuestro el **Manejo de Errores e Insumos Inválidos**.
> Si un sensor o agente envía una lectura corrupta, por ejemplo un porcentaje negativo de CPU (-25%) o un pico menor al promedio, el backend aplica validación estricta con Pydantic y rechaza la solicitud retornando **código HTTP 422 Unprocessable Entity**, mostrando en la interfaz exactamente qué campo violó las restricciones físicas."

---

### Minuto 4:00 - 5:00 · Conclusiones, Límites y Entrega
*(Diapositiva 5)*
> "Para concluir:
> 1. Demostramos que las ventanas temporales agregadas de 10 minutos y el modelo Isolation Forest aportan una **alerta temprana efectiva (Lead Time positivo)** frente a incidentes operacionales graduales en Proxmox.
> 2. Como **limitación honesta**, el modelo no supervisado requiere periodos de referencia limpios y genera mayor dispersión de alertas en cargas no estacionarias, por lo que la recomendación arquitectónica final para SIGeCAD es un **enfoque híbrido**: umbrales fijos para protección inmediata por sobrecalentamiento e Isolation Forest para detección predictiva temprana.
> 
> Todo el código fuente, dataset reproducible, suite de 17 pruebas, documentación técnica en PDF y guion están versionados en el repositorio Git entregado.
> 
> Muchas gracias. Quedo atento a sus preguntas."
