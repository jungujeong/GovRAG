# PowerShell installation script for Windows

Write-Host "Installing dependencies..." -ForegroundColor Green

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Python not found. Please install Python 3.12 or later." -ForegroundColor Red
    exit 1
}

# Check Node.js installation
try {
    $nodeVersion = node --version 2>&1
    Write-Host "Found Node.js: $nodeVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Node.js not found. Please install Node.js 18 or later." -ForegroundColor Red
    exit 1
}

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install Python dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "requirements.txt not found" -ForegroundColor Yellow
}

# Download models
Write-Host "Downloading models..." -ForegroundColor Cyan
if (Test-Path "setup_offline.py") {
    python setup_offline.py --download-models
}

# Check Tesseract
Write-Host "Checking Tesseract OCR..." -ForegroundColor Cyan
try {
    $tesseractVersion = tesseract --version 2>&1
    Write-Host "Found Tesseract: $($tesseractVersion.Split("`n")[0])" -ForegroundColor Green
} catch {
    Write-Host "Tesseract not found. Please install manually:" -ForegroundColor Yellow
    Write-Host "  Download from: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "  Make sure to install Korean language pack" -ForegroundColor Yellow
}

# Install frontend dependencies
Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
if (Test-Path "frontend/package.json") {
    Set-Location "frontend"
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install frontend dependencies" -ForegroundColor Red
        Set-Location ".."
        exit 1
    }
    Set-Location ".."
} else {
    Write-Host "frontend/package.json not found" -ForegroundColor Yellow
}

Write-Host "Installation complete!" -ForegroundColor Green