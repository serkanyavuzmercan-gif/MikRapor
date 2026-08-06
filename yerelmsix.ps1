# MikRapor - Store MSIX'ini YEREL Windows makinede uretir.
#
# NEDEN: GitHub Actions kesintide, kosu kuyrukta kaldi. Bu betik
# .github/workflows/msix.yml'in Store paketi ureten adimlarini tekrarlar.
# Yan yukleme paketi, kendinden imzali sertifika ve WACK adimlari YOK: Store'a
# yuklenen paket IMZASIZDIR (Microsoft kendisi imzalar), WACK'i de Store zaten
# kendi tarafinda kosturur.
#
# BU DOSYA SAF ASCII OLMAK ZORUNDA. Windows PowerShell 5.1, BOM'suz .ps1'i
# cp1252 okur; UTF-8 uzun tire (U+2014) orada UC karaktere bolunur ve
# sonuncusu KIVRIK KAPAMA TIRNAGIDIR (U+201D). PowerShell onu dize
# sonlandirici sayar, betik bastan asagi parse hatasi verir. Yasandi.
# Uzun tire yerine duz '-' yazin.
#
# KULLANIM (repo kokunde, yonetici gerekmez):
#     cd C:\mikrapor
#     powershell -ExecutionPolicy Bypass -File yerelmsix.ps1
#
# CIKTI: out\MikRapor-<surum>-store.msix  -> Partner Center'a bu yuklenir.

$ErrorActionPreference = 'Stop'

# Turkce cikti Windows konsolunu dusuruyor (cp1252'de UnicodeEncodeError).
$env:PYTHONIOENCODING = 'utf-8'

function Adim([int]$no, [string]$metin) {
    Write-Host ''
    Write-Host ("[" + $no + "] " + $metin) -ForegroundColor Cyan
}

function Dogrula([bool]$sart, [string]$mesaj) {
    if (-not $sart) { throw $mesaj }
}

Dogrula (Test-Path 'MikRapor.spec') 'Repo kokunde degilsiniz (MikRapor.spec yok).'
Dogrula (Test-Path 'packaging/AppxManifest.xml') 'packaging/AppxManifest.xml yok.'

Adim 1 'Bagimliliklar'
python -m pip install --upgrade pip
Dogrula ($LASTEXITCODE -eq 0) 'pip guncellenemedi'
pip install -r requirements.txt
Dogrula ($LASTEXITCODE -eq 0) 'requirements.txt kurulamadi'
pip install 'pyinstaller>=6.3.0' pillow
Dogrula ($LASTEXITCODE -eq 0) 'pyinstaller/pillow kurulamadi'

Adim 2 'Testler (magazaya dogrulanmamis kod gitmez)'
python -m unittest discover -s . -p 'test_*.py' -q
Dogrula ($LASTEXITCODE -eq 0) 'TESTLER DUSTU - paket uretilmedi.'

Adim 3 'Asset uret (logo, ikon, MSIX kutuciklari, chevron)'
python assets/generate_icons.py
Dogrula ($LASTEXITCODE -eq 0) 'assets/generate_icons.py dustu'

Adim 4 'Surumu oku'
$esles = Select-String -Path 'infra/surum.py' -Pattern '^SURUM = "(.+)"'
Dogrula ($null -ne $esles) 'infra/surum.py icinde SURUM satiri bulunamadi'
$surum = $esles.Matches[0].Groups[1].Value
# MSIX dort parcali ister; son parcayi Store kendine ayirdigi icin 0 kalir.
$msixSurum = $surum + '.0'
Write-Host ('    Surum: ' + $surum + ' -> MSIX ' + $msixSurum)

Adim 5 'Derle (onedir, MSIX govdesi)'
# onefile MSIX'e KONMAZ: her acilista paketi gecici klasore actirir.
$env:MIKRAPOR_ONEDIR = '1'
pyinstaller --clean --noconfirm MikRapor.spec
$pyKod = $LASTEXITCODE
Remove-Item Env:\MIKRAPOR_ONEDIR
Dogrula ($pyKod -eq 0) 'pyinstaller dustu'

Adim 6 'Paket klasorunu kur'
$pkg = 'msix-root'
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
Copy-Item -Recurse 'dist/MikRapor' $pkg
Copy-Item 'packaging/AppxManifest.xml' ($pkg + '/AppxManifest.xml')
New-Item -ItemType Directory -Force -Path ($pkg + '/assets') | Out-Null
Copy-Item 'assets/store/*.png' ($pkg + '/assets/')

# Surum manifest'e BURADA yazilir - repodaki 0.0.0.0 bilerek gecersizdir,
# tek surum kaynagi infra/surum.py. Duz metin degistirme (regex degil).
$m = $pkg + '/AppxManifest.xml'
$eski = 'Version="0.0.0.0"'
$yeni = 'Version="' + $msixSurum + '"'
$icerik = Get-Content $m -Raw
Dogrula ($icerik.Contains($eski)) 'Manifest yer tutucusu bulunamadi.'
Set-Content -Path $m -Value $icerik.Replace($eski, $yeni) -Encoding UTF8
$kontrol = Get-Content $m -Raw
Dogrula ($kontrol.Contains($yeni)) 'Manifest surumu yazilamadi.'
Dogrula (Test-Path ($pkg + '/MikRapor.exe')) 'msix-root/MikRapor.exe yok.'

Adim 7 'Windows SDK araclarini bul'
$kits = 'C:/Program Files (x86)/Windows Kits/10/bin'
$bin = $null
if (Test-Path $kits) {
    $bin = Get-ChildItem $kits -Directory |
           Where-Object { Test-Path ($_.FullName + '/x64/makeappx.exe') } |
           Sort-Object Name -Descending |
           Select-Object -First 1
}
if ($null -eq $bin) {
    Write-Host 'makeappx.exe bulunamadi - Windows SDK kurulu degil.' -ForegroundColor Red
    Write-Host 'Indirme: https://developer.microsoft.com/windows/downloads/windows-sdk/'
    Write-Host 'Kurarken "Windows SDK Signing Tools for Desktop Apps" secili olsun.'
    throw 'Windows SDK yok.'
}
$sdk = $bin.FullName + '/x64'
Write-Host ('    SDK: ' + $sdk)

Adim 8 'MSIX paketle (Store icin, IMZASIZ)'
New-Item -ItemType Directory -Force -Path 'out' | Out-Null
$cikti = 'out/MikRapor-' + $surum + '-store.msix'
& ($sdk + '/makeappx.exe') pack /d $pkg /p $cikti /o
Dogrula ($LASTEXITCODE -eq 0) ('makeappx basarisiz (' + $LASTEXITCODE + ')')

$boyut = [math]::Round((Get-Item $cikti).Length / 1MB, 1)
Write-Host ''
Write-Host ('HAZIR: ' + $cikti + '  (' + $boyut + ' MB)') -ForegroundColor Green
Write-Host 'Partner Center > Paketler bolumune BU dosya yuklenir. Imzalamayin.' -ForegroundColor Green
