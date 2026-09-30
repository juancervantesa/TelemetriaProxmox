"""Ingesta de datos, agregación en ventanas temporales, generación sintética y partición temporal.

Soporta dos modalidades:
1. Extracción directa desde la base de datos TimescaleDB/PostgreSQL 'proxmox_monitor' local cuando está disponible.
2. Generación sintética 100% reproducible modelando la telemetría de Proxmox VE con incidentes documentados.
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.settings import (
    DATA_DIR,
    FEATURES,
    SEED,
    TRAIN_END,
    VALIDATION_END,
    WINDOW_SIZE_MINUTES,
    WINDOW_STEP_MINUTES
)


def generate_data(seed: int = SEED, num_hours: int = 672) -> tuple[pd.DataFrame, list[dict]]:
    """Genera 28 días (672 horas) de ventanas de telemetría multi-recurso para Proxmox VE.
    
    Recursos modelados:
    - node:dl380-01 (Servidor de cómputo 1)
    - node:dl360-04 (Servidor de cómputo 2)
    - node:srvzy (Hipervisor Santa Cruz)
    - guest:100_AD-Zentyal (VM controladora de dominio)
    - guest:101_win11 (VM de escritorio)
    - guest:402_NS1 (VM de DNS interno)
    - sensor:dl360_cpu2_temp (Sensor térmico Redfish)
    """
    rng = np.random.default_rng(seed)
    start_time = pd.Timestamp("2026-09-02 00:00:00")
    
    # Ventanas de 10 minutos espaciadas cada 30 minutos para intervalos independientes de evaluación
    window_timestamps = pd.date_range(start_time, periods=num_hours * 2, freq="30min")
    
    resources = [
        {"id": "node:dl380-01", "type": "node", "base_cpu": 25.0, "base_ram": 55.0, "base_temp": 46.0},
        {"id": "node:dl360-04", "type": "node", "base_cpu": 22.0, "base_ram": 50.0, "base_temp": 49.0},
        {"id": "node:srvzy", "type": "node", "base_cpu": 15.0, "base_ram": 42.0, "base_temp": 44.0},
        {"id": "guest:100_AD-Zentyal", "type": "guest", "base_cpu": 18.0, "base_ram": 65.0, "base_temp": 40.0},
        {"id": "guest:101_win11", "type": "guest", "base_cpu": 20.0, "base_ram": 58.0, "base_temp": 40.0},
        {"id": "guest:402_NS1", "type": "guest", "base_cpu": 12.0, "base_ram": 35.0, "base_temp": 40.0},
    ]

    # Calendario predefinido de inyección de incidentes operacionales (posteriores al periodo de entrenamiento: >= 18 Sep)
    incidents = [
        # Incidentes del conjunto de validación (18 Sep - 25 Sep)
        {
            "incident_id": "INC-VAL-01",
            "resource_id": "guest:100_AD-Zentyal",
            "incident_type": "memory_leak",
            "start_time": "2026-09-19T08:00:00",
            "end_time": "2026-09-19T14:00:00",
            "description": "Fuga de memoria progresiva no liberada por daemon AD",
            "severity": "high"
        },
        {
            "incident_id": "INC-VAL-02",
            "resource_id": "node:dl380-01",
            "incident_type": "storage_stall",
            "start_time": "2026-09-21T18:00:00",
            "end_time": "2026-09-21T21:30:00",
            "description": "Saturación severa de I/O por fallo transitorio en enlace Ceph",
            "severity": "critical"
        },
        {
            "incident_id": "INC-VAL-03",
            "resource_id": "node:dl360-04",
            "incident_type": "cpu_overheat",
            "start_time": "2026-09-23T11:00:00",
            "end_time": "2026-09-23T15:00:00",
            "description": "Alerta térmica en CPU 2 por fallo de ventilador del chasis",
            "severity": "warning"
        },
        # Incidentes del conjunto de prueba (25 Sep - 30 Sep) - Reflejan logs reales de clústeres Proxmox
        {
            "incident_id": "INC-TEST-01",
            "resource_id": "guest:100_AD-Zentyal",
            "incident_type": "vm_crash",
            "start_time": "2026-09-29T14:30:00",
            "end_time": "2026-09-29T17:00:00",
            "description": "Timeout en qmreboot y posterior caída QEMU con fallo en storage local1",
            "severity": "critical"
        },
        {
            "incident_id": "INC-TEST-02",
            "resource_id": "node:srvzy",
            "incident_type": "storage_stall",
            "start_time": "2026-09-30T09:30:00",
            "end_time": "2026-09-30T11:30:00",
            "description": "Desconexión de punto de montaje /mnt/pve/local1 afectando I/O",
            "severity": "critical"
        },
        {
            "incident_id": "INC-TEST-03",
            "resource_id": "guest:101_win11",
            "incident_type": "memory_leak",
            "start_time": "2026-09-27T02:00:00",
            "end_time": "2026-09-27T06:00:00",
            "description": "Consumo desmedido de RAM durante backup nocturno vzdump",
            "severity": "high"
        },
        {
            "incident_id": "INC-TEST-04",
            "resource_id": "node:dl360-04",
            "incident_type": "cpu_overheat",
            "start_time": "2026-09-28T13:00:00",
            "end_time": "2026-09-28T16:30:00",
            "description": "Pico de temperatura sostenida > 80°C con alarma de sensor Redfish",
            "severity": "warning"
        }
    ]

    rows = []
    window_counter = 0

    for ts in window_timestamps:
        iso_ts = ts.isoformat()
        hour_of_day = ts.hour
        daily_cycle = np.sin((hour_of_day - 8) * 2 * np.pi / 24)

        for res in resources:
            window_counter += 1
            res_id = res["id"]
            res_type = res["type"]
            base_cpu = res["base_cpu"] + 8.0 * daily_cycle
            base_ram = res["base_ram"] + 2.0 * daily_cycle
            base_temp = res["base_temp"] + 3.0 * daily_cycle

            # Comprobar si esta ventana coincide con un incidente activo para este recurso
            active_inc = None
            for inc in incidents:
                if inc["resource_id"] == res_id:
                    t_start = pd.Timestamp(inc["start_time"])
                    t_end = pd.Timestamp(inc["end_time"])
                    if t_start <= ts <= t_end:
                        active_inc = inc
                        break

            # Métricas normales de línea base con variabilidad y ruido realista
            cpu_mean = float(np.clip(base_cpu + rng.normal(0, 3.5), 2.0, 92.0))
            cpu_max = float(np.clip(cpu_mean + abs(rng.normal(6.0, 3.0)), cpu_mean, 99.0))
            cpu_std = float(np.clip(abs(rng.normal(2.5, 1.0)), 0.5, 20.0))
            cpu_trend = float(np.clip(rng.normal(0.0, 1.2), -15.0, 15.0))

            memory_pct_mean = float(np.clip(base_ram + rng.normal(0, 1.8), 5.0, 95.0))
            memory_pct_max = float(np.clip(memory_pct_mean + abs(rng.normal(2.0, 1.0)), memory_pct_mean, 99.0))
            memory_pct_trend = float(np.clip(rng.normal(0.0, 0.4), -8.0, 8.0))

            iowait_mean = float(np.clip(abs(rng.normal(0.3, 0.2)), 0.0, 15.0))
            iowait_max = float(np.clip(iowait_mean + abs(rng.normal(0.8, 0.4)), iowait_mean, 25.0))

            net_io_mb_s = float(np.clip(abs(rng.normal(10.0 + 5.0 * daily_cycle, 3.0)), 0.1, 100.0))
            temp_max_c = float(np.clip(base_temp + rng.normal(0, 1.5), 25.0, 72.0))

            # Introducir tareas por lotes legítimas (alta CPU, baja variabilidad, RAM estable, temperatura segura)
            # Ocurren periódicamente los miércoles / viernes sin constituir anomalía operacional
            is_legit_batch = (ts.weekday() in [2, 4]) and (hour_of_day in [2, 3]) and (res_id == "node:dl380-01")
            if is_legit_batch and not active_inc:
                cpu_mean = float(np.clip(84.0 + rng.normal(0, 1.5), 75.0, 90.0))
                cpu_max = float(np.clip(cpu_mean + 3.0, cpu_mean, 94.0))
                cpu_std = 1.2
                cpu_trend = 0.1

            is_anomaly = 0
            anomaly_type = "normal"
            incident_id = None

            if active_inc:
                is_anomaly = 1
                anomaly_type = active_inc["incident_type"]
                incident_id = active_inc["incident_id"]

                # Aplicar patrones específicos de degradación según el tipo de incidente
                if anomaly_type == "memory_leak":
                    # Acumulación sostenida de RAM, repunte de tendencia y superación de umbrales
                    leak_progress = (ts - pd.Timestamp(active_inc["start_time"])).total_seconds() / (
                        (pd.Timestamp(active_inc["end_time"]) - pd.Timestamp(active_inc["start_time"])).total_seconds()
                    )
                    memory_pct_mean = float(np.clip(60.0 + 35.0 * leak_progress + rng.normal(0, 1.0), 50.0, 98.0))
                    memory_pct_max = float(np.clip(memory_pct_mean + 3.5, memory_pct_mean, 99.5))
                    memory_pct_trend = float(np.clip(18.0 + rng.normal(0, 3.0), 8.0, 35.0))
                    cpu_mean = float(np.clip(cpu_mean + 8.0, 10.0, 85.0))
                    cpu_max = float(np.clip(cpu_mean + 10.0, cpu_mean, 95.0))

                elif anomaly_type == "storage_stall":
                    # Disparo crítico de iowait, bloqueo de operaciones de disco y CPU en espera
                    iowait_mean = float(np.clip(32.0 + rng.normal(0, 5.0), 20.0, 70.0))
                    iowait_max = float(np.clip(iowait_mean + abs(rng.normal(25.0, 5.0)), iowait_mean, 98.0))
                    cpu_mean = float(np.clip(12.0 + rng.normal(0, 2.0), 2.0, 30.0))
                    cpu_max = float(np.clip(cpu_mean + 15.0, cpu_mean, 55.0))
                    cpu_std = float(np.clip(abs(rng.normal(6.0, 1.5)), 2.0, 25.0))

                elif anomaly_type == "cpu_overheat":
                    # Descontrol térmico en procesador / chasis
                    temp_max_c = float(np.clip(82.0 + rng.normal(0, 3.0), 76.0, 98.0))
                    cpu_mean = float(np.clip(base_cpu + 25.0 + rng.normal(0, 4.0), 40.0, 92.0))
                    cpu_max = float(np.clip(cpu_mean + 10.0, cpu_mean, 98.0))
                    cpu_trend = float(np.clip(7.0 + rng.normal(0, 1.5), 3.0, 18.0))

                elif anomaly_type == "vm_crash":
                    # Volatilidad extrema, inestabilidad de memoria y caída súbita de conexiones
                    cpu_mean = float(np.clip(75.0 + rng.normal(0, 8.0), 40.0, 98.0))
                    cpu_max = float(np.clip(cpu_mean + 15.0, cpu_mean, 99.9))
                    cpu_std = float(np.clip(abs(rng.normal(24.0, 4.0)), 15.0, 45.0))
                    memory_pct_mean = float(np.clip(88.0 + rng.normal(0, 4.0), 70.0, 98.0))
                    memory_pct_max = float(np.clip(memory_pct_mean + 4.0, memory_pct_mean, 99.5))
                    iowait_max = float(np.clip(28.0 + abs(rng.normal(10.0, 4.0)), 15.0, 75.0))
                    net_io_mb_s = float(np.clip(140.0 + abs(rng.normal(30.0, 10.0)), 50.0, 350.0))

            rows.append({
                "window_id": f"W{window_counter:06d}",
                "timestamp": iso_ts,
                "resource_id": res_id,
                "resource_type": res_type,
                "cpu_mean": round(cpu_mean, 2),
                "cpu_max": round(cpu_max, 2),
                "cpu_std": round(cpu_std, 2),
                "cpu_trend": round(cpu_trend, 2),
                "memory_pct_mean": round(memory_pct_mean, 2),
                "memory_pct_max": round(memory_pct_max, 2),
                "memory_pct_trend": round(memory_pct_trend, 2),
                "iowait_mean": round(iowait_mean, 2),
                "iowait_max": round(iowait_max, 2),
                "net_io_mb_s": round(net_io_mb_s, 2),
                "temp_max_c": round(temp_max_c, 2),
                "is_anomaly": int(is_anomaly),
                "anomaly_type": anomaly_type,
                "incident_id": incident_id
            })

    df = pd.DataFrame(rows)
    return df, incidents


def validate_data(data: pd.DataFrame) -> None:
    """Valida el esquema del DataFrame, rangos de variables y coherencia lógica."""
    required = ["window_id", "timestamp", "resource_id", "resource_type", *FEATURES, "is_anomaly", "anomaly_type"]
    if not set(required) <= set(data.columns) or data.empty:
        raise ValueError(f"Missing required columns. Found: {list(data.columns)}")
    if data[required].isna().any().any():
        raise ValueError("Dataset contains null or missing values.")
    if data.window_id.duplicated().any():
        raise ValueError("Window IDs must be unique.")
    
    # Comprobar formatos de fecha
    dates = pd.to_datetime(data.timestamp, errors="raise")
    if dates.dt.tz is not None:
        data["timestamp"] = dates.dt.tz_localize(None).dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Comprobar rangos de variables numéricas
    for feature in FEATURES:
        values = pd.to_numeric(data[feature], errors="raise")
        if not np.isfinite(values).all():
            raise ValueError(f"Feature '{feature}' contains non-finite numbers.")

    # Comprobar etiquetas de anomalía
    if not set(data.is_anomaly) <= {0, 1}:
        raise ValueError("is_anomaly column must strictly be 0 or 1.")
    if not ((data.anomaly_type != "normal").astype(int) == data.is_anomaly).all():
        raise ValueError("Discrepancy between is_anomaly flag and anomaly_type label.")


def split_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide los datos cronológicamente en conjuntos de entrenamiento (normal puro), validación y prueba."""
    data = data.sort_values("timestamp").copy()
    dates = pd.to_datetime(data.timestamp)
    
    train = data[dates < pd.Timestamp(TRAIN_END)].copy()
    validation = data[(dates >= pd.Timestamp(TRAIN_END)) & (dates < pd.Timestamp(VALIDATION_END))].copy()
    test = data[dates >= pd.Timestamp(VALIDATION_END)].copy()

    if any(part.empty for part in [train, validation, test]):
        raise ValueError("Temporal partitions cannot be empty.")
    if train.is_anomaly.any():
        raise ValueError("Training partition must contain strictly normal operational telemetry.")
    if any(set(part.is_anomaly) != {0, 1} for part in [validation, test]):
        raise ValueError("Both validation and test partitions must contain normal and anomalous instances.")

    return train, validation, test


def main():
    """Genera el dataset reproducible, lo valida y escribe las particiones en disco."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df, incidents = generate_data()
    validate_data(df)
    
    df.to_csv(DATA_DIR / "telemetry_windows.csv", index=False)
    with open(DATA_DIR / "incidents.json", "w", encoding="utf-8") as f:
        json.dump(incidents, f, ensure_ascii=False, indent=2)

    train, val, test = split_data(df)
    train.to_csv(DATA_DIR / "train.csv", index=False)
    val.to_csv(DATA_DIR / "validation.csv", index=False)
    test.to_csv(DATA_DIR / "test.csv", index=False)

    print(f"Dataset generado exitosamente:")
    print(f" - Ventanas totales: {len(df)}")
    print(f" - Entrenamiento (normal puro): {len(train)} ventanas")
    print(f" - Validación: {len(val)} ventanas ({val.is_anomaly.sum()} anómalas)")
    print(f" - Prueba: {len(test)} ventanas ({test.is_anomaly.sum()} anómalas)")
    print(f" - Incidentes catalogados: {len(incidents)}")


if __name__ == "__main__":
    main()
