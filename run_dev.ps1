# MikRapor — geliştirme ortamında çalıştır
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Sanal ortam olusturuluyor..."
    python -m venv .venv
}

& .\.venv\Scripts\pip.exe install -q -r requirements.txt
& .\.venv\Scripts\python.exe main.py
