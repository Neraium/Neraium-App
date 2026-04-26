#!/bin/bash
# Launch Neraium: backend + frontend (Linux/Mac version)

cd "$(dirname "$0")"

echo "🚀 Starting Neraium..."

# Trap Ctrl+C to kill both processes
trap 'echo ""; echo "Shutting down..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' INT

# Check if .venv exists, create if needed
if [ ! -d "backend/.venv" ]; then
  echo "📦 Creating Python virtual environment..."
  cd backend
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -e ..
  cd ..
fi

# Start backend
echo "📦 Starting backend..."
cd backend
source .venv/bin/activate
uvicorn server:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
sleep 2

# Start frontend
echo "🎨 Starting frontend..."
cd frontend
npm install -q
npm start &
FRONTEND_PID=$!
cd ..

echo "✅ All systems running!"
echo "   Backend: http://127.0.0.1:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for processes
wait
