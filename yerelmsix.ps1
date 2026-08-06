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

# PS 5.1 TUZAGI: $ErrorActionPreference='Stop' iken yerel bir programin stderr'e
# yazmasi SONLANDIRICI hata uretiyor - ve '2>$null' bunu ONLEMIYOR, tersine
# yonlendirmenin kendisi ErrorRecord dogurmasina sebep oluyor. py.exe "No
# suitable Python runtime found" yazinca betik ilk adaydan sonra oluyordu;
# ikinci adaya ve asil yardimci mesaja hic ulasamiyordu. Yoklamalar bu yuzden
# bu iki yardimcidan gecer.
function PyVar([string]$s) {
    $eski = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $tamam = $false
    try {
        $null = & py ('-' + $s) -c 'pass' 2>&1
        $tamam = ($LASTEXITCODE -eq 0)
    }
    catch { $tamam = $false }
    finally {
        $ErrorActionPreference = $eski
        $global:LASTEXITCODE = 0
        $Error.Clear()
    }
    return $tamam
}

function VarsayilanSurum() {
    $eski = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $sonuc = ''
    try {
        $c = & python -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2>&1
        if ($LASTEXITCODE -eq 0) { $sonuc = ($c | Select-Object -First 1).ToString().Trim() }
    }
    catch { $sonuc = '' }
    finally {
        $ErrorActionPreference = $eski
        $global:LASTEXITCODE = 0
        $Error.Clear()
    }
    return $sonuc
}

Dogrula (Test-Path 'MikRapor.spec') 'Repo kokunde degilsiniz (MikRapor.spec yok).'
Dogrula (Test-Path 'packaging/AppxManifest.xml') 'packaging/AppxManifest.xml yok.'

# --------------------------------------------------------------------------
Adim 1 'Uygun Python ile sanal ortam kur'
# winsdk 1.0.0b10 YALNIZCA cp38-cp312 icin hazir wheel yayinliyor. Daha yeni bir
# Python'da pip kaynaktan derlemeye kalkiyor, o da Visual Studio + CMake + nmake
# istiyor ve "Failed building wheel for winsdk" ile duruyor. Workflow Python 3.11
# kullandigi icin CI'da hic gorulmedi.
#
# winsdk ATLANAMAZ: paketlenmezse Store lisansi hic okunamaz ve premium ODEYEN
# musteride bile acilmaz (bkz. test_paketleme.TestStoreKoprusuPaketleniyor).
#
# Sanal ortam kullaniliyor ki sistem Python'unuz degismesin; ikinci kosuda
# yeniden kurulmaz.
$uygun = @('3.12', '3.11')
$venv = '.venv-msix'
if (-not (Test-Path $venv)) {
    $secilen = $null
    foreach ($s in $uygun) {
        if (PyVar $s) { $secilen = $s; break }
    }
    if ($null -ne $secilen) {
        & py ('-' + $secilen) -m venv $venv
        Dogrula ($LASTEXITCODE -eq 0) 'Sanal ortam kurulamadi.'
        Write-Host ('    Python ' + $secilen + ' (py launcher)')
    }
    else {
        # py launcher hic kurulu olmayabilir; varsayilan python zaten uygunsa o kullanilir.
        $vs = VarsayilanSurum
        if ($uygun -contains $vs) {
            & python -m venv $venv
            Dogrula ($LASTEXITCODE -eq 0) 'Sanal ortam kurulamadi.'
            Write-Host ('    Python ' + $vs + ' (varsayilan; py launcher yok)')
        }
        else {
            $etiket = $vs
            if ([string]::IsNullOrWhiteSpace($etiket)) { $etiket = '(python bulunamadi)' }
            Write-Host ''
            Write-Host 'Python 3.11 veya 3.12 bulunamadi.' -ForegroundColor Red
            Write-Host ('  Kurulu varsayilan surum : ' + $etiket)
            Write-Host '  Gereken                 : 3.11 ya da 3.12'
            Write-Host ''
            Write-Host 'SEBEP: Microsoft Store lisansini okuyan winsdk paketi yalnizca'
            Write-Host 'Python 3.8-3.12 icin hazir surum yayinliyor. Daha yenisinde pip'
            Write-Host 'kaynaktan derlemeye kalkiyor, o da Visual Studio + CMake istiyor.'
            Write-Host 'winsdk ATLANAMAZ: olmadan premium, odeyen musteride bile acilmaz.'
            Write-Host ''
            Write-Host 'COZUM - mevcut Python surumunuz SILINMEZ, yan yana durur:' -ForegroundColor Yellow
            Write-Host '  winget install Python.Python.3.12'
            Write-Host 'ya da https://www.python.org/downloads/windows/ adresinden'
            Write-Host '3.12.x "Windows installer (64-bit)" - kurulumda "py launcher"'
            Write-Host 'isaretli olsun. Sonra bu betigi tekrar calistirin.'
            throw 'Uygun Python surumu yok.'
        }
    }
}
else {
    Write-Host '    Mevcut .venv-msix kullaniliyor'
}
$py = Join-Path (Resolve-Path $venv).Path 'Scripts\python.exe'
Dogrula (Test-Path $py) 'Sanal ortamda python.exe yok - .venv-msix klasorunu silip tekrar deneyin.'
& $py -c "import sys; print('    Yorumlayici: %d.%d.%d' % sys.version_info[:3])"

