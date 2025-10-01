#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting RAG Development Environment...${NC}"

# Check if ports are available
if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${RED}Error: Port 8000 is already in use.${NC}"
    echo "Run 'make stop' or 'lsof -ti:8000 | xargs kill -9' to free the port."
    exit 1
fi

if lsof -tiTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${RED}Error: Port 5173 is already in use.${NC}"
    echo "Run 'make stop' or 'lsof -ti:5173 | xargs kill -9' to free the port."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Services stopped.${NC}"
    exit 0
}

trap cleanup EXIT INT TERM

# Start backend
echo -e "${GREEN}Starting backend server on http://localhost:8000${NC}"
(cd backend && PYTHONPATH=. uvicorn main:app --reload --port 8000) &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend server on http://localhost:5173${NC}"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}RAG System is running!${NC}"
echo -e "${GREEN}Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}Backend API: http://localhost:8000${NC}"
echo -e "${GREEN}API Docs: http://localhost:8000/docs${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID