param([ValidateRange(1024,65535)][int]$Port = 8501)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "SmartMove - Transportation Intelligence" -ForegroundColor Cyan
Write-Host "Local synthetic-data edition. No real payments or GPS feed."
try {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -m venv .venv
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
            if ($LASTEXITCODE -ne 0) { throw "Install Python 3.12 (64-bit), then reopen this window." }
            & python -m venv .venv
        } else { throw "Python was not found. Install Python 3.12 (64-bit) from python.org and select Add Python to PATH." }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) { throw "Virtual environment creation failed. Verify: py -3.12 --version" }
    }
    & $python -c "import sys; assert sys.version_info >= (3,12), 'This .venv uses an older Python. Rename it and restart setup.'"
    if ($LASTEXITCODE -ne 0) { throw "Python version check failed." }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Keep the error message; do not continue to launch." }
    $newCredentials = -not (Test-Path "data\LOCAL_CREDENTIALS.txt")
    & $python -m smartmove.bootstrap
    if ($LASTEXITCODE -ne 0) { throw "Database or account setup failed." }
    if ($newCredentials -and (Test-Path "data\LOCAL_CREDENTIALS.txt")) {
        Start-Process notepad.exe -ArgumentList ('"' + (Join-Path $root "data\LOCAL_CREDENTIALS.txt") + '"')
    }
    Write-Host "Credentials: $root\data\LOCAL_CREDENTIALS.txt" -ForegroundColor Yellow
    Write-Host "Open http://localhost:$Port . Keep this window open. Ctrl+C stops the app." -ForegroundColor Green
    $browserJob = Start-Job -ArgumentList $Port -ScriptBlock {
        param($p)
        for ($i = 0; $i -lt 45; $i++) {
            try {
                $health = Invoke-RestMethod "http://localhost:$p/api/health" -TimeoutSec 2
                if ($health.application -eq "SmartMove") { Start-Process "http://localhost:$p"; break }
            } catch { }
            Start-Sleep -Seconds 1
        }
    }
    try { & $python run.py --port $Port }
    finally { Stop-Job $browserJob -ErrorAction SilentlyContinue; Remove-Job $browserJob -Force -ErrorAction SilentlyContinue }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
