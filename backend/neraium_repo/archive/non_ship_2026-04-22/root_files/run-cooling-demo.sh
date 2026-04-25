#!/bin/bash

# Cooling System Demo Runner
# Starts the frontend dev server and opens the demo in your browser

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "🔧 Neraium Cooling System Demo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ and try again."
    exit 1
fi

echo "✓ Node.js $(node --version) detected"

# Navigate to frontend directory
cd "$FRONTEND_DIR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Starting dev server..."
echo ""
echo "📍 The demo will be available at:"
echo "   → http://localhost:3000"
echo ""
echo "💡 What you'll see:"
echo "   1. Baseline: System operating normally (green)"
echo "   2. Early Drift: Efficiency degrading (yellow)"
echo "   3. Structural Shift: Failure risk detected (orange)"
echo "   4. Pre-instability: Immediate action required (red)"
echo ""
echo "⏱️  Demo auto-advances every ~14 seconds (~60 seconds total)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the dev server
npm run dev
