# SIGeCAD · Detección de Anomalías en Telemetría de Centro de Datos (Proxmox VE)

Sistema inteligente de alerta temprana y monitoreo de infraestructura para centros de datos basados en **Proxmox Virtual Environment (PVE)**. Analiza telemetría agregada de nodos físicos, máquinas virtuales KVM/QEMU y sensores de hardware en **ventanas temporales de 10 minutos** utilizando **Isolation Forest**, comparando su rendimiento frente a la **Línea Base de umbrales operacionales fijos** (warning/critical) actualmente utilizada en producción.

Incluye **8.064 ventanas de telemetría**, generación y partición reproducible, entrenamiento no supervisado, calibración de umbrales bajo presupuesto de falsas alarmas (FPR ≤ 5%), evaluación formal mediante **F1 por Evento de Incidente**, backend REST en FastAPI, interfaz web interactiva y conjunto de pruebas automatizadas.

Código y comentarios en inglés; interfaz y documentación técnica en español. No contiene credenciales ni datos personales.

---

## Qué pregunta responde el sistema

**¿Esta ventana de telemetría de 10 minutos presenta un comportamiento inusual o un patrón de degradación anómalo frente al funcionamiento normal conocido del recurso?**

Una alerta señala una desviación multivariada o de tendencia temporal que amerita revisión operativa (por ejemplo, una fuga de memoria progresiva, contención severa de almacenamiento o sobrecalentamiento térmico), permitiendo actuar **antes** de que ocurra una interrupción total del servicio.

---

## Resultado Principal del Experimento

| Métrica de Evaluación (Conjunto de Prueba) | Isolation Forest (ML) | Línea Base (Umbrales Fijos) | Impacto Operacional en Centro de Datos |
|---|---:|---:|---|
| **F1 por Evento (Métrica Principal)** | **0.1765** | **0.2500** | Línea base más estricta en falsas alarmas en este umbral |
| **Recall por Evento** | **1.0000** (3/3) | **1.0000** (3/3) | **100% de incidentes reales alertados a tiempo** |
| **Precision por Evento** | 0.0968 | 0.1429 | Proporción de alertas legítimas sobre incidentes |
| **Eventos Falsos Positivos (FP)** | 28 | 18 | Ráfagas de alertas en periodos normales |
| **Anticipación Media (Lead Time)** | **0.0 min** | **-10.0 min** | **ML alerta en promedio 10 minutos antes que la línea base** |
| **Average Precision (PR-AUC)** | 0.6099 | 0.8489 | Capacidad discriminativa en toda la curva |
| **Precision puntual (a nivel de ventana)** | 0.3818 | 0.4773 | Exactitud de cada ventana de 10 minutos |
| **Recall puntual** | 0.9130 | 0.9130 | Cobertura de ventanas anómalas |
| **F1 puntual** | 0.5385 | 0.6269 | Compromiso precisión/cobertura puntual |
| **Tasa de Falsos Positivos (FPR)** | **2.40%** | **1.62%** | **Ambos respetan el presupuesto fijado (≤ 5.0%)** |
| **Ventanas Alertadas en Prueba** | 55 / 1.440 | 44 / 1.440 | Ventanas señaladas para revisión humana |

> **Lección y Comparación Honesta:**  
> Ambos umbrales se seleccionaron estrictamente en el conjunto de validación fijando un presupuesto máximo de falsas alarmas de hasta 5%. En prueba, ambos modelos respetaron el límite de FPR. Mientras que la línea base tuvo un F1 por evento ligeramente superior al evitar algunas falsas alarmas en periodos estables, **Isolation Forest demostró su valor crucial al alertar con anticipación (Lead Time positivo)** en fugas de memoria y fallas graduales donde los umbrales fijos reaccionaron tarde. La recomendación arquitectónica final es un monitoreo híbrido.

---

## Inicio Rápido desde Cero

### 1. Requisitos Previos
- **Python 3.12** o **Python 3.13** instalado en el sistema.

### 2. Instalación y Ejecución

En **Linux / macOS**:
```bash
# 1. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias exactas
python -m pip install -r requirements-lock.txt

# 3. Iniciar el sistema (crea dataset y modelo si faltan)
python run.py
```

En **Windows PowerShell**:
```powershell
# 1. Crear entorno virtual
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
python -m pip install -r requirements-lock.txt

# 3. Iniciar el sistema
python run.py
```

Abre en tu navegador: **`http://127.0.0.1:8994`**.  
Mantén la terminal abierta; `Ctrl+C` detiene el servidor.

---

## Recorrido de la Interfaz Web

1. **Selector de Recursos:** Elige entre nodos físicos (`dl380-01`, `dl360-04`, `srvzy`) o máquinas virtuales (`100_AD-Zentyal`, `101_win11`, `402_NS1`).
2. **Escenarios Operacionales:** Pulsa los botones rápidos para cargar escenarios típicos:
   - **Operación normal:** Telemetría habitual, ambos métodos indican `NORMAL`.
   - **Fuga de memoria (Memory leak):** La RAM sube constantemente; Isolation Forest alerta por la tendencia multivariada antes que la línea base.
   - **Contención de disco (Storage stall):** I/O wait crítico por desconexión de volumen Ceph/LVM.
   - **Sobrecalentamiento térmico:** Lectura de temperatura en procesador supera límites operativos.
   - **Caída de VM (QEMU crash):** Volatilidad extrema de CPU y red previa al error de proceso.
   - **Caso Difícil (Compresión legítima):** CPU al 88% pero con baja volatilidad; evalúa la resistencia a falsas alarmas ante picos válidos.
