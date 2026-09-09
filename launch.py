#!/usr/bin/env python3
"""Local analyst launcher. Install dependencies once using README instructions."""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent

def main():
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.server:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'], cwd=ROOT))
        env = {**os.environ, 'PORT': '3006', 'HOST': '127.0.0.1', 'BROWSER': 'none', 'REACT_APP_BACKEND_URL': 'http://127.0.0.1:8000'}
        children.append(subprocess.Popen(['npm.cmd' if os.name == 'nt' else 'npm', 'start'], cwd=ROOT / 'frontend', env=env))
        print('Internal workbench: http://127.0.0.1:3006', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()

if __name__ == '__main__':
    main()
