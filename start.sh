#!/bin/bash
set -e

echo "Starting RAG Chatbot System..."

# Check environment
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Warning: Ollama not running. Please start Ollama first."
    echo "Run: ollama serve"
    exit 1
fi

# Start backend
echo "Starting backend server..."
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend
echo "Waiting for backend..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    sleep 1
done

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "System started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop"

# Wait and handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait