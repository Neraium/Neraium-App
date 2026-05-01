#!/usr/bin/env python3
"""
Neraium Unified Launcher
Starts backend (uvicorn :8000) + frontend (React :3006) with one command
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND = PROJECT_ROOT / "backend"
FRONTEND = PROJECT_ROOT / "frontend"

def cleanup(sig=None, frame=None):
    """Kill both processes on Ctrl+C"""
    print("\n\n🛑 Shutting down...\n")
    if backend_proc:
        backend_proc.terminate()
    if frontend_proc:
        frontend_proc.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
backend_proc = None
frontend_proc = None

def run():
    global backend_proc, frontend_proc

    print("\n" + "="*60)
    print("🚀 NERAIUM LAUNCHER")
    print("="*60 + "\n")

    # Setup Python venv if needed
    venv_path = BACKEND / ".venv"
    if not venv_path.exists():
        print("📦 Creating Python virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    # Install Python deps
    print("📦 Installing backend dependencies...")
    if sys.platform == "win32":
        pip_cmd = str(venv_path / "Scripts" / "pip")
    else:
        pip_cmd = str(venv_path / "bin" / "pip")
    subprocess.run([pip_cmd, "install", "-q", "-e", ".."], cwd=str(BACKEND), check=True)

    # Setup frontend .env
    env_file = FRONTEND / ".env"
    env_file.write_text("PORT=3006\nREACT_APP_BACKEND_URL=http://localhost:8000\n")

    # Install Node deps
    print("📦 Installing frontend dependencies...")
    subprocess.run(["npm", "install", "-q"], cwd=str(FRONTEND), check=True)

    # Start backend
    print("📡 Starting backend (port 8000)...")
    if sys.platform == "win32":
        uvicorn = str(venv_path / "Scripts" / "uvicorn")
        backend_proc = subprocess.Popen(
            f'"{uvicorn}" server:app --reload --host 127.0.0.1 --port 8000',
            cwd=str(BACKEND),
            shell=True
        )
    else:
        uvicorn = str(venv_path / "bin" / "uvicorn")
        backend_proc = subprocess.Popen(
            [uvicorn, "server:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BACKEND)
        )

    # Wait for backend
    time.sleep(2)

    # Start frontend
    print("🎨 Starting frontend (port 3006)...")
    env = os.environ.copy()
    env["PORT"] = "3006"
    env["REACT_APP_BACKEND_URL"] = "http://localhost:8000"

    if sys.platform == "win32":
        frontend_proc = subprocess.Popen(
            'set "PORT=3006" && npm start',
            cwd=str(FRONTEND),
            env=env,
            shell=True
        )
    else:
        frontend_proc = subprocess.Popen(
            ["env", "PORT=3006", "npm", "start"],
            cwd=str(FRONTEND),
            env=env
        )

    # Print startup info
    print("\n" + "="*60)
    print("✅ SYSTEMS RUNNING")
    print("="*60)
    print("\n📡 Backend:  http://127.0.0.1:8000")
    print("🎨 Frontend: http://localhost:3006\n")
    print("Press Ctrl+C to stop\n")
    print("="*60 + "\n")

    # Keep running
    backend_proc.wait()
    frontend_proc.wait()

if __name__ == "__main__":
    run()
