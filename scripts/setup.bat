@echo off
REM Windows setup script

echo Setting up project structure...

REM Create directories
mkdir "data\documents" 2>nul
mkdir "data\index" 2>nul
mkdir "data\chroma" 2>nul
mkdir "data\golden" 2>nul
mkdir "reports" 2>nul
mkdir "logs" 2>nul

REM Copy environment file
if not exist ".env" (
    copy ".env.example" ".env"
    echo Created .env file from template
)

echo Project structure ready!