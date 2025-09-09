# PowerShell run script for Windows

Write-Host "Starting RAG system..." -ForegroundColor Green

# Function to check if port is in use
function Test-Port {
    param([int]$Port)
    try {
        $listener = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return ($listener | Where-Object { $_.Port -eq $Port }).Count -gt 0
    }
    catch {
        return $false
    }
}

# Check if backend port is already in use
if (Test-Port 8000) {
    Write-Host "Port 8000 is already in use. Please stop the existing backend server." -ForegroundColor Yellow
    exit 1
}

# Start backend
Write-Host "Starting backend server..." -ForegroundColor Cyan
$backendJob = Start-Job -ScriptBlock {
    Set-Location "backend"
    $env:PYTHONPATH = "."
    python -m uvicorn main:app --reload --port 8000
}

# Wait for backend to start
Start-Sleep -Seconds 3

# Check if backend started successfully
if ($backendJob.State -eq "Running") {
    Write-Host "Backend started successfully" -ForegroundColor Green
} else {
    Write-Host "Failed to start backend" -ForegroundColor Red
    Receive-Job $backendJob
    exit 1
}

# Start frontend
Write-Host "Starting frontend server..." -ForegroundColor Cyan
try {
    Set-Location "frontend"
    npm run dev
} catch {
    Write-Host "Failed to start frontend: $_" -ForegroundColor Red
    Stop-Job $backendJob
    Remove-Job $backendJob
    exit 1
} finally {
    # Cleanup
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -ErrorAction SilentlyContinue
}