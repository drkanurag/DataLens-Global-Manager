"""DataLens Enterprise Microservices Orchestrator.

Launches all 6 microservices concurrently across ports 8000-8005:
  - Port 8000: API Gateway & Frontend Dashboard (`services.api_gateway.main:app`)
  - Port 8001: Auth & IAM Microservice (`services.auth_service.main:app`)
  - Port 8002: Workforce Analytics Microservice (`services.analytics_service.main:app`)
  - Port 8003: Data Quality & SAP Audit Microservice (`services.data_quality_service.main:app`)
  - Port 8004: Scoped AI Chatbot Microservice (`services.chatbot_service.main:app`)
  - Port 8005: GDPR & Compliance Microservice (`services.compliance_service.main:app`)
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent

SERVICES = [
    ("auth-service", "services.auth_service.main:app", 8001),
    ("analytics-service", "services.analytics_service.main:app", 8002),
    ("data-quality-service", "services.data_quality_service.main:app", 8003),
    ("chatbot-service", "services.chatbot_service.main:app", 8004),
    ("compliance-service", "services.compliance_service.main:app", 8005),
    ("api-gateway", "services.api_gateway.main:app", 8000),
]


def main():
    processes: list[tuple[str, int, subprocess.Popen]] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    env["DATALENS_PROXY_MODE"] = "1"

    print("=" * 72)
    print("  DataLens Enterprise — Microservices Mesh Orchestrator v4.0")
    print("=" * 72)

    try:
        for name, module, port in SERVICES:
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                module,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ]
            proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR), env=env)
            processes.append((name, port, proc))
            print(f"  [+] Started {name:<22} -> http://localhost:{port}")

        print("-" * 72)
        print("  Dashboard UI : http://localhost:8000/dashboard/")
        print("  Mesh Status  : http://localhost:8000/api/services/status")
        print("  Press Ctrl+C to stop all microservices.")
        print("=" * 72)

        while True:
            time.sleep(1)
            for name, port, proc in processes:
                if proc.poll() is not None:
                    print(f"[!] Service {name} (port {port}) exited with code {proc.returncode}")
                    return
    except KeyboardInterrupt:
        print("\nShutting down DataLens Microservices Mesh...")
    finally:
        for name, port, proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for name, port, proc in processes:
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        print("All microservices stopped cleanly.")


if __name__ == "__main__":
    main()