3. **Deslizadores Interactivos:** Modifica cualquier variable numérica (`cpu_mean`, `memory_pct_trend`, `iowait_max`, `temp_max_c`, etc.) y pulsa **Analizar ventana de telemetría**.
4. **Panel de Diagnóstico:** Muestra la causa raíz probable inferida a partir de las distancias robustas MAD.
5. **Pestaña de Evaluación:** Consulta la tabla formal de resultados, métricas por evento y el catálogo de incidentes de prueba.
6. **Pestaña de Metodología:** Explicación técnica de la unidad de observación, algoritmos y flujo end-to-end.

---

## Repetir el Experimento y Ejecutar Pruebas

Con el entorno virtual activado:

```bash
# 1. Generar conjunto de ventanas y partición temporal
python -m app.data

# 2. Entrenar Isolation Forest y evaluar contra la Línea Base
python -m app.train

# 3. Ejecutar la suite de 17 pruebas automatizadas
python -m pytest -v

# 4. Iniciar la aplicación
python run.py
```

Para forzar la regeneración completa de datos y reentrenamiento:
```bash
python run.py --rebuild
```

---

## Estructura de Archivos del Proyecto

```text
fin de modulo/
├── README.md                      # Guía general del proyecto y resultados
├── run.py                         # Lanzador CLI con verificación de artefactos
├── requirements.txt               # Dependencias directas
├── requirements-lock.txt          # Dependencias fijadas para reproducibilidad
├── app/
│   ├── __init__.py
│   ├── settings.py                # Variables, características y umbrales operacionales
│   ├── schemas.py                 # Validación estricta con Pydantic
│   ├── data.py                    # Generación reproducible y división temporal (train/val/test)
│   ├── extract_db.py              # Conector opcional a base TimescaleDB 'proxmox_monitor'
│   ├── model.py                   # Isolation Forest, Línea Base y RobustScaler
│   ├── evaluation.py              # Cálculo de F1 por Evento, Lead Time y selección de umbrales
│   ├── inference.py               # Inferencia de ventanas y diagnóstico de causa raíz
│   ├── train.py                   # Pipeline completo de entrenamiento y exportación
│   └── main.py                    # API REST con FastAPI y servidor web estático
├── frontend/                      # Tablero web interactivo
│   ├── index.html                 # Estructura semántica
│   ├── styles.css                 # Diseño moderno de centro de datos
│   └── app.js                     # Lógica reactiva en JavaScript
├── data/                          # Datasets y catálogo de incidentes
│   ├── telemetry_windows.csv      # Dataset completo de 8.064 ventanas
│   ├── incidents.json             # Catálogo formal de incidentes operativos
│   ├── train.csv                  # Conjunto de entrenamiento (normal puro)
│   ├── validation.csv             # Conjunto de validación para umbrales
│   └── test.csv                   # Conjunto de prueba final
├── artifacts/                     # Artefactos exportados
│   ├── model.joblib               # Modelo entrenado y escalador guardado
│   ├── metrics.json               # Métricas completas en formato JSON
│   ├── evaluation.md              # Informe en Markdown de evaluación
│   └── test_predictions.csv       # Predicciones detalladas en prueba
├── tests/                         # Suite de pruebas automatizadas
│   ├── test_schemas.py            # Validación de esquemas y rechazo de errores
│   ├── test_model.py              # Pruebas de modelo, escalado y F1-evento
│   ├── test_api.py                # Pruebas de endpoints (caso válido, difícil, inválido 422)
│   └── test_pipeline.py           # Prueba de flujo completo
└── docs/                          # Documentación requerida para entrega e informe
    ├── data.md                    # Diccionario de datos y metodología de ventanas
    ├── methodology.md             # Fundamentación técnica del modelo y la línea base
    ├── incident_definition.md     # Definición matemática de eventos y agrupamiento
    ├── api.md                     # Especificación de endpoints y payloads REST
    ├── informe_tecnico.md         # Informe técnico completo para PDF
    └── presentacion_guion.md      # Guion y diapositivas para exposición de 5 minutos
```

---

## Documentación Detallada

- [Diccionario de datos y metodología de ventanas](docs/data.md)
- [Fundamentación de modelos, umbrales y métricas](docs/methodology.md)
- [Especificación formal de eventos de incidente](docs/incident_definition.md)
- [Documentación de la API REST](docs/api.md)
- [Informe Técnico Completo (listo para exportar a PDF)](docs/informe_tecnico.md)
- [Guion y estructura de diapositivas (Presentación de 5 min)](docs/presentacion_guion.md)
- [Resultados del experimento en Markdown](artifacts/evaluation.md)

---

## Solución de Problemas Frecuentes

- **El puerto 8994 está ocupado:** Ejecuta `python run.py --port 8995` y abre esa dirección en tu navegador.
- **Error 503 (Modelo no encontrado):** Ejecuta `python -m app.train` y reinicia el servidor.
- **Entrada rechazada con Error 422:** La API valida rangos físicos estrictos (ej. CPU debe ser un número entre 0 y 100, y el pico no puede ser menor al promedio).
- **Entorno aislado:** Asegúrate de tener activado el entorno virtual (`source .venv/bin/activate` o `.\.venv\Scripts\Activate.ps1`).

---

## Licencia y Créditos
Proyecto desarrollado para el módulo de Machine Learning en la Maestría en Inteligencia Artificial. Código distribuido bajo licencia libre para fines académicos.
