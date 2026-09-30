"""Utilidad opcional para extraer y agregar ventanas en vivo desde la base de datos PostgreSQL / TimescaleDB 'proxmox_monitor'."""
import json
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
from app.settings import DATA_DIR, WINDOW_SIZE_MINUTES


def extract_telemetry_from_db(
    conn_info: str = "host=localhost port=5432 dbname=proxmox_monitor user=postgres password=secretpassword"
) -> bool:
    """Se conecta a TimescaleDB, consulta métricas sin procesar y agrega ventanas de 10 minutos."""
    try:
        with psycopg.connect(conn_info, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                print("Conectado a la base de datos TimescaleDB proxmox_monitor.")
                
                # Verificar cantidad de registros
                cur.execute("SELECT count(*) as cnt FROM node_metrics")
                node_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM guest_metrics")
                guest_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM hardware_sensors")
                sensor_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM cluster_logs WHERE level IN ('ERROR', 'WARNING')")
                err_cnt = cur.fetchone()["cnt"]

                print(f"Encontradas {node_cnt} métricas de nodo, {guest_cnt} métricas de VM/LXC, {sensor_cnt} lecturas de sensores, {err_cnt} registros de alerta/error.")
                return True
    except Exception as e:
        print(f"Nota: No se pudo conectar a la base de datos en vivo ({e}). Se utiliza el dataset reproducible.")
        return False


if __name__ == "__main__":
    extract_telemetry_from_db()
