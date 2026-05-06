"""Start the local Neraium demo stack.

This script is intentionally boring and explicit:
- writes the React backend URL into .env and .env.local
- starts FastAPI from the backend directory, where its imports resolve
- waits until the PRONOSTIA API responds
- starts the React dev server

Run from the repo root:
    python tools/start_local_demo.py
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def write_frontend_env(api_url: str) -> None:
    value = f"REACT_APP_BACKEND_URL={api_url}\n"
    for name in (".env", ".env.local"):
        path = FRONTEND_DIR / name
        path.write_text(value, encoding="utf-8")
        print(f"[ENV] {path.relative_to(ROOT)} -> {api_url}", flush=True)


def wait_for_backend(url: str, timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    print(f"[BACKEND] ready: {url}", flush=True)
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return False


def start_process(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    print(f"[START] {' '.join(command)}", flush=True)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        creationflags=creationflags,
    )


def stop_process(process: subprocess.Popen, name: str) -> None:
    if process.poll() is not None:
        return
    print(f"[STOP] {name}", flush=True)
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        process.wait(timeout=8)
    except Exception:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Neraium backend and frontend locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8010)
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--skip-report", action="store_true", help="Do not generate the operator explanation report.")
    args = parser.parse_args()

    api_url = f"http://{args.host}:{args.backend_port}"
    write_frontend_env(api_url)

    report_path = ROOT / "results" / "operator_explanation_report.md"
    if not args.skip_report and not report_path.exists():
        print("[REPORT] generating operator explanation report", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "generate_operator_explanation_report.py")],
            cwd=str(ROOT),
            check=False,
        )

    health_url = f"{api_url}/api/demo/pronostia/decisions"
    backend = None
    if wait_for_backend(health_url, timeout_seconds=3):
        print(f"[BACKEND] reusing existing server on {api_url}", flush=True)
    else:
        backend = start_process(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "server:app",
                "--host",
                args.host,
                "--port",
                str(args.backend_port),
            ],
            cwd=BACKEND_DIR,
        )

        if not wait_for_backend(health_url):
            stop_process(backend, "backend")
            print(f"[ERROR] backend did not become ready at {health_url}", flush=True)
            return 1

    frontend_env = os.environ.copy()
    frontend_env["PORT"] = str(args.frontend_port)
    frontend_env["REACT_APP_BACKEND_URL"] = api_url
    npm = "npm.cmd" if os.name == "nt" else "npm"
    frontend = start_process([npm, "start"], cwd=FRONTEND_DIR, env=frontend_env)

    print("", flush=True)
    print(f"[READY] Backend:  {api_url}", flush=True)
    print(f"[READY] Frontend: http://localhost:{args.frontend_port}", flush=True)
    print("[READY] Press Ctrl+C here to stop both.", flush=True)

    try:
        while True:
            if backend is not None and backend.poll() is not None:
                print("[ERROR] backend exited", flush=True)
                return backend.returncode or 1
            if frontend.poll() is not None:
                print("[ERROR] frontend exited", flush=True)
                return frontend.returncode or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] stopping local demo", flush=True)
        stop_process(frontend, "frontend")
        if backend is not None:
            stop_process(backend, "backend")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
