@echo off
REM Windows installation script

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python setup_offline.py --download-models

echo Setting up Tesseract OCR...
where tesseract >nul 2>nul
if %errorlevel% neq 0 (
    echo Tesseract not found. Please install manually:
    echo   Download from: https://github.com/UB-Mannheim/tesseract/wiki
    echo   Make sure to install Korean language pack
)

echo Installing frontend dependencies...
cd frontend
npm install
cd ..

echo Installation complete!