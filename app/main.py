"""Aplicación REST FastAPI y servicio web estático para la detección de anomalías en telemetría de SIGeCAD."""
import json
from contextlib import asynccontextmanager
import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.inference import inspect_reading
from app.schemas import WindowInput
from app.settings import (
    ARTIFACT_DIR,
    FRONTEND_DIR,
    FEATURES,
    SCENARIOS,
    TELEMETRY_FEATURES,
    BASELINE_THRESHOLDS
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga y valida los artefactos del modelo y las métricas al iniciar el servidor."""
    app.state.bundle = None
    app.state.report = None
    
    model_path = ARTIFACT_DIR / "model.joblib"
    report_path = ARTIFACT_DIR / "metrics.json"

    if model_path.exists() and report_path.exists():
        bundle = joblib.load(model_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if bundle.get("version") != report.get("version") or bundle.get("features") != FEATURES:
            raise RuntimeError("Mismatch between model artifact and reported metrics. Please retrain.")
        app.state.bundle = bundle
        app.state.report = report
    yield


app = FastAPI(
    title="SIGeCAD - Detección de Anomalías en Telemetría Proxmox",
    description="Sistema inteligente de alerta temprana para centros de datos basado en Isolation Forest y ventanas temporales.",
    version="1.0.0",
    lifespan=lifespan
)

# Servir archivos estáticos del frontend
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formatea los errores de validación en respuestas JSON legibles en español."""
    errors = []
    for err in exc.errors():
        loc_str = " -> ".join(str(l) for l in err.get("loc", []))
        errors.append({
            "field": loc_str,
            "message": err.get("msg", "Valor de entrada inválido o fuera de rango"),
            "type": err.get("type", "value_error")
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "Error de validación en la ventana de telemetría ingresada",
            "detalles": errors
        }
    )


def require_model():
    """Garantiza que el paquete del modelo esté cargado antes de la inferencia."""
    if app.state.bundle is None:
        raise HTTPException(
            status_code=503,
            detail="El modelo aún no ha sido entrenado. Ejecute 'python -m app.train' y reinicie el servidor."
        )
    return app.state.bundle


@app.get("/")
def home():
    """Sirve el panel principal de la interfaz web."""
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return {"status": "backend_ready", "message": "Frontend en construcción."}
    return FileResponse(index_file)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Silencia las peticiones de favicon del navegador con 204 No Content."""
    return Response(status_code=204)


@app.get("/api/health")
def health():
    """Punto de verificación de estado y salud del sistema."""
    has_model = app.state.bundle is not None
    return {
        "status": "ok" if has_model else "model_missing",
        "system": "SIGeCAD Data Center Telemetry Anomaly Detector",
        "version": app.state.bundle.get("version") if has_model else None,
        "features_count": len(FEATURES)
    }


@app.get("/api/config")
def config():
    """Retorna metadatos del esquema de telemetría, umbrales y escenarios preconfigurados."""
    return {
        "features": TELEMETRY_FEATURES,
        "feature_order": FEATURES,
        "baseline_thresholds": BASELINE_THRESHOLDS,
        "scenarios": SCENARIOS
    }


@app.get("/api/metrics")
def metrics():
    """Retorna métricas de prueba y validación comparando Isolation Forest frente a la Línea Base."""
    require_model()
    return app.state.report


@app.get("/api/events")
def events():
    """Retorna el catálogo de eventos de incidentes operacionales y sus resultados en el conjunto de prueba."""
    require_model()
    test_eval = app.state.report.get("test", {}).get("model", {}).get("event_based", {})
    return {
        "total_incidents": test_eval.get("total_incidents", 0),
        "event_f1": test_eval.get("event_f1", 0.0),
        "avg_lead_time_minutes": test_eval.get("avg_lead_time_minutes", 0.0),
        "incidents": test_eval.get("incident_details", [])
    }


@app.post("/api/inspect")
def inspect(window: WindowInput):
    """Realiza la inferencia de anomalías en tiempo real para una ventana temporal de telemetría."""
    bundle = require_model()
    result = inspect_reading(bundle, window.model_dump())
    return result
