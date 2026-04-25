@echo off
REM Launch Neraium: backend + frontend + browser

echo.
echo 🚀 Starting Neraium...
echo.

REM Start backend in new window
echo 📦 Starting backend...
start "Neraium Backend" cmd /k "cd backend && ..\\.venv\\Scripts\\activate.bat && uvicorn server:app --reload --host 127.0.0.1 --port 8000"

REM Start frontend in new window
echo 🎨 Starting frontend...
start "Neraium Frontend" cmd /k "cd frontend && npm start"

REM Wait for servers to start
timeout /t 3 /nobreak

REM Open browser
echo 🌐 Opening browser...
start http://localhost:3000

echo.
echo ✅ All systems running!
echo.
echo    Backend:  http://127.0.0.1:8000
echo    Frontend: http://localhost:3000
echo.
