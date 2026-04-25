#!/bin/bash
# Launch Neraium: backend + frontend + browser

cd "$(dirname "$0")"

echo "🚀 Starting Neraium..."

# Start backend in new terminal
echo "📦 Starting backend..."
start "Neraium Backend" bash -c "cd backend && source ../.venv/Scripts/activate && uvicorn server:app --reload --host 127.0.0.1 --port 8000; read"

# Start frontend in new terminal
echo "🎨 Starting frontend..."
start "Neraium Frontend" bash -c "cd frontend && npm start; read"

# Wait a moment for servers to start
sleep 3

# Open browser
echo "🌐 Opening browser..."
start http://localhost:3000

echo "✅ All systems running!"
echo "   Backend: http://127.0.0.1:8000"
echo "   Frontend: http://localhost:3000"
