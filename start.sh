#!/bin/bash
set -e

echo "=== NASDAQ Flow Terminal ==="
echo ""

# Backend
echo "[1/2] Starting FastAPI backend on port 8000..."
cd backend
pip install -r requirements.txt -q
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Frontend
echo "[2/2] Starting React frontend on port 3000..."
cd ../frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "=== Ready ==="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

wait
