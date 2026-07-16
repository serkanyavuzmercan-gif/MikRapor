# MikRapor — tek dosya Windows .exe
# Kullanım: .\build_exe.ps1
# Derleme tanımı: MikRapor.spec (tek kaynak — asset / hiddenimport / exclude listesi orada).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Sanal ortam olusturuluyor..."
    python -m venv .venv
}

try {
    & .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt *> $null
    & .\.venv\Scripts\python.exe -m pip install -q "pyinstaller>=6.3.0" *> $null
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

if (-not (Test-Path "MikRapor.spec")) {
    Write-Error "MikRapor.spec bulunamadi."
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& .\.venv\Scripts\pyinstaller.exe --clean --noconfirm MikRapor.spec 2>&1 | Out-Host
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
