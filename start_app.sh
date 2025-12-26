#!/bin/bash

# Kill ports 3000 and 8000 if they are in use to avoid conflicts
echo "Cleaning up ports..."
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Start Backend
echo "Starting Backend..."
cd backend
source venv/bin/activate
# Run in background
python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"

# Start Frontend
echo "Starting Frontend..."
cd ../frontend
# Run in background
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started with PID $FRONTEND_PID"

echo "------------------------------------------------"
echo "Application launched!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Logs are being written to backend.log and frontend.log"
echo "------------------------------------------------"
