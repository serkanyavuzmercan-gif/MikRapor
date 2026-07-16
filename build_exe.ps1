# MikRapor — tek dosya Windows .exe
# Kullanım: .\build_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Sanal ortam olusturuluyor..."
    python -m venv .venv
}

try {
    & .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt *> $null
} catch {
    Write-Warning "pip install uyarisi (devam ediliyor)."
}

if (Test-Path "assets\logo_source.png") {
    Write-Host "Logo ve ikonlar uretiliyor..."
    & .\.venv\Scripts\python.exe assets\generate_icons.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Logo/ikon uretimi basarisiz."
    }
}

Get-Process -Name "MikRapor" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "Mikrapor" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "MizanAnaliz" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& .\.venv\Scripts\pyinstaller.exe `
    --onefile `
    --windowed `
    --noconsole `
    --noupx `
    --name MikRapor `
    --icon "assets\icon.ico" `
    --add-data "assets\icon.ico;assets" `
    --add-data "assets\logo.png;assets" `
    --hidden-import matplotlib.backends.backend_qtagg `
    --hidden-import reportlab `
    --hidden-import PyQt6.QtCore `
    --hidden-import PyQt6.QtGui `
    --hidden-import PyQt6.QtWidgets `
    --hidden-import PyQt6.QtNetwork `
    --exclude-module PyQt6.Qt3DAnimation `
    --exclude-module PyQt6.Qt3DCore `
    --exclude-module PyQt6.Qt3DExtras `
    --exclude-module PyQt6.Qt3DInput `
    --exclude-module PyQt6.Qt3DLogic `
    --exclude-module PyQt6.Qt3DRender `
    --exclude-module PyQt6.QtWebEngine `
    --exclude-module PyQt6.QtWebEngineCore `
    --exclude-module PyQt6.QtWebEngineWidgets `
    --exclude-module PyQt6.QtQml `
    --exclude-module PyQt6.QtQuick `
    --clean `
    main.py 2>&1 | Out-Host
$pyExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($pyExit -ne 0) {
    Write-Error "PyInstaller derlemesi basarisiz (cikis kodu $pyExit)."
}

$ExePath = Join-Path $Root "dist\MikRapor.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "dist\MikRapor.exe olusmadi."
}
$SizeMb = [math]::Round((Get-Item $ExePath).Length / 1MB, 2)
if ($SizeMb -lt 15) {
    Write-Warning "Exe beklenenden kucuk ($SizeMb MB). Derlemeyi kontrol edin."
}

Write-Host ""
Write-Host "Derleme tamam ($SizeMb MB):"
Write-Host "  $ExePath"
