$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Run START_SMARTMOVE.bat once to create the environment." }
& $python -m pip install -r requirements-analytics.txt
if ($LASTEXITCODE -ne 0) { throw "Analytics installation failed." }
& $python -m analytics.pipeline
if ($LASTEXITCODE -ne 0) { throw "Analytics run failed. Existing output files may be from different run times; inspect the log." }
Write-Host "Analytics and Power BI CSV exports refreshed." -ForegroundColor Green