# --------------------------------------------------------------------------
Adim 2 'Bagimliliklar'
& $py -m pip install --upgrade pip
Dogrula ($LASTEXITCODE -eq 0) 'pip guncellenemedi'
& $py -m pip install -r requirements.txt
Dogrula ($LASTEXITCODE -eq 0) 'requirements.txt kurulamadi'
& $py -m pip install 'pyinstaller>=6.3.0' pillow
Dogrula ($LASTEXITCODE -eq 0) 'pyinstaller/pillow kurulamadi'

# winsdk gercekten kuruldu mu: sessizce eksik kalirsa premium hic acilmaz.
& $py -c "import winsdk; print('    winsdk tamam')"
Dogrula ($LASTEXITCODE -eq 0) 'winsdk kurulamadi - paket premium acamaz, uretim durduruldu.'

# --------------------------------------------------------------------------
Adim 3 'Testler (magazaya dogrulanmamis kod gitmez)'
& $py -m unittest discover -s . -p 'test_*.py' -q
Dogrula ($LASTEXITCODE -eq 0) 'TESTLER DUSTU - paket uretilmedi.'

# --------------------------------------------------------------------------
Adim 4 'Asset uret (logo, ikon, MSIX kutuciklari, chevron)'
& $py assets/generate_icons.py
Dogrula ($LASTEXITCODE -eq 0) 'assets/generate_icons.py dustu'

# --------------------------------------------------------------------------
Adim 5 'Surumu oku'
$esles = Select-String -Path 'infra/surum.py' -Pattern '^SURUM = "(.+)"'
Dogrula ($null -ne $esles) 'infra/surum.py icinde SURUM satiri bulunamadi'
$surum = $esles.Matches[0].Groups[1].Value
# MSIX dort parcali ister; son parcayi Store kendine ayirdigi icin 0 kalir.
$msixSurum = $surum + '.0'
Write-Host ('    Surum: ' + $surum + ' -> MSIX ' + $msixSurum)

# --------------------------------------------------------------------------
Adim 6 'Derle (onedir, MSIX govdesi)'
# onefile MSIX'e KONMAZ: her acilista paketi gecici klasore actirir.
$env:MIKRAPOR_ONEDIR = '1'
& $py -m PyInstaller --clean --noconfirm MikRapor.spec
$pyKod = $LASTEXITCODE
Remove-Item Env:\MIKRAPOR_ONEDIR
Dogrula ($pyKod -eq 0) 'pyinstaller dustu'

# --------------------------------------------------------------------------
Adim 7 'Paket klasorunu kur'
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

# --------------------------------------------------------------------------
Adim 8 'Windows SDK araclarini bul'
$kits = 'C:/Program Files (x86)/Windows Kits/10/bin'
$bin = $null
if (Test-Path $kits) {
    $bin = Get-ChildItem $kits -Directory |
           Where-Object { Test-Path ($_.FullName + '/x64/makeappx.exe') } |
           Sort-Object Name -Descending |
           Select-Object -First 1
}
if ($null -eq $bin) {
    Write-Host ''
    Write-Host 'makeappx.exe bulunamadi - Windows SDK kurulu degil.' -ForegroundColor Red
    Write-Host 'Indirme: https://developer.microsoft.com/windows/downloads/windows-sdk/'
    Write-Host 'Kurarken "Windows SDK Signing Tools for Desktop Apps" secili olsun.'
    throw 'Windows SDK yok.'
}
$sdk = $bin.FullName + '/x64'
Write-Host ('    SDK: ' + $sdk)

# --------------------------------------------------------------------------
Adim 9 'MSIX paketle (Store icin, IMZASIZ)'
New-Item -ItemType Directory -Force -Path 'out' | Out-Null
$cikti = 'out/MikRapor-' + $surum + '-store.msix'
& ($sdk + '/makeappx.exe') pack /d $pkg /p $cikti /o
Dogrula ($LASTEXITCODE -eq 0) ('makeappx basarisiz (' + $LASTEXITCODE + ')')

$boyut = [math]::Round((Get-Item $cikti).Length / 1MB, 1)
Write-Host ''
Write-Host ('HAZIR: ' + $cikti + '  (' + $boyut + ' MB)') -ForegroundColor Green
Write-Host 'Partner Center > Paketler bolumune BU dosya yuklenir. Imzalamayin.' -ForegroundColor Green
