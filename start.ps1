# Démarre l'application Ecole_Admin_Celia en local
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root "backend\.venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "==> Création du venv (Python 3.12)..." -ForegroundColor Cyan
    py -3.12 -m venv "$venv"
    & $python -m pip install -r (Join-Path $root "backend\requirements.txt")
}

Write-Host "==> Lancement sur http://localhost:8770" -ForegroundColor Green
Set-Location (Join-Path $root "backend")
& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8770 --reload
