#!/bin/bash
# Kill any existing instances
pkill -f "python server.py" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null

# Start backend
echo "Starting backend..."
python server.py &

# Start frontend
echo "Starting frontend..."
cd frontend && npm run dev &

echo "JARVIS is starting. Open Chrome at http://localhost:5173"
echo "Press Ctrl+C to stop."
wait
