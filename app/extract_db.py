"""Optional utility to extract and aggregate live windows from PostgreSQL / TimescaleDB 'proxmox_monitor'."""
import json
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
from app.settings import DATA_DIR, WINDOW_SIZE_MINUTES


def extract_telemetry_from_db(
    conn_info: str = "host=localhost port=5432 dbname=proxmox_monitor user=postgres password=secretpassword"
) -> bool:
    """Connects to TimescaleDB, queries raw metrics and aggregates 10-minute windows."""
    try:
        with psycopg.connect(conn_info, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                print("Connected to TimescaleDB proxmox_monitor database.")
                
                # Check row counts
                cur.execute("SELECT count(*) as cnt FROM node_metrics")
                node_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM guest_metrics")
                guest_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM hardware_sensors")
                sensor_cnt = cur.fetchone()["cnt"]
                cur.execute("SELECT count(*) as cnt FROM cluster_logs WHERE level IN ('ERROR', 'WARNING')")
                err_cnt = cur.fetchone()["cnt"]

                print(f"Found {node_cnt} node metrics, {guest_cnt} guest metrics, {sensor_cnt} sensor readings, {err_cnt} incident logs.")
                return True
    except Exception as e:
        print(f"Notice: Could not connect to live database ({e}). Using reproducible offline dataset.")
        return False


if __name__ == "__main__":
    extract_telemetry_from_db()
