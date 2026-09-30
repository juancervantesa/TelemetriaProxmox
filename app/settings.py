"""Shared configuration, operational thresholds, telemetry features and scenario definitions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
FRONTEND_DIR = ROOT / "frontend"

SEED = 42
FALSE_ALARM_BUDGET = 0.05

# Temporal Windowing Settings
WINDOW_SIZE_MINUTES = 10
WINDOW_STEP_MINUTES = 2

# Temporal partition boundaries (covering Proxmox telemetry span: Sept 2 to Sept 30, 2026)
TRAIN_END = "2026-09-18T00:00:00"
VALIDATION_END = "2026-09-25T00:00:00"

# Telemetry features aggregated per 10-minute window
TELEMETRY_FEATURES = {
    "cpu_mean": {"label": "CPU promedio", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 24.5},
    "cpu_max": {"label": "CPU pico", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 35.0},
    "cpu_std": {"label": "Variabilidad CPU (desv)", "unit": "%", "min": 0.0, "max": 50.0, "step": 0.1, "default": 3.2},
    "cpu_trend": {"label": "Tendencia CPU (pendiente)", "unit": "%/10m", "min": -50.0, "max": 50.0, "step": 0.1, "default": 0.4},
    "memory_pct_mean": {"label": "Memoria RAM promedio", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 48.0},
    "memory_pct_max": {"label": "Memoria RAM pico", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 51.5},
    "memory_pct_trend": {"label": "Tendencia RAM (pendiente)", "unit": "%/10m", "min": -50.0, "max": 50.0, "step": 0.1, "default": 0.2},
    "iowait_mean": {"label": "I/O Wait promedio", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 0.3},
    "iowait_max": {"label": "I/O Wait pico", "unit": "%", "min": 0.0, "max": 100.0, "step": 0.1, "default": 1.2},
    "net_io_mb_s": {"label": "Tráfico de red", "unit": "MB/s", "min": 0.0, "max": 500.0, "step": 0.1, "default": 12.5},
    "temp_max_c": {"label": "Temperatura máxima hardware", "unit": "°C", "min": 20.0, "max": 110.0, "step": 0.5, "default": 48.0},
}

FEATURES = list(TELEMETRY_FEATURES.keys())

# Operational Thresholds (Baseline SIGeCAD rules)
BASELINE_THRESHOLDS = {
    "warning": {
        "cpu_max": 80.0,
        "memory_pct_max": 85.0,
        "iowait_max": 15.0,
        "temp_max_c": 75.0,
    },
    "critical": {
        "cpu_max": 90.0,
        "memory_pct_max": 95.0,
        "iowait_max": 30.0,
        "temp_max_c": 85.0,
    }
}

# Predefined operational scenarios for demo and testing
SCENARIOS = [
    {
        "id": "usual",
        "name": "Operación normal de servicio",
        "description": "Carga moderada y estable típica en clúster Proxmox. Ambos métodos reportan normalidad.",
        "expected_alert": False,
        "values": {
            "cpu_mean": 24.5,
            "cpu_max": 35.0,
            "cpu_std": 3.2,
            "cpu_trend": 0.4,
            "memory_pct_mean": 48.0,
            "memory_pct_max": 51.5,
            "memory_pct_trend": 0.2,
            "iowait_mean": 0.3,
            "iowait_max": 1.2,
            "net_io_mb_s": 12.5,
            "temp_max_c": 48.0,
        }
    },
    {
        "id": "memory_leak",
        "name": "Fuga de memoria progresiva (Memory Leak)",
        "description": "Una VM acumula memoria continuamente (+28% en la ventana). Isolation Forest detecta la anomalía de tendencia antes de que el umbral estático de la línea base (85%) se alcance.",
        "expected_alert": True,
        "values": {
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
            "temp_max_c": 50.5,
        }
    },
    {
        "id": "storage_stall",
        "name": "Contención de disco / Fallo de storage",
        "description": "I/O Wait crítico debido a desconexión de volumen Ceph/LVM. La CPU real es baja pero las transacciones quedan encoladas.",
        "expected_alert": True,
        "values": {
            "cpu_mean": 14.0,
            "cpu_max": 28.0,
            "cpu_std": 6.8,
            "cpu_trend": -2.0,
            "memory_pct_mean": 55.0,
            "memory_pct_max": 58.0,
            "memory_pct_trend": 0.5,
            "iowait_mean": 38.5,
            "iowait_max": 72.0,
            "net_io_mb_s": 1.2,
            "temp_max_c": 52.0,
        }
    },
    {
        "id": "cpu_overheat",
        "name": "Sobrecalentamiento térmico de nodo físico",
        "description": "Lecturas térmicas en nodo Proxmox DL-360 superan umbrales de seguridad operacional debido a fallo en ventiladores o sobrecarga.",
        "expected_alert": True,
        "values": {
            "cpu_mean": 58.0,
            "cpu_max": 74.0,
            "cpu_std": 8.5,
            "cpu_trend": 6.5,
            "memory_pct_mean": 62.0,
            "memory_pct_max": 65.0,
            "memory_pct_trend": 1.0,
            "iowait_mean": 1.5,
            "iowait_max": 4.0,
            "net_io_mb_s": 22.0,
            "temp_max_c": 87.5,
        }
    },
    {
        "id": "vm_crash",
        "name": "Inestabilidad previa a caída QEMU (VM Crash)",
        "description": "Ráfaga descontrolada de llamadas a red y volatilidad extrema de CPU antes de que el proceso QEMU termine en error.",
        "expected_alert": True,
        "values": {
            "cpu_mean": 78.0,
            "cpu_max": 96.0,
            "cpu_std": 28.4,
            "cpu_trend": -15.0,
            "memory_pct_mean": 88.0,
            "memory_pct_max": 94.0,
            "memory_pct_trend": -8.0,
            "iowait_mean": 18.0,
            "iowait_max": 45.0,
            "net_io_mb_s": 185.0,
            "temp_max_c": 68.0,
        }
    },
    {
        "id": "legitimate_batch",
        "name": "Caso difícil: Tarea de compresión/backup legítima",
        "description": "CPU alta sostenida (86%) pero con volatilidad baja, memoria constante y temperatura dentro del rango seguro. Mide si el modelo evita falsas alarmas ante picos operacionales válidos.",
        "expected_alert": False,
        "values": {
            "cpu_mean": 84.0,
            "cpu_max": 88.0,
            "cpu_std": 1.8,
            "cpu_trend": 0.1,
            "memory_pct_mean": 60.0,
            "memory_pct_max": 62.0,
            "memory_pct_trend": 0.1,
            "iowait_mean": 2.1,
            "iowait_max": 4.5,
            "net_io_mb_s": 35.0,
            "temp_max_c": 64.0,
        }
    },
    {
        "id": "combined_incident",
        "name": "Incidente múltiple concurrente",
        "description": "Degradación generalizada en nodo y máquinas virtuales: CPU saturada, I/O wait elevado y fuga de memoria simultánea.",
        "expected_alert": True,
        "values": {
            "cpu_mean": 91.0,
            "cpu_max": 98.5,
            "cpu_std": 14.2,
            "cpu_trend": 8.0,
            "memory_pct_mean": 94.0,
            "memory_pct_max": 98.0,
            "memory_pct_trend": 12.0,
            "iowait_mean": 26.0,
            "iowait_max": 58.0,
            "net_io_mb_s": 140.0,
            "temp_max_c": 82.0,
        }
    }
]
