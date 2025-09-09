@echo off
REM Windows run script

echo Starting RAG system...

REM Start backend in background
echo Starting backend server...
start /B "Backend" cmd /c "cd backend && set PYTHONPATH=. && uvicorn main:app --reload --port 8000"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
echo Starting frontend server...
cd frontend
npm run dev