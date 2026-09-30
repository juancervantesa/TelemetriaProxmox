"""FastAPI REST application and static web service for SIGeCAD telemetry anomaly detection."""
import json
from contextlib import asynccontextmanager
import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
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
    """Loads and verifies model and metrics artifacts on server startup."""
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

# Serve static frontend files
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation errors into friendly Spanish JSON responses."""
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
    """Ensures model bundle is loaded before inference."""
    if app.state.bundle is None:
        raise HTTPException(
            status_code=503,
            detail="El modelo aún no ha sido entrenado. Ejecute 'python -m app.train' y reinicie el servidor."
        )
    return app.state.bundle


@app.get("/")
def home():
    """Serves the main frontend dashboard."""
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return {"status": "backend_ready", "message": "Frontend en construcción."}
    return FileResponse(index_file)


@app.get("/api/health")
def health():
    """System health check endpoint."""
    has_model = app.state.bundle is not None
    return {
        "status": "ok" if has_model else "model_missing",
        "system": "SIGeCAD Data Center Telemetry Anomaly Detector",
        "version": app.state.bundle.get("version") if has_model else None,
        "features_count": len(FEATURES)
    }


@app.get("/api/config")
def config():
    """Returns telemetry schema metadata, thresholds and pre-configured scenarios."""
    return {
        "features": TELEMETRY_FEATURES,
        "feature_order": FEATURES,
        "baseline_thresholds": BASELINE_THRESHOLDS,
        "scenarios": SCENARIOS
    }


@app.get("/api/metrics")
def metrics():
    """Returns test and validation metrics comparing Isolation Forest against Baseline."""
    require_model()
    return app.state.report


@app.get("/api/events")
def events():
    """Returns the catalog of operational incident events and their test detection outcomes."""
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
    """Performs real-time anomaly inference for an aggregated telemetry window."""
    bundle = require_model()
    result = inspect_reading(bundle, window.model_dump())
    return result
