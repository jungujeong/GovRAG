#!/bin/bash
# Frontend startup wrapper with direct Node 18 path

cd "$(dirname "$0")/frontend"

# Use Node 18 directly (avoid nvm in subshell)
export PATH="$HOME/.nvm/versions/node/v18.20.8/bin:$PATH"

# Start Vite
exec npm run dev
