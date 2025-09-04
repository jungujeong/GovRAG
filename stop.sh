#!/bin/bash

echo "Stopping RAG Chatbot System..."

# Kill backend
pkill -f "uvicorn main:app" 2>/dev/null || true

# Kill frontend
pkill -f "vite" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

echo "System stopped."