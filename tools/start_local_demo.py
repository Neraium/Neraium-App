#!/usr/bin/env python3
"""
Local demo starter — launches Neraium backend + frontend.
Usage: python tools/start_local_demo.py
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nShutting down...")
    if backend_process:
        backend_process.terminate()
    if frontend_process:
        frontend_process.terminate()
    sys.exit(0)

def check_backend_ready(max_retries=30):
    """Check if backend is ready to accept requests."""
    import socket
    for i in range(max_retries):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=1):
                print("✓ Backend ready")
                return True
        except (socket.timeout, ConnectionRefusedError):
            if i < max_retries - 1:
                time.sleep(1)
    return False

backend_process = None
frontend_process = None

if __name__ == "__main__":
    print("\n🚀 Starting Neraium Demo...\n")

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Check Python environment
    if sys.platform == "win32":
        venv_activate = BACKEND_DIR / ".venv" / "Scripts" / "activate.bat"
    else:
        venv_activate = BACKEND_DIR / ".venv" / "bin" / "activate"

    # Create venv if needed
    if not venv_activate.exists():
        print("📦 Creating Python virtual environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(BACKEND_DIR / ".venv")],
            cwd=str(BACKEND_DIR),
            check=True
        )
        print("✓ Virtual environment created")

    # Install dependencies
    print("📦 Installing Python dependencies...")
    if sys.platform == "win32":
        subprocess.run(
            [str(BACKEND_DIR / ".venv" / "Scripts" / "pip"), "install", "-q", "-e", ".."],
            cwd=str(BACKEND_DIR),
            check=True
        )
    else:
        subprocess.run(
            [str(BACKEND_DIR / ".venv" / "bin" / "pip"), "install", "-q", "-e", ".."],
            cwd=str(BACKEND_DIR),
            check=True
        )
    print("✓ Dependencies installed")

    # Start backend
    print("📡 Starting backend (uvicorn on :8000)...")
    if sys.platform == "win32":
        backend_process = subprocess.Popen(
            f'"{BACKEND_DIR / ".venv" / "Scripts" / "uvicorn"}" server:app --reload --host 127.0.0.1 --port 8000',
            cwd=str(BACKEND_DIR),
            shell=True
        )
    else:
        backend_process = subprocess.Popen(
            [str(BACKEND_DIR / ".venv" / "bin" / "uvicorn"), "server:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BACKEND_DIR)
        )

    # Wait for backend to be ready
    if not check_backend_ready():
        print("✗ Backend failed to start")
        backend_process.terminate()
        sys.exit(1)

    # Install frontend dependencies
    print("📦 Installing Node dependencies...")
    subprocess.run(
        ["npm", "install", "-q"],
        cwd=str(FRONTEND_DIR),
        check=True,
        capture_output=True
    )
    print("✓ Node dependencies installed")

    # Start frontend
    print("🎨 Starting frontend (React on :3006)...")
    env = os.environ.copy()
    env["PORT"] = "3006"
    env["REACT_APP_BACKEND_URL"] = "http://localhost:8000"

    if sys.platform == "win32":
        frontend_process = subprocess.Popen(
            "npm start",
            cwd=str(FRONTEND_DIR),
            env=env,
            shell=True
        )
    else:
        frontend_process = subprocess.Popen(
            ["npm", "start"],
            cwd=str(FRONTEND_DIR),
            env=env
        )

    # Give frontend time to start
    time.sleep(3)

    print("\n✅ All systems running!\n")
    print("   Backend:  http://127.0.0.1:8000")
    print("   Frontend: http://localhost:3006")
    print("\n   Press Ctrl+C to stop\n")

    try:
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)
