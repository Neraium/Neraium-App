# Neraium Launcher

Launch both backend and frontend with a **single command**.

## Quick Start

### Linux / macOS
```bash
cd ~/Documents/Neraium-App
python3 launch.py
# or
./launch.sh
```

### Windows
```bash
cd C:\Users\YourUsername\Documents\Neraium-App
python launch.py
# or double-click: launch.bat
```

## What it does

1. ✅ Creates Python virtual environment (if needed)
2. ✅ Installs backend dependencies
3. ✅ Installs frontend dependencies
4. ✅ Configures frontend with PORT=3006
5. ✅ Starts backend on `http://127.0.0.1:8000`
6. ✅ Starts frontend on `http://localhost:3006`

## Services

Once running, you'll have:

| Service | URL | Purpose |
|---------|-----|---------|
| Backend | http://127.0.0.1:8000 | API server (uvicorn) |
| Frontend | http://localhost:3006 | React UI |

## Stopping

Press `Ctrl+C` to stop both services gracefully.

## Requirements

- Python 3.10+
- Node.js 18+
- npm or yarn

## Troubleshooting

**Port already in use?**
```bash
# Kill process on port 8000 (Linux/Mac)
lsof -ti :8000 | xargs kill -9

# Or use a different port in launch.py
```

**Virtual environment issues?**
```bash
# Remove and recreate
rm -rf backend/.venv
python3 launch.py
```

**Dependencies not installing?**
```bash
# Manually install
cd backend
python3 -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
pip install -e ..

cd ../frontend
npm install
PORT=3006 npm start
```

## File locations

- `launch.py` - Main Python launcher (all platforms)
- `launch.sh` - Shell wrapper for Unix/Linux/Mac
- `launch.bat` - Batch wrapper for Windows
- `tools/start_local_demo.py` - Alternative launcher with more options

---

Happy coding! 🚀
