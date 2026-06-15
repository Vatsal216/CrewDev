#!/usr/bin/env bash
set -e

echo "=== CrewDev Platform Setup ==="

# Check .env
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env — fill in your API keys before running!"
  echo "  ANTHROPIC_API_KEY=sk-ant-..."
  echo "  VOYAGE_API_KEY=pa-..."
  echo "  TAVILY_API_KEY=tvly-..."
  echo ""
fi

# Docker services
echo "Starting Postgres, Redis..."
docker-compose up -d postgres redis
sleep 3

# Backend
echo "Installing Python deps..."
cd backend
pip install -r requirements.txt -q
echo "Starting backend..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Frontend
echo "Installing Node deps..."
cd frontend
npm install -q
echo "Starting frontend..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=== CrewDev running ==="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker-compose stop" EXIT
wait
