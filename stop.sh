#!/bin/bash
set -euo pipefail

echo "Stopping RAG Chatbot System..."

stop_by_name() {
  local pattern="$1"
  pkill -f "$pattern" >/dev/null 2>&1 || true
}

stop_by_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      echo "Killing processes on port $port: $pids"
      kill -9 $pids >/dev/null 2>&1 || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

# Kill by name (covers make run and start.sh variants)
stop_by_name "uvicorn main:app"
stop_by_name "python.*uvicorn.*main:app"
stop_by_name "vite"
stop_by_name "node.*vite"
stop_by_name "npm.*run dev"

# Also kill anything still bound to the dev ports
stop_by_port 8000
stop_by_port 5173

# Clean up any stale pid files if present
rm -f .backend.pid .frontend.pid

echo "System stopped."
