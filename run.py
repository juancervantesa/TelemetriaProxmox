"""Start the SIGeCAD Telemetry Anomaly Detection system. Creates missing data and model artifacts automatically."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="SIGeCAD: Detección de Anomalías en Telemetría de Centro de Datos (Proxmox VE).")
    parser.add_argument("--rebuild", action="store_true", help="Regenera dataset y re-entrena el modelo antes de iniciar.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host IP local (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8994, help="Puerto HTTP local (default: 8994).")
    args = parser.parse_args()

    data_missing = not all((ROOT / "data" / name).exists() for name in ["telemetry_windows.csv", "incidents.json"])
    artifacts_missing = not all((ROOT / "artifacts" / name).exists() for name in ["model.joblib", "metrics.json"])

    if args.rebuild or data_missing:
        print("[SIGeCAD] Generando/verificando conjunto de ventanas de telemetría...")
        subprocess.run([sys.executable, "-m", "app.data"], cwd=ROOT, check=True)

    if args.rebuild or data_missing or artifacts_missing:
        print("[SIGeCAD] Ejecutando pipeline de entrenamiento y evaluación...")
        subprocess.run([sys.executable, "-m", "app.train"], cwd=ROOT, check=True)

    print(f"\n=======================================================")
    print(f" SIGeCAD - Centro de Datos Proxmox VE")
    print(f" Servidor iniciado en http://{args.host}:{args.port}")
    print(f" Presione Ctrl+C para detener el servicio.")
    print(f"=======================================================\n", flush=True)

    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)],
        cwd=ROOT,
        check=True
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SIGeCAD] Servicio detenido correctamente.")
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"[SIGeCAD Error] Falló un paso con código {error.returncode}. Revise README.md.") from None
