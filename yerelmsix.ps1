# MikRapor — Store MSIX'ini YEREL Windows makinede uretir.
#
# NEDEN: GitHub Actions kesintide (06.08.2026 major outage), kosu kuyrukta oldu.
# Bu betik .github/workflows/msix.yml'in Store paketi ureten adimlarini birebir
# tekrarlar. Yan yukleme paketi, kendinden imzali sertifika ve WACK ADIMLARI YOK:
# Store'a yuklenen paket IMZASIZDIR (Microsoft kendisi imzalar) ve WACK'i Store
# zaten kendi tarafinda kosturuyor.
#
# KULLANIM (repo kokunde, normal PowerShell — yonetici gerekmez):
#     cd C:\...\MikRapor
#     git pull
#     powershell -ExecutionPolicy Bypass -File yerel-msix.ps1
#
# CIKTI: out\MikRapor-<surum>-store.msix   → Partner Center'a bu yuklenir.

$ErrorActionPreference = "Stop"

# Turkce cikti Windows konsolunu dusuruyor (cp1252'de 'i' UnicodeEncodeError atar).
# Workflow bunu is duzeyinde yapiyor; burada da ayni.
$env:PYTHONIOENCODING = "utf-8"

function Adim($n, $metin) { Write-Host "`n[$n] $metin" -ForegroundColor Cyan }
function Dogrula($sart, $mesaj) { if (-not $sart) { throw $mesaj } }

Dogrula (Test-Path "MikRapor.spec") "Repo kokunde degilsiniz (MikRapor.spec yok)."
Dogrula (Test-Path "packaging/AppxManifest.xml") "packaging/AppxManifest.xml yok."

Adim 1 "Bagimliliklar"
python -m pip install --upgrade pip
Dogrula ($LASTEXITCODE -eq 0) "pip guncellenemedi"
pip install -r requirements.txt
Dogrula ($LASTEXITCODE -eq 0) "requirements.txt kurulamadi"
pip install "pyinstaller>=6.3.0" pillow
Dogrula ($LASTEXITCODE -eq 0) "pyinstaller/pillow kurulamadi"

Adim 2 "Testler (magazaya dogrulanmamis kod gitmez)"
python -m unittest discover -s . -p "test_*.py" -q
Dogrula ($LASTEXITCODE -eq 0) "TESTLER DUSTU — paket uretilmedi."

Adim 3 "Asset uret (logo, ikon, MSIX kutuciklari, chevron)"
python assets/generate_icons.py
Dogrula ($LASTEXITCODE -eq 0) "assets/generate_icons.py dustu"

Adim 4 "Surumu oku"
$surum = (Select-String -Path infra/surum.py -Pattern '^SURUM = "(.+)"').Matches[0].Groups[1].Value
# MSIX dort parcali ister; son parcayi Store kendine ayirdigi icin 0 kalir.
$msixSurum = "$surum.0"
Write-Host "    Surum: $surum -> MSIX $msixSurum"

Adim 5 "Derle (onedir — MSIX govdesi)"
# onefile MSIX'e KONMAZ: her acilista paketi gecici klasore actirir.
$env:MIKRAPOR_ONEDIR = "1"
pyinstaller --clean --noconfirm MikRapor.spec
Dogrula ($LASTEXITCODE -eq 0) "pyinstaller dustu"
Remove-Item Env:\MIKRAPOR_ONEDIR

Adim 6 "Paket klasorunu kur"
$pkg = "msix-root"
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
Copy-Item -Recurse dist/MikRapor $pkg
Copy-Item packaging/AppxManifest.xml "$pkg/AppxManifest.xml"
New-Item -ItemType Directory -Force -Path "$pkg/assets" | Out-Null
Copy-Item assets/store/*.png "$pkg/assets/"
# Surum manifest'e BURADA yazilir — repodaki 0.0.0.0 bilerek gecersizdir,
# tek surum kaynagi infra/surum.py.
$m = "$pkg/AppxManifest.xml"
(Get-Content $m -Raw) -replace 'Version="0\.0\.0\.0"', "Version=`"$msixSurum`"" |
  Set-Content $m -Encoding UTF8
Dogrula (Select-String -Path $m -Pattern ([regex]::Escape("Version=`"$msixSurum`"")) -Quiet) `
  "Manifest surumu yazilamadi — yer tutucu degismedi."
Dogrula (Test-Path "$pkg/MikRapor.exe") "$pkg/MikRapor.exe yok."

Adim 7 "Windows SDK araclarini bul"
$bin = Get-ChildItem "C:/Program Files (x86)/Windows Kits/10/bin" -Directory -ErrorAction SilentlyContinue |
       Where-Object { Test-Path "$($_.FullName)/x64/makeappx.exe" } |
       Sort-Object Name -Descending | Select-Object -First 1
if (-not $bin) {
  throw @"
makeappx.exe bulunamadi — Windows SDK kurulu degil.
Kurulum: https://developer.microsoft.com/windows/downloads/windows-sdk/
Kurarken "Windows SDK Signing Tools for Desktop Apps" secili olsun.
"@
}
$sdk = "$($bin.FullName)/x64"
Write-Host "    SDK: $sdk"

Adim 8 "MSIX paketle (Store icin — IMZASIZ)"
New-Item -ItemType Directory -Force -Path out | Out-Null
$cikti = "out/MikRapor-$surum-store.msix"
& "$sdk/makeappx.exe" pack /d $pkg /p $cikti /o
Dogrula ($LASTEXITCODE -eq 0) "makeappx basarisiz ($LASTEXITCODE)"

$boyut = [math]::Round((Get-Item $cikti).Length / 1MB, 1)
Write-Host "`nHAZIR: $cikti  ($boyut MB)" -ForegroundColor Green
Write-Host "Partner Center > Paketler bolumune BU dosya yuklenir. Imzalamayin." -ForegroundColor Green
